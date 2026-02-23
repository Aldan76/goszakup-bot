"""
Admin Panel для управления Goszakup Bot
Веб-интерфейс для администраторов с контролем всех функций бота
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime, timedelta
from functools import wraps
import os
import json
import logging
from dotenv import load_dotenv

# Импорты из проекта
from admin_db import AdminDB
from admin_config import ADMIN_CONFIG, ADMIN_USERS

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
CORS(app)

# Инициализируем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализируем БД для админ панели
db = AdminDB()

# ─── Decorators ───────────────────────────────────────────────────────────

def login_required(f):
    """Проверка что админ залогирован"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Проверка что это администратор"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_id" not in session:
            return jsonify({"error": "Не авторизован"}), 401
        return f(*args, **kwargs)
    return decorated_function


# ─── Authentication Routes ────────────────────────────────────────────────

@app.route("/")
def index():
    """Главная страница - редирект на логин или панель"""
    if "admin_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Страница входа"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # Проверяем учетные данные
        for admin_user in ADMIN_USERS:
            if admin_user["username"] == username and admin_user["password"] == password:
                session["admin_id"] = admin_user["id"]
                session["admin_name"] = admin_user["name"]
                session["admin_role"] = admin_user["role"]
                db.log_admin_action(
                    admin_id=admin_user["id"],
                    action="LOGIN",
                    details=f"Admin {admin_user['name']} logged in"
                )
                return redirect(url_for("dashboard"))

        return render_template("login.html", error="Неверные учетные данные")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Выход из системы"""
    if "admin_id" in session:
        db.log_admin_action(
            admin_id=session["admin_id"],
            action="LOGOUT",
            details=f"Admin {session.get('admin_name', 'Unknown')} logged out"
        )
    session.clear()
    return redirect(url_for("login"))


# ─── Dashboard Routes ─────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    """Главная панель администратора"""
    stats = db.get_dashboard_stats()
    return render_template("dashboard.html", stats=stats, admin_name=session.get("admin_name"))


@app.route("/api/stats")
@admin_required
def api_stats():
    """API для получения статистики"""
    stats = db.get_dashboard_stats()
    return jsonify(stats)


# ─── Users Management Routes ──────────────────────────────────────────────

@app.route("/users")
@login_required
def users():
    """Страница управления пользователями"""
    return render_template("users.html", admin_name=session.get("admin_name"))


@app.route("/api/users")
@admin_required
def api_users_list():
    """API: Получить список пользователей"""
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 50, type=int)
    search = request.args.get("search", "", type=str)

    users_data = db.get_users(page=page, limit=limit, search=search)
    return jsonify(users_data)


@app.route("/api/users/<int:user_id>")
@admin_required
def api_user_details(user_id):
    """API: Получить детали пользователя"""
    user = db.get_user(user_id)
    if not user:
        return jsonify({"error": "Пользователь не найден"}), 404
    return jsonify(user)


@app.route("/api/users/<int:user_id>/ban", methods=["POST"])
@admin_required
def api_ban_user(user_id):
    """API: Забанить пользователя"""
    reason = request.json.get("reason", "No reason provided")

    result = db.ban_user(user_id, reason=reason)
    db.log_admin_action(
        admin_id=session["admin_id"],
        action="BAN_USER",
        details=f"Banned user {user_id}. Reason: {reason}"
    )
    return jsonify(result)


@app.route("/api/users/<int:user_id>/unban", methods=["POST"])
@admin_required
def api_unban_user(user_id):
    """API: Разбанить пользователя"""
    reason = request.json.get("reason", "No reason provided")

    result = db.unban_user(user_id, reason=reason)
    db.log_admin_action(
        admin_id=session["admin_id"],
        action="UNBAN_USER",
        details=f"Unbanned user {user_id}. Reason: {reason}"
    )
    return jsonify(result)


@app.route("/api/users/<int:user_id>/notes", methods=["POST"])
@admin_required
def api_user_notes(user_id):
    """API: Добавить заметку о пользователе"""
    notes = request.json.get("notes", "")

    result = db.update_user_notes(user_id, notes=notes)
    db.log_admin_action(
        admin_id=session["admin_id"],
        action="UPDATE_NOTES",
        details=f"Updated notes for user {user_id}"
    )
    return jsonify(result)


# ─── Logs Routes ──────────────────────────────────────────────────────────

@app.route("/logs")
@login_required
def logs():
    """Страница просмотра логов"""
    return render_template("logs.html", admin_name=session.get("admin_name"))


@app.route("/api/logs")
@admin_required
def api_logs():
    """API: Получить логи"""
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 100, type=int)
    log_type = request.args.get("type", "all", type=str)

    logs_data = db.get_logs(page=page, limit=limit, log_type=log_type)
    return jsonify(logs_data)


@app.route("/messages")
@login_required
def messages():
    """Страница просмотра всех сообщений пользователей"""
    return render_template("messages.html", admin_name=session.get("admin_name"))


@app.route("/api/logs/conversations")
@admin_required
def api_conversations_logs():
    """API: Получить логи разговоров"""
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 50, type=int)
    user_id = request.args.get("user_id", None, type=int)

    logs_data = db.get_conversation_logs(page=page, limit=limit, user_id=user_id)
    return jsonify(logs_data)


@app.route("/api/messages")
@admin_required
def api_messages():
    """API: Получить все сообщения (переписку)"""
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 100, type=int)
    user_id = request.args.get("user_id", None, type=int)

    try:
        if not db.supabase:
            return jsonify({"error": "Supabase not connected"}), 500

        query = db.supabase.table("conversations")

        # Фильтр по пользователю если указан
        if user_id:
            query = query.eq("chat_id", user_id)

        # Сортировка по дате (новые сверху)
        query = query.order("created_at", desc=True)

        # Пагинация
        start = (page - 1) * limit
        result = query.range(start, start + limit - 1).execute()

        # Получить общее количество
        count_result = db.supabase.table("conversations").select("id", count="exact").execute()
        total = count_result.count if hasattr(count_result, 'count') else 0

        return jsonify({
            "messages": result.data,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        })
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        return jsonify({"error": str(e)}), 500


# ─── FAQ Management Routes ────────────────────────────────────────────────

@app.route("/faq")
@login_required
def faq():
    """Страница управления FAQ"""
    return render_template("faq.html", admin_name=session.get("admin_name"))


@app.route("/api/faq")
@admin_required
def api_faq_list():
    """API: Получить список FAQ"""
    faq_list = db.get_faq()
    return jsonify(faq_list)


@app.route("/api/faq", methods=["POST"])
@admin_required
def api_faq_create():
    """API: Создать новый FAQ"""
    data = request.json

    if not data.get("question") or not data.get("answer"):
        return jsonify({"error": "Question and answer required"}), 400

    result = db.create_faq(
        question=data["question"],
        answer=data["answer"],
        tags=data.get("tags", [])
    )
    db.log_admin_action(
        admin_id=session["admin_id"],
        action="CREATE_FAQ",
        details=f"Created FAQ: {data['question'][:50]}..."
    )
    return jsonify(result), 201


@app.route("/api/faq/<int:faq_id>", methods=["PUT"])
@admin_required
def api_faq_update(faq_id):
    """API: Обновить FAQ"""
    data = request.json

    result = db.update_faq(
        faq_id=faq_id,
        question=data.get("question"),
        answer=data.get("answer"),
        tags=data.get("tags")
    )
    db.log_admin_action(
        admin_id=session["admin_id"],
        action="UPDATE_FAQ",
        details=f"Updated FAQ {faq_id}"
    )
    return jsonify(result)


@app.route("/api/faq/<int:faq_id>", methods=["DELETE"])
@admin_required
def api_faq_delete(faq_id):
    """API: Удалить FAQ"""
    result = db.delete_faq(faq_id)
    db.log_admin_action(
        admin_id=session["admin_id"],
        action="DELETE_FAQ",
        details=f"Deleted FAQ {faq_id}"
    )
    return jsonify(result)


# ─── Settings Routes ─────────────────────────────────────────────────────

@app.route("/settings")
@login_required
def settings():
    """Страница настроек"""
    return render_template("settings.html", admin_name=session.get("admin_name"))


@app.route("/api/settings")
@admin_required
def api_settings():
    """API: Получить настройки"""
    settings = db.get_settings()
    return jsonify(settings)


@app.route("/api/settings", methods=["POST"])
@admin_required
def api_settings_update():
    """API: Обновить настройки"""
    data = request.json

    result = db.update_settings(data)
    db.log_admin_action(
        admin_id=session["admin_id"],
        action="UPDATE_SETTINGS",
        details=f"Updated settings"
    )
    return jsonify(result)


# ─── Reports Routes ──────────────────────────────────────────────────────

@app.route("/reports")
@login_required
def reports():
    """Страница отчетов"""
    return render_template("reports.html", admin_name=session.get("admin_name"))


@app.route("/api/reports/summary")
@admin_required
def api_report_summary():
    """API: Получить сводный отчет"""
    days = request.args.get("days", 30, type=int)

    report = db.get_report_summary(days=days)
    return jsonify(report)


@app.route("/api/reports/platform")
@admin_required
def api_report_platform():
    """API: Отчет по платформам"""
    days = request.args.get("days", 30, type=int)

    report = db.get_platform_report(days=days)
    return jsonify(report)


@app.route("/api/reports/topics")
@admin_required
def api_report_topics():
    """API: Отчет по темам"""
    days = request.args.get("days", 30, type=int)

    report = db.get_topics_report(days=days)
    return jsonify(report)


# ─── Error Handlers ──────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(error):
    """404 обработчик"""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """500 обработчик"""
    return jsonify({"error": "Internal server error"}), 500


# ─── Запуск приложения ───────────────────────────────────────────────────

if __name__ == "__main__":
    # Создаем папку templates если её нет
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)

    # Запускаем Flask приложение
    debug = os.getenv("FLASK_DEBUG", "False") == "True"
    port = int(os.getenv("ADMIN_PORT", 5000))

    print(f"Admin Panel запущена на http://localhost:{port}")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug,
        use_reloader=debug
    )
