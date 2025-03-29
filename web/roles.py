# web/roles.py
from quart import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from quart_auth import login_required
from utils.database import async_session, roles_table, role_users_table, get_roles, get_users_by_role_id
from sqlalchemy.sql import select, update, delete
import random
import string
import logging
from web import bot_instance  # Для отправки сообщений через Telegram

logger = logging.getLogger(__name__)

roles_bp = Blueprint('roles', __name__)

@roles_bp.route('/', methods=['GET'])
@login_required
async def index():
    args = request.args
    page = int(args.get('page', 1))
    per_page = int(args.get('per_page', 25))
    group_filter = args.get('group', 'all')
    search_query = args.get('search', '')
    only_with_users = args.get('only_with_users') == 'on'

    async with async_session() as session:
        roles_query = select(roles_table)
        if group_filter != 'all':
            roles_query = roles_query.where(roles_table.c.role_group == group_filter)
        if search_query:
            roles_query = roles_query.where(roles_table.c.role_full_name.ilike(f"%{search_query}%"))
        if only_with_users:
            roles_query = roles_query.join(role_users_table, roles_table.c.role_id == role_users_table.c.role_id, isouter=False)

        roles_result = await session.execute(roles_query)
        all_roles = roles_result.fetchall()
        total = len(all_roles)
        offset = (page - 1) * per_page
        roles_query = roles_query.offset(offset).limit(per_page)
        roles_result = await session.execute(roles_query)
        roles = roles_result.fetchall()

        groups = sorted(set(role.role_group for role in all_roles if role.role_group))
        users_by_role = {role.role_id: await get_users_by_role_id(role.role_id) for role in roles}

    total_pages = (total + per_page - 1) // per_page

    return await render_template(
        'roles.html',
        roles=roles,
        users_by_role=users_by_role,
        groups=groups,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        group_filter=group_filter,
        search_query=search_query,
        only_with_users=only_with_users
    )

@roles_bp.route('/add', methods=['POST'])
@login_required
async def add_role():
    form = await request.form
    role_id = form.get('role_id')
    role_full_name = form.get('role_full_name')
    role_group = form.get('role_group') or None
    role_subgroup = form.get('role_subgroup') or None
    rolepass = form.get('rolepass') or ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))

    if not role_id or not role_full_name or not all(c in (string.ascii_letters + string.digits) for c in role_id):
        await flash("Некорректный ID роли или полное название", "danger")
        return redirect(url_for('roles.index'))

    async with async_session() as session:
        existing_role = await session.execute(roles_table.select().where(roles_table.c.role_id == role_id))
        if existing_role.fetchone():
            await flash("Роль с таким ID уже существует", "danger")
            return redirect(url_for('roles.index'))

        await session.execute(
            roles_table.insert().values(
                role_id=role_id,
                role_full_name=role_full_name,
                role_group=role_group,
                role_subgroup=role_subgroup,
                rolepass=rolepass
            )
        )
        await session.commit()

    await flash("Роль успешно добавлена", "success")
    return redirect(url_for('roles.index'))

@roles_bp.route('/update', methods=['POST'])
@login_required
async def update_role():
    data = await request.get_json()
    role_id = data.get('role_id')
    updates = {k: v for k, v in data.items() if k != 'role_id' and v is not None}

    if not role_id or not updates:
        return jsonify({'success': False, 'error': 'Нет данных для обновления'})

    async with async_session() as session:
        await session.execute(
            roles_table.update()
            .where(roles_table.c.role_id == role_id)
            .values(**updates)
        )
        await session.commit()

    return jsonify({'success': True})



@roles_bp.route('/delete/<role_id>', methods=['POST'])
@login_required
async def delete_role(role_id):
    async with async_session() as session:
        await session.execute(role_users_table.delete().where(role_users_table.c.role_id == role_id))
        await session.execute(roles_table.delete().where(roles_table.c.role_id == role_id))
        await session.commit()
    await flash("Роль удалена", "success")
    return redirect(url_for('roles.index'))

@roles_bp.route('/add_user', methods=['POST'])
@login_required
async def add_user():
    data = await request.get_json()
    role_id = data.get('role_id')
    user_id = data.get('user_id')
    user_name = data.get('user_name') or None

    if not role_id or not user_id or not user_id.isdigit():
        return jsonify({'success': False, 'error': 'Некорректный Telegram ID'})

    async with async_session() as session:
        role = (await session.execute(roles_table.select().where(roles_table.c.role_id == role_id))).fetchone()
        if not role:
            return jsonify({'success': False, 'error': 'Роль не найдена'})

        existing_user = (await session.execute(
            role_users_table.select()
            .where(role_users_table.c.role_id == role_id)
            .where(role_users_table.c.user_id == user_id)
        )).fetchone()
        if existing_user:
            return jsonify({'success': False, 'error': 'Пользователь уже привязан'})

        await session.execute(
            role_users_table.insert().values(role_id=role_id, user_id=user_id, user_name=user_name)
        )
        await session.commit()

        if bot_instance:
            try:
                await bot_instance.send_message(
                    user_id,
                    f"Вы привязаны к роли '{role.role_full_name}'. Пароль: {role.rolepass}\n"
                    f"Для входа в бот используйте команду /start и введите этот пароль."
                )
                logger.info(f"Сообщение отправлено пользователю {user_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
                return jsonify({'success': True, 'warning': 'Пользователь добавлен, но сообщение не отправлено'})

    return jsonify({'success': True})

@roles_bp.route('/delete_user', methods=['POST'])
@login_required
async def delete_user():
    data = await request.get_json()
    role_id = data.get('role_id')
    user_id = data.get('user_id')

    async with async_session() as session:
        await session.execute(
            role_users_table.delete()
            .where(role_users_table.c.role_id == role_id)
            .where(role_users_table.c.user_id == user_id)
        )
        await session.commit()

    return jsonify({'success': True})

@roles_bp.route('/regenerate_password/<role_id>', methods=['POST'])
@login_required
async def regenerate_password(role_id):
    new_password = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
    async with async_session() as session:
        # Получаем текущих пользователей роли
        users = await get_users_by_role_id(role_id)
        role = (await session.execute(roles_table.select().where(roles_table.c.role_id == role_id))).fetchone()

        # Удаляем привязанных пользователей
        await session.execute(role_users_table.delete().where(role_users_table.c.role_id == role_id))
        # Обновляем пароль
        await session.execute(
            roles_table.update()
            .where(roles_table.c.role_id == role_id)
            .values(rolepass=new_password)
        )
        await session.commit()

        # Уведомляем пользователей о сбросе
        if bot_instance and users:
            for user in users:
                try:
                    await bot_instance.send_message(
                        user.user_id,
                        f"Пароль для роли '{role.role_full_name}' был обновлён. Новый пароль: {new_password}\n"
                        f"Все пользователи отвязаны. Для повторной привязки обратитесь к администратору."
                    )
                    logger.info(f"Сообщение отправлено пользователю {user.user_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки сообщения пользователю {user.user_id}: {e}")

    await flash("Пароль обновлён, пользователи отвязаны и уведомлены", "success")
    return redirect(url_for('roles.index'))

@roles_bp.route('/send_password/<role_id>', methods=['POST'])
@login_required
async def send_password(role_id):
    async with async_session() as session:
        role = (await session.execute(roles_table.select().where(roles_table.c.role_id == role_id))).fetchone()
        users = await get_users_by_role_id(role_id)

    if not role or not users or not bot_instance:
        await flash("Ошибка: роль не найдена, нет пользователей или бот не инициализирован", "danger")
        return redirect(url_for('roles.index'))

    for user in users:
        try:
            await bot_instance.send_message(user.user_id, f"Пароль для роли '{role.role_full_name}': {role.rolepass}")
            logger.info(f"Пароль отправлен пользователю {user.user_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки пароля пользователю {user.user_id}: {e}")

    await flash("Пароль отправлен всем пользователям роли", "success")
    return redirect(url_for('roles.index'))

@roles_bp.route('/add_from_table', methods=['POST'])
@login_required
async def add_from_table():
    data = await request.get_json()
    role_id = data.get('role_id')
    role_full_name = data.get('role_full_name')
    role_group = data.get('role_group') or None
    role_subgroup = data.get('role_subgroup') or None
    rolepass = data.get('rolepass') or ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))

    if not role_id or not role_full_name or not all(c in (string.ascii_letters + string.digits) for c in role_id):
        return jsonify({'success': False, 'error': 'Некорректный ID роли или полное название'})

    async with async_session() as session:
        existing_role = await session.execute(roles_table.select().where(roles_table.c.role_id == role_id))
        if existing_role.fetchone():
            return jsonify({'success': False, 'error': 'Роль с таким ID уже существует'})

        await session.execute(
            roles_table.insert().values(
                role_id=role_id,
                role_full_name=role_full_name,
                role_group=role_group,
                role_subgroup=role_subgroup,
                rolepass=rolepass
            )
        )
        await session.commit()

    return jsonify({'success': True})