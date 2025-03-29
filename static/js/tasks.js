function setToday() {
    const now = new Date().toISOString().slice(0, 16);
    document.getElementById("due_at").value = now;
}

function setTomorrow() {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    document.getElementById("due_at").value = tomorrow.toISOString().slice(0, 16);
}

function setWeek() {
    const week = new Date();
    week.setDate(week.getDate() + 7);
    document.getElementById("due_at").value = week.toISOString().slice(0, 16);
}

function toggleCustomRepeat(select) {
    const customInput = document.getElementById("custom_repeat_container");
    customInput.style.display = select.value.startsWith("custom_") ? "block" : "none";
}

function toggleNotificationBlock(checkbox) {
    const notificationBlock = document.getElementById("notification_settings");
    notificationBlock.style.display = checkbox.checked ? "block" : "none";
}

function toggleNotificationOptions(select, taskId) {
    const options = {
        'now': 'custom-notification-options',
        'deadline': 'custom-notification-options',
        'custom': 'custom-notification-options',
        'reminder': `reminder-options-${taskId}`,
        'deadline': `deadline-options-${taskId}`,
        'overdue': `overdue-options-${taskId}`,
        'repeated': `repeated-options-${taskId}`
    };
    for (let key in options) {
        const element = document.getElementById(options[key]);
        if (element) element.style.display = (select.value === key || (select.value === 'custom' && key === 'custom-notification-options')) ? 'block' : 'none';
    }
    if (select.value === 'custom') toggleCustomNotification(document.querySelector('#custom_notification_type'));
    if (select.value === 'repeated') {
        const endSelect = document.querySelector(`#add-notification-form-${taskId} [name="repeat_end"]`);
        toggleRepeatEndOptions(endSelect, taskId);
    }
}

function toggleCustomNotification(select) {
    document.getElementById('single_notification').style.display = select.value === 'single' ? 'block' : 'none';
    document.getElementById('repeated_notification').style.display = select.value === 'repeated' ? 'block' : 'none';
}

function loadSubgroups(select) {
    const group = select.value;
    const subgroupContainer = document.getElementById("subgroup-container");
    const subgroupSelect = document.getElementById("subgroup");

    subgroupSelect.innerHTML = "";
    if (group && group !== 'all') {
        subgroupContainer.style.display = "block";
        subgroupSelect.innerHTML = '<option value="">Всем в этой группе</option>';
        fetch(`/tasks/get_subgroups?group=${encodeURIComponent(group)}`)
            .then(response => response.json())
            .then(data => {
                data.forEach(role => {
                    const option = document.createElement("option");
                    option.value = role.role_id;
                    option.text = role.role_full_name;
                    subgroupSelect.appendChild(option);
                });
            })
            .catch(error => console.error("Ошибка загрузки подгрупп:", error));
    } else {
        subgroupContainer.style.display = "none";
    }
}

function goToPage() {
    const pageInput = document.getElementById("page_input");
    const page = pageInput.value;
    if (page && !isNaN(page)) {
        const baseUrl = document.getElementById("per_page").getAttribute("data-base-url");
        window.location.href = `${baseUrl}&page=${page}`;
    }
}

document.getElementById("per_page").addEventListener("change", function() {
    const baseUrl = this.getAttribute("data-base-url");
    const perPage = this.value;
    window.location.href = `${baseUrl}&per_page=${perPage}`;
});

function toggleRepeatEndOptions(select, taskId) {
    const valueInput = document.querySelector(`#add-notification-form-${taskId} [name="repeat_end_value"]`);
    const unitSelect = document.querySelector(`#add-notification-form-${taskId} [name="repeat_end_unit"]`);
    if (select.value === 'after') {
        valueInput.style.display = 'block';
        unitSelect.style.display = 'block';
    } else {
        valueInput.style.display = 'none';
        unitSelect.style.display = 'none';
    }
}

function toggleFixedTimes(checkbox, taskId) {
    document.getElementById(`fixed_times_container_${taskId}`).style.display = checkbox.checked ? 'block' : 'none';
}

function addFixedTime(taskId) {
    const container = document.getElementById(`fixed_times_container_${taskId}`);
    const newInput = document.createElement("input");
    newInput.type = "time";
    newInput.name = `fixed_time_${container.children.length + 1}`;
    newInput.className = "form-control mb-2";
    container.insertBefore(newInput, container.lastElementChild);
}

function loadNotifications(taskId) {
    fetch(`/tasks/get_notifications?task_id=${taskId}`)
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById(`notifications-table-${taskId}`);
            tbody.innerHTML = '';
            data.forEach(notif => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${notif.type}</td>
                    <td>${notif.scheduled_time ? new Date(notif.scheduled_time).toLocaleString('ru-RU') : notif.repeat_interval || 'Сразу'}</td>
                    <td class="${notif.status === 'scheduled' ? 'bg-secondary' : notif.status === 'sent' ? 'bg-success' : 'bg-danger'}">${notif.status}</td>
                    <td>${notif.status === 'scheduled' ? `<button class="btn btn-sm btn-danger" onclick="cancelNotification(${taskId}, ${notif.id})">Отменить</button>` : '-'}</td>
                `;
                tbody.appendChild(row);
            });
        })
        .catch(error => console.error('Ошибка загрузки уведомлений:', error));
}

function cancelNotification(taskId, notificationId) {
    if (confirm('Вы уверены, что хотите отменить это уведомление?')) {
        fetch(`/tasks/cancel_notification`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: taskId, notification_id: notificationId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                loadNotifications(taskId);
            } else {
                alert('Ошибка при отмене уведомления');
            }
        })
        .catch(error => console.error('Ошибка:', error));
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const repeatSelect = document.getElementById('repeat_interval');
    if (repeatSelect) {
        toggleCustomRepeat(repeatSelect);
        repeatSelect.addEventListener('change', () => toggleCustomRepeat(repeatSelect));
    }

    const notificationCheckbox = document.getElementById('notification_enabled');
    if (notificationCheckbox) {
        toggleNotificationBlock(notificationCheckbox);
        notificationCheckbox.addEventListener('change', () => toggleNotificationBlock(notificationCheckbox));
    }

    const groupSelect = document.getElementById('executor_group');
    if (groupSelect) {
        loadSubgroups(groupSelect);
        groupSelect.addEventListener('change', () => loadSubgroups(groupSelect));
    }

    document.querySelectorAll('[id^="editTaskModal"]').forEach(modal => {
        modal.addEventListener('shown.bs.modal', () => {
            const taskId = modal.id.replace('editTaskModal', '');
            const groupSelect = document.getElementById(`executor_group_${taskId}`);
            loadSubgroups(groupSelect); // Загружаем подгруппы при открытии
        });
    });

    document.querySelectorAll('[id^="add-notification-form-"]').forEach(form => {
        const taskId = form.id.split('-')[3];
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(form);
            const data = {
                task_id: taskId,
                notification_type: formData.get('notification_type')
            };

            if (data.notification_type === 'reminder') {
                data.reminder_time = formData.get('reminder_time');
                data.reminder_offset = formData.get('reminder_offset');
                data.reminder_unit = formData.get('reminder_unit');
            } else if (data.notification_type === 'overdue') {
                data.overdue_value = formData.get('overdue_value');
                data.overdue_unit = formData.get('overdue_unit');
            } else if (data.notification_type === 'repeated') {
                data.repeat_frequency_value = formData.get('repeat_frequency_value');
                data.repeat_frequency_unit = formData.get('repeat_frequency_unit');
                data.repeat_start_value = formData.get('repeat_start_value');
                data.repeat_start_unit = formData.get('repeat_start_unit');
                data.repeat_end = formData.get('repeat_end');
                data.repeat_end_value = formData.get('repeat_end_value');
                data.repeat_end_unit = formData.get('repeat_end_unit');
                data.fixed_times = formData.get('fixed_times') ? Array.from(formData.entries())
                    .filter(([key]) => key.startsWith('fixed_time_'))
                    .map(([, value]) => value)
                    .filter(v => v) : [];
            }

            fetch(`/tasks/add_notification`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    loadNotifications(taskId);
                    form.reset();
                    toggleNotificationOptions(document.getElementById(`notification_type_${taskId}`), taskId);
                } else {
                    alert('Ошибка при добавлении уведомления');
                }
            })
            .catch(error => console.error('Ошибка:', error));
        });

        const modal = document.getElementById(`notifyModal${taskId}`);
        modal.addEventListener('shown.bs.modal', () => loadNotifications(taskId));
    });
});