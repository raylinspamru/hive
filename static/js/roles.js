// static/js/roles.js
document.addEventListener('DOMContentLoaded', () => {
    let editMode = false;

    // Инициализация всплывающих подсказок Bootstrap
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    const toggleEditButton = document.getElementById('toggle-edit-mode');
    const saveChangesButton = document.getElementById('save-changes');
    const addRowButton = document.getElementById('add-row-btn');
    const table = document.querySelector('.table');

    // Переключение режима редактирования
    toggleEditButton.addEventListener('click', () => {
        editMode = !editMode;
        toggleEditButton.textContent = editMode ? 'Выключить редактирование' : 'Включить редактирование';
        toggleEditButton.classList.toggle('btn-primary', !editMode);
        toggleEditButton.classList.toggle('btn-warning', editMode);
        saveChangesButton.style.display = editMode ? 'inline-block' : 'none';
        addRowButton.style.display = editMode ? 'inline-block' : 'none';
        document.querySelectorAll('.delete-row-btn').forEach(btn => {
            btn.style.display = editMode ? 'inline-block' : 'none';
        });
        table.classList.toggle('table-editable', editMode); // Визуальная индикация

        if (!editMode) {
            // При выключении режима возвращаем все ячейки в текстовый вид
            document.querySelectorAll('.editable').forEach(cell => {
                const input = cell.querySelector('input');
                if (input) {
                    saveCell(cell, cell.dataset.field, input.value, cell.dataset.originalText || '-');
                }
            });
        }
    });

    // Редактирование ячеек по клику
    document.querySelectorAll('.editable').forEach(cell => {
        cell.addEventListener('click', function() {
            if (!editMode || this.querySelector('input')) return;
            const originalText = this.textContent.trim();
            this.dataset.originalText = originalText;
            const field = this.dataset.field;
            const input = document.createElement('input');
            input.type = 'text';
            input.value = originalText === '-' ? '' : originalText;
            input.className = 'form-control form-control-sm';
            if (field === 'role_id') input.pattern = '[a-zA-Z0-9]+';
            this.textContent = '';
            this.appendChild(input);
            input.focus();

            input.addEventListener('blur', () => saveCell(this, field, input.value, originalText));
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') saveCell(this, field, input.value, originalText);
            });
        });
    });

    // Удаление пользователя
    document.querySelectorAll('.delete-user').forEach(button => {
        button.addEventListener('click', () => {
            const roleId = button.closest('tr').dataset.roleId;
            const userId = button.dataset.userId;
            if (confirm('Удалить пользователя из роли?')) {
                fetch('/roles/delete_user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ role_id: roleId, user_id: userId })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) location.reload();
                    else alert('Ошибка удаления пользователя');
                });
            }
        });
    });

    // Сохранение изменений
    saveChangesButton.addEventListener('click', () => {
        const updates = [];
        const newRoles = [];
        document.querySelectorAll('tr[data-role-id]').forEach(row => {
            const roleId = row.dataset.roleId;
            const updatedFields = {};
            row.querySelectorAll('.editable').forEach(cell => {
                const input = cell.querySelector('input');
                updatedFields[cell.dataset.field] = input ? input.value || null : cell.textContent === '-' ? null : cell.textContent;
            });
            if (Object.keys(updatedFields).length) {
                if (roleId.startsWith('new_')) {
                    newRoles.push(updatedFields);
                } else {
                    updates.push({ role_id: roleId, ...updatedFields });
                }
            }
        });

        saveChangesButton.disabled = true;
        saveChangesButton.textContent = 'Сохранение...';

        // Обновление существующих ролей
        Promise.all(updates.map(update =>
            fetch('/roles/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(update)
            }).then(response => response.json())
        )).then(results => {
            const allSuccess = results.every(r => r.success);
            if (!allSuccess) {
                alert('Ошибка сохранения изменений в существующих ролях');
            }
            return Promise.all(newRoles.map(newRole =>
                fetch('/roles/add_from_table', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(newRole)
                }).then(response => response.json())
            ));
        }).then(results => {
            const allSuccess = results.every(r => r.success);
            if (allSuccess) {
                saveChangesButton.textContent = 'Сохранено!';
                setTimeout(() => {
                    saveChangesButton.textContent = 'Сохранить изменения';
                    saveChangesButton.disabled = false;
                    location.reload();
                }, 1000);
            } else {
                alert('Ошибка добавления новых ролей');
                saveChangesButton.disabled = false;
                saveChangesButton.textContent = 'Сохранить изменения';
            }
        }).catch(() => {
            alert('Ошибка при сохранении');
            saveChangesButton.disabled = false;
            saveChangesButton.textContent = 'Сохранить изменения';
        });
    });

    // Пагинация
    document.getElementById('per_page').addEventListener('change', function() {
        const baseUrl = this.dataset.baseUrl;
        window.location.href = `${baseUrl}&per_page=${this.value}`;
    });

    // Удаление строки
    document.querySelectorAll('.delete-row-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const row = btn.closest('tr');
            const roleId = row.dataset.roleId;
            if (roleId.startsWith('new_')) {
                if (confirm('Удалить новую роль?')) {
                    row.remove();
                }
            } else {
                if (confirm('Удалить роль?')) {
                    fetch(`/roles/delete/${roleId}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    }).then(response => {
                        if (response.ok) location.reload();
                        else alert('Ошибка удаления роли');
                    });
                }
            }
        });
    });

    // Добавление новой строки
    addRowButton.addEventListener('click', () => {
        const tbody = document.querySelector('tbody');
        const newRow = document.createElement('tr');
        newRow.dataset.roleId = 'new_' + Date.now();
        newRow.innerHTML = `
            <td>-</td>
            <td class="editable" data-field="role_id">-</td>
            <td class="editable" data-field="role_full_name">-</td>
            <td class="editable" data-field="role_group">-</td>
            <td class="editable" data-field="role_subgroup">-</td>
            <td class="editable" data-field="rolepass">-</td>
            <td>-</td>
            <td>
                <button class="btn btn-sm btn-danger delete-row-btn" style="display: inline-block;" data-bs-toggle="tooltip" title="Удалить роль"><i class="fas fa-trash"></i></button>
            </td>
        `;
        tbody.appendChild(newRow);
        newRow.querySelectorAll('.editable').forEach(cell => {
            cell.addEventListener('click', function() {
                if (!editMode || this.querySelector('input')) return;
                const originalText = this.textContent.trim();
                this.dataset.originalText = originalText;
                const field = this.dataset.field;
                const input = document.createElement('input');
                input.type = 'text';
                input.value = originalText === '-' ? '' : originalText;
                input.className = 'form-control form-control-sm';
                if (field === 'role_id') input.pattern = '[a-zA-Z0-9]+';
                this.textContent = '';
                this.appendChild(input);
                input.focus();

                input.addEventListener('blur', () => saveCell(this, field, input.value, originalText));
                input.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') saveCell(this, field, input.value, originalText);
                });
            });
        });
        newRow.querySelector('.delete-row-btn').addEventListener('click', () => {
            if (confirm('Удалить новую роль?')) {
                newRow.remove();
            }
        });
        new bootstrap.Tooltip(newRow.querySelector('.delete-row-btn'));
    });
});

function saveCell(cell, field, value, originalText) {
    if (field === 'role_id' && value && !/^[a-zA-Z0-9]+$/.test(value)) {
        alert('ID роли должен содержать только буквы и цифры');
        cell.textContent = originalText;
        return;
    }
    if (field === 'role_full_name' && !value) {
        alert('Полное название не может быть пустым');
        cell.textContent = originalText;
        return;
    }
    cell.textContent = value || '-';
}

function addUser(roleId) {
    const userId = document.getElementById(`user_id_${roleId}`).value;
    const userName = document.getElementById(`user_name_${roleId}`).value;
    if (!/^\d+$/.test(userId)) {
        alert('Telegram ID должен содержать только цифры');
        return;
    }

    fetch('/roles/add_user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_id: roleId, user_id: userId, user_name: userName })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById(`addUserModal${roleId}`).querySelector('.btn-close').click();
            location.reload();
        } else {
            alert(data.error || 'Ошибка добавления пользователя');
        }
    });
}

function goToPage() {
    const pageInput = document.getElementById('page_input');
    const page = pageInput.value;
    if (page && !isNaN(page)) {
        const baseUrl = document.getElementById('per_page').dataset.baseUrl;
        window.location.href = `${baseUrl}&page=${page}`;
    }
}

function editRole(roleId) {
    const row = document.querySelector(`tr[data-role-id="${roleId}"]`);
    document.getElementById('edit_role_id').value = row.querySelector('[data-field="role_id"]').textContent;
    document.getElementById('edit_role_full_name').value = row.querySelector('[data-field="role_full_name"]').textContent;
    document.getElementById('edit_role_group').value = row.querySelector('[data-field="role_group"]').textContent === '-' ? '' : row.querySelector('[data-field="role_group"]').textContent;
    document.getElementById('edit_role_subgroup').value = row.querySelector('[data-field="role_subgroup"]').textContent === '-' ? '' : row.querySelector('[data-field="role_subgroup"]').textContent;
    document.getElementById('edit_rolepass').value = row.querySelector('[data-field="rolepass"]').textContent;
    document.getElementById('edit-role-form').dataset.roleId = roleId;
}

function saveEditedRole() {
    const form = document.getElementById('edit-role-form');
    const roleId = form.dataset.roleId;
    const data = {
        role_id: document.getElementById('edit_role_id').value,
        role_full_name: document.getElementById('edit_role_full_name').value,
        role_group: document.getElementById('edit_role_group').value || null,
        role_subgroup: document.getElementById('edit_role_subgroup').value || null,
        rolepass: document.getElementById('edit_rolepass').value
    };

    fetch('/roles/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            location.reload();
        } else {
            alert('Ошибка сохранения роли');
        }
    });
}