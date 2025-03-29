#web/__init__.py
from quart import Quart, render_template, request, redirect, url_for, session, flash
from quart_auth import QuartAuth, AuthUser, login_required, login_user, logout_user
from config import settings
from utils.database import async_session, engine as async_engine
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание приложения Quart
app = Quart(__name__, template_folder="../templates")
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Замените на безопасный ключ в продакшене
auth = QuartAuth(app)

# Переменные для интеграции с ботом и уведомлениями
notification_service = None
bot_instance = None

def set_notification_service(service):
    """Функция для передачи сервиса уведомлений из main.py"""
    global notification_service
    notification_service = service

def set_bot(bot):
    """Функция для передачи экземпляра бота из main.py"""
    global bot_instance
    bot_instance = bot

# Главный маршрут (перенаправляет на авторизацию или dashboard)
@app.route('/')
async def index():
    return redirect(url_for('dashboard.index'))  # @login_required сам проверит авторизацию

# Маршрут для страницы входа
@app.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        form = await request.form
        login = form.get('login')
        password = form.get('password')

        if login == settings.DIRECTOR_LOGIN and password == settings.DIRECTOR_PASSWORD:
            user = AuthUser("director")
            login_user(user)
            logger.info(f"Успешная авторизация для пользователя {login}")
            return redirect(url_for('dashboard.index'))
        else:
            await flash("Неверный логин или пароль", "danger")
            logger.warning(f"Неудачная попытка входа: логин={login}")
    
    return await render_template('login.html')

# Маршрут для выхода
@app.route('/logout')
@login_required
async def logout():
    logout_user()
    logger.info("Пользователь вышел из системы")
    return redirect(url_for('login'))

# Регистрация blueprints
from .dashboard import dashboard_bp
from .tasks import tasks_bp
from .roles import roles_bp
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(tasks_bp, url_prefix='/tasks')
app.register_blueprint(roles_bp, url_prefix='/roles')

# Заглушки для будущих модулей (раскомментировать при реализации)
# from .dynmenu import dynmenu_bp
# from .messages import messages_bp
# app.register_blueprint(dynmenu_bp, url_prefix='/dynmenu')
# app.register_blueprint(messages_bp, url_prefix='/messages')

# Закрытие соединения с базой данных
@app.after_request
async def close_db(response):
    await async_engine.dispose()
    return response

if __name__ == "__main__":
    app.run(host='localhost', port=5000, debug=True)