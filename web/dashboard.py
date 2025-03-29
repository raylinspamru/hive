# web/dashboard.py
from quart import Blueprint, render_template
from quart_auth import login_required

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
async def index():
    return await render_template('dashboard.html')