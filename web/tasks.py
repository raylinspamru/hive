from quart import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from quart_auth import login_required
from utils.database import get_roles, add_task, update_task_status, async_session, tasks_table, task_completions_table, roles_table, role_users_table, add_notification, get_task_completions, task_notifications_table
from sqlalchemy.sql import select
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

tasks_bp = Blueprint('tasks', __name__)

from web import notification_service

@tasks_bp.route('/', methods=['GET'])
@login_required
async def index():
    args = request.args
    page = int(args.get('page', 1))
    per_page = int(args.get('per_page', 25))
    status_filter = args.get('status', 'all')
    deadline_filter = args.get('deadline', 'all')
    executor_filter = args.get('executor', 'all')
    frequency_filter = args.get('frequency', 'all')
    search_query = args.get('search', '')

    async with async_session() as session:
        roles = await get_roles()
        groups = sorted(set(role.role_group for role in roles if role.role_group))

        query = select(tasks_table)
        if status_filter != 'all':
            query = query.where(tasks_table.c.status == status_filter)
        now = datetime.now()
        if deadline_filter == 'overdue':
            query = query.where(tasks_table.c.due_at < now)
        elif deadline_filter == 'today':
            query = query.where(tasks_table.c.due_at >= now).where(tasks_table.c.due_at < now + timedelta(days=1))
        elif deadline_filter == 'future':
            query = query.where(tasks_table.c.due_at >= now + timedelta(days=1))
        if executor_filter != 'all':
            query = query.where(tasks_table.c.role_id == executor_filter)
        if frequency_filter != 'all':
            query = query.where(tasks_table.c.repeat_interval == frequency_filter)
        if status_filter == 'overdue':
            query = query.where(tasks_table.c.due_at < now).where(tasks_table.c.status != 'completed')
        if search_query:
            query = query.where(tasks_table.c.description.ilike(f"%{search_query}%"))

        total_tasks = (await session.execute(query)).fetchall()
        total = len(total_tasks)
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        tasks_result = await session.execute(query)
        tasks = tasks_result.fetchall()

        # Обновление статуса просроченных задач
        for task in tasks:
            if task.due_at and task.due_at < now and task.status != 'completed':
                await session.execute(
                    tasks_table.update()
                    .where(tasks_table.c.task_id == task.task_id)
                    .values(status='overdue')
                )
        await session.commit()
        tasks_result = await session.execute(query)  # Повторный запрос после обновления
        tasks = tasks_result.fetchall()

        # Проверка на отсутствующие роли и добавление флага is_group_task
        role_ids = {role.role_id for role in roles}
        tasks_with_flags = []
        for task in tasks:
            if task.role_id in role_ids or task.role_id == 'all':
                # Проверяем, является ли задача групповой
                is_group_task = (task.role_id == 'all' or 
                                 (task.role_id in groups and 
                                  not any(role.role_id == task.role_id and role.role_subgroup for role in roles)))
                tasks_with_flags.append((task, is_group_task))
        
        frequency_result = await session.execute(select(tasks_table.c.repeat_interval).distinct())
        frequencies = [row[0] for row in frequency_result if row[0]]

    total_pages = (total + per_page - 1) // per_page

    return await render_template(
        'tasks.html',
        tasks=tasks_with_flags,  # Передаем список кортежей (task, is_group_task)
        roles=roles,
        groups=groups,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total=total,
        status_filter=status_filter,
        deadline_filter=deadline_filter,
        executor_filter=executor_filter,
        frequency_filter=frequency_filter,
        search_query=search_query,
        frequencies=frequencies
    )

@tasks_bp.route('/add', methods=['POST'])
@login_required
async def add():
    form = await request.form
    role_id = form.get('executor')
    subgroup = form.get('subgroup')
    description = form.get('description')
    due_at_str = form.get('due_at')
    repeat_interval = form.get('repeat_interval')
    custom_repeat_value = form.get('custom_repeat_value')
    notification_type = form.get('notification_type')
    notification_enabled = form.get('notification_enabled') == 'on'

    if not description:
        await flash("Описание задачи обязательно", "danger")
        return redirect(url_for('tasks.index'))

    if subgroup and subgroup != "all":
        role_id = subgroup

    due_at = datetime.strptime(due_at_str, '%Y-%m-%dT%H:%M') if due_at_str else None

    # Обработка пользовательского интервала повторения (добавлены недели и месяцы)
    if repeat_interval and repeat_interval.startswith("custom_"):
        if custom_repeat_value:
            unit = repeat_interval.split('_')[1]
            repeat_interval = f"{custom_repeat_value} {unit}"

    task_id = await add_task(role_id, description, "sent", due_at, repeat_interval)

    # Обработка уведомлений
    if notification_enabled:
        if notification_type == "now" and notification_service:
            await notification_service.schedule_task_notification(task_id, datetime.now(), description, role_id)
        elif notification_type == "deadline" and due_at:
            await add_notification(task_id, "deadline", scheduled_time=due_at)
        elif notification_type == "custom":
            custom_type = form.get('custom_notification_type')
            if custom_type == "single":
                single_time = form.get('single_time')
                single_offset = form.get('single_offset')
                single_unit = form.get('single_unit', 'minutes')
                scheduled_time = datetime.strptime(single_time, '%Y-%m-%dT%H:%M') if single_time else None
                if single_offset and due_at and not scheduled_time:
                    delta = {
                        'minutes': timedelta(minutes=int(single_offset)),
                        'hours': timedelta(hours=int(single_offset)),
                        'days': timedelta(days=int(single_offset)),
                        'weeks': timedelta(weeks=int(single_offset)),
                        'months': timedelta(days=int(single_offset) * 30)
                    }[single_unit]
                    scheduled_time = due_at - delta
                await add_notification(task_id, "single", scheduled_time=scheduled_time)
            elif custom_type == "repeated":
                repeat_frequency = form.get('repeat_frequency')
                repeat_value = form.get('repeat_frequency_value')
                repeat_start = form.get('repeat_start')
                repeat_end = form.get('repeat_end')
                fixed_times = [form.get(f'fixed_time_{i}') for i in range(1, 10) if form.get(f'fixed_time_{i}')]
                repeat_interval = f"{repeat_value} {repeat_frequency.split('_')[1]}" if repeat_value else None
                start_time = datetime.strptime(repeat_start, '%Y-%m-%dT%H:%M') if repeat_start else None
                end_time = datetime.strptime(repeat_end, '%Y-%m-%dT%H:%M') if repeat_end else None
                await add_notification(
                    task_id, "repeated",
                    repeat_interval=repeat_interval,
                    scheduled_time=start_time,
                    end_offset=end_time,
                    fixed_times=",".join(fixed_times) if fixed_times else None
                )

    await flash("Задача успешно добавлена!", "success")
    return redirect(url_for('tasks.index'))

@tasks_bp.route('/delete/<int:task_id>', methods=['POST'])
@login_required
async def delete(task_id):
    async with async_session() as session:
        await session.execute(tasks_table.delete().where(tasks_table.c.task_id == task_id))
        await session.commit()
    await flash("Задача удалена", "success")
    return redirect(url_for('tasks.index'))

@tasks_bp.route('/update_status/<int:task_id>', methods=['POST'])
@login_required
async def update_status(task_id):
    form = await request.form
    role_id = form.get('executor')
    subgroup = form.get('subgroup')
    description = form.get('description')
    due_at_str = form.get('due_at')
    repeat_interval = form.get('repeat_interval')
    custom_repeat_value = form.get('custom_repeat_value')
    new_status = form.get('status')

    if not description:
        await flash("Описание задачи обязательно", "danger")
        return redirect(url_for('tasks.index'))

    if subgroup and subgroup != "all":
        role_id = subgroup

    due_at = datetime.strptime(due_at_str, '%Y-%m-%dT%H:%M') if due_at_str else None

    if repeat_interval and repeat_interval.startswith("custom_"):
        if custom_repeat_value:
            unit = repeat_interval.split('_')[1]
            repeat_interval = f"{custom_repeat_value} {unit}"
        else:
            repeat_interval = None

    async with async_session() as session:
        await session.execute(
            tasks_table.update()
            .where(tasks_table.c.task_id == task_id)
            .values(
                role_id=role_id,
                description=description,
                status=new_status if new_status in ["sent", "accepted", "completed"] else "sent",
                due_at=due_at,
                repeat_interval=repeat_interval
            )
        )
        await session.commit()

    await flash(f"Задача #{task_id} успешно обновлена", "success")
    return redirect(url_for('tasks.index'))

@tasks_bp.route('/get_subgroups', methods=['GET'])
@login_required
async def get_subgroups():
    group = request.args.get('group')
    if not group or group == 'all':
        return jsonify([])
    async with async_session() as session:
        result = await session.execute(
            roles_table.select().where(roles_table.c.role_group == group).where(roles_table.c.role_subgroup.isnot(None))
        )
        subgroups = result.fetchall()
    return jsonify([{"role_id": row.role_id, "role_full_name": row.role_full_name} for row in subgroups])

@tasks_bp.route('/stats/<int:task_id>', methods=['GET'])
@login_required
async def stats(task_id):
    async with async_session() as session:
        task_result = await session.execute(tasks_table.select().where(tasks_table.c.task_id == task_id))
        task = task_result.fetchone()
        if not task:
            await flash("Задача не найдена", "danger")
            return redirect(url_for('tasks.index'))
        completions = await get_task_completions(task_id)
        roles = await get_roles()  # Добавлено для отображения ролей в статистике
        return await render_template('tasks_stats.html', task=task, completions=completions, roles=roles)

@tasks_bp.route('/get_notifications', methods=['GET'])
@login_required
async def get_notifications():
    task_id = request.args.get('task_id', type=int)
    if not task_id:
        return jsonify([])
    async with async_session() as session:
        result = await session.execute(
            task_notifications_table.select().where(task_notifications_table.c.task_id == task_id)
        )
        notifications = result.fetchall()
    return jsonify([
        {
            'id': n.id,
            'type': n.type,
            'scheduled_time': n.scheduled_time.isoformat() if n.scheduled_time else None,
            'repeat_interval': n.repeat_interval,
            'status': n.status
        } for n in notifications
    ])

@tasks_bp.route('/add_notification', methods=['POST'])
@login_required
async def add_notification_route():
    data = await request.get_json()
    task_id = data.get('task_id')
    notification_type = data.get('notification_type')

    async with async_session() as session:
        task_result = await session.execute(tasks_table.select().where(tasks_table.c.task_id == task_id))
        task = task_result.fetchone()
        if not task:
            return jsonify({'success': False, 'error': 'Задача не найдена'})

        scheduled_time = None
        repeat_interval = None
        start_offset = None
        end_offset = None
        fixed_times = None

        if notification_type == 'reminder':
            if data.get('reminder_time'):
                scheduled_time = datetime.fromisoformat(data['reminder_time'])
            elif data.get('reminder_offset'):
                offset = int(data['reminder_offset'])
                unit = data.get('reminder_unit', 'minutes')
                delta = {
                    'minutes': timedelta(minutes=offset),
                    'hours': timedelta(hours=offset),
                    'days': timedelta(days=offset),
                    'weeks': timedelta(weeks=offset),
                    'months': timedelta(days=offset * 30)
                }[unit]
                scheduled_time = task.due_at - delta
        elif notification_type == 'deadline':
            scheduled_time = task.due_at
        elif notification_type == 'overdue':
            value = int(data.get('overdue_value', 0))
            unit = data.get('overdue_unit', 'hours')
            delta = {
                'minutes': timedelta(minutes=value),
                'hours': timedelta(hours=value),
                'days': timedelta(days=value),
                'weeks': timedelta(weeks=value),
                'months': timedelta(days=value * 30)
            }[unit]
            scheduled_time = task.due_at + delta
        elif notification_type == 'repeated':
            freq_value = int(data.get('repeat_frequency_value', 0))
            freq_unit = data.get('repeat_frequency_unit')
            repeat_interval = f"{freq_value} {freq_unit}"
            start_value = int(data.get('repeat_start_value', 0))
            start_unit = data.get('repeat_start_unit')
            start_delta = {
                'minutes': timedelta(minutes=start_value),
                'hours': timedelta(hours=start_value),
                'days': timedelta(days=start_value),
                'weeks': timedelta(weeks=start_value),
                'months': timedelta(days=start_value * 30)
            }[start_unit]
            scheduled_time = task.due_at - start_delta
            end_value = None
            end_unit = None
            if data.get('repeat_end') == 'after':
                end_value = int(data.get('repeat_end_value', 0))
                end_unit = data.get('repeat_end_unit')
                end_delta = {
                    'minutes': timedelta(minutes=end_value),
                    'hours': timedelta(hours=end_value),
                    'days': timedelta(days=end_value),
                    'weeks': timedelta(weeks=end_value),
                    'months': timedelta(days=end_value * 30)
                }[end_unit]
            fixed_times = ','.join(data.get('fixed_times', [])) if data.get('fixed_times') else None

            await add_notification(task_id, notification_type, scheduled_time, repeat_interval,
                                start_offset_value=start_value, start_offset_unit=start_unit,
                                end_offset_value=end_value, end_offset_unit=end_unit, fixed_times=fixed_times)
    return jsonify({'success': True})

@tasks_bp.route('/cancel_notification', methods=['POST'])
@login_required
async def cancel_notification():
    data = await request.get_json()
    task_id = data.get('task_id')
    notification_id = data.get('notification_id')

    async with async_session() as session:
        await session.execute(
            task_notifications_table.update()
            .where(task_notifications_table.c.id == notification_id)
            .where(task_notifications_table.c.task_id == task_id)
            .values(status='cancelled')
        )
        await session.commit()

    if notification_service and hasattr(notification_service, 'scheduler'):
        try:
            notification_service.scheduler.remove_job(f"task_{task_id}_notification_{notification_id}")
        except:
            logger.warning(f"Не удалось удалить задачу уведомления task_{task_id}_notification_{notification_id}")
    
    return jsonify({'success': True})