"""
bot.py — Telegram-бот консультант по госзакупкам РК.

Запуск:
    python bot.py

Переменные окружения (.env):
    TELEGRAM_TOKEN      — токен от BotFather
    ANTHROPIC_API_KEY   — ключ Claude API
    SUPABASE_URL        — URL Supabase проекта
    SUPABASE_KEY        — anon/public ключ Supabase
"""

import os
import logging
import time
from collections import defaultdict, deque
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import Conflict
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv
from rag import answer_question, supabase

load_dotenv()

# ─── Логирование ──────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Конвертер Markdown → HTML (для Telegram) ────────────────────────────────

def md_to_html(text: str) -> str:
    """
    Конвертирует базовый Markdown (который генерирует Claude) в Telegram HTML.
    Порядок важен: сначала ссылки, потом жирный/курсив.
    """
    import re, html

    # 1. Экранируем HTML-спецсимволы КРОМЕ тех, что мы сами добавим тегами
    #    Делаем это поэтапно через placeholder-технику
    # Сначала вытаскиваем [текст](url) — ссылки
    links = []
    def save_link(m):
        link_text = m.group(1)
        url = m.group(2)
        # Экранируем содержимое
        safe_text = html.escape(link_text)
        safe_url  = html.escape(url)
        placeholder = f"\x00LINK{len(links)}\x00"
        links.append(f'<a href="{safe_url}">{safe_text}</a>')
        return placeholder

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', save_link, text)

    # 2. Экранируем оставшийся текст
    text = html.escape(text)

    # 3. Восстанавливаем ссылки
    for i, link_html in enumerate(links):
        text = text.replace(f"\x00LINK{i}\x00", link_html)

    # 4. **жирный** → <b>жирный</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # 5. *курсив* или _курсив_ → <i>курсив</i>
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<i>\1</i>', text)

    # 6. `моноширинный` → <code>моноширинный</code>
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)

    return text


# ─── Хранилище истории диалогов ───────────────────────────────────────────────
conversation_histories: dict[int, list] = {}
MAX_HISTORY_PAIRS = 10

# ─── Хранилище ожидающих комментарий дизлайков ────────────────────────────────
# Ключ: chat_id, значение: {question, answer, message_id}
pending_dislike: dict[int, dict] = {}

# ─── Кэш зарегистрированных пользователей (чтобы не дёргать Supabase каждый раз)
_registered_users: set[int] = set()

# ─── ID администратора (ваш Telegram chat_id) ────────────────────────────────
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# ─── Кэш забаненных пользователей (загружается из Supabase при старте) ────────
_banned_users: set[int] = set()

# ─── Rate limiting ────────────────────────────────────────────────────────────
# Храним метки времени последних N запросов для каждого chat_id
_rate_timestamps: dict[int, deque] = defaultdict(lambda: deque())
RATE_LIMIT_MESSAGES = 5    # не более 5 сообщений...
RATE_LIMIT_WINDOW   = 60   # ...за 60 секунд
RATE_LIMIT_COOLDOWN = 300  # пауза 5 минут при превышении

# ─── Антиспам: ключевые слова не по теме ─────────────────────────────────────
# Если вопрос ТОЛЬКО из этих слов или явно не про закупки — отклоняем
_OFFTOPIC_PATTERNS = [
    # Флуд / бессмыслица
    r"^[а-яёa-z\s]{1,3}$",               # очень короткие (1-3 символа)
    r"^(.)\1{4,}$",                        # повторяющийся символ (аааааа)
    r"^\d+$",                              # только цифры
    # Явно не тематические
    r"\b(погода|курс\s+(валют|доллар|евро)|рецепт|кино|фильм|игр[аы]|футбол|казино|крипт|биткоин|секс|порно|наркотик)\b",
]

import re as _re
_OFFTOPIC_COMPILED = [_re.compile(p, _re.IGNORECASE) for p in _OFFTOPIC_PATTERNS]

# Минимальная длина вопроса (защита от одиночных символов)
MIN_QUESTION_LEN = 4


# ─── Регистрация / обновление пользователя в Supabase ─────────────────────────

def upsert_user(user) -> None:
    """
    Регистрирует нового пользователя или обновляет last_seen.
    user — объект telegram.User
    """
    try:
        supabase.table("users").upsert({
            "chat_id":       user.id,
            "username":      user.username,
            "first_name":    user.first_name,
            "last_name":     user.last_name,
            "language_code": user.language_code,
            "is_bot":        user.is_bot,
            "last_seen":     "now()",
        }, on_conflict="chat_id").execute()
        logger.info(f"[user] Зарегистрирован/обновлён: chat_id={user.id} username={user.username}")
    except Exception as e:
        logger.warning(f"[user] Ошибка upsert_user: {e}")


# ─── Загрузка забаненных пользователей из Supabase ───────────────────────────

def load_banned_users() -> None:
    """Загружает список забаненных пользователей при старте бота."""
    global _banned_users
    try:
        result = supabase.table("users").select("chat_id").eq("is_banned", True).execute()
        _banned_users = {row["chat_id"] for row in (result.data or [])}
        logger.info(f"[ban] Загружено забаненных: {len(_banned_users)}")
    except Exception as e:
        logger.warning(f"[ban] Ошибка загрузки banned: {e}")


def is_banned(chat_id: int) -> bool:
    return chat_id in _banned_users


def ban_user(chat_id: int) -> bool:
    """Баним пользователя в Supabase и кэше."""
    try:
        supabase.table("users").update({"is_banned": True}).eq("chat_id", chat_id).execute()
        _banned_users.add(chat_id)
        logger.info(f"[ban] Забанен: {chat_id}")
        return True
    except Exception as e:
        logger.warning(f"[ban] Ошибка бана: {e}")
        return False


def unban_user(chat_id: int) -> bool:
    """Разбаниваем пользователя."""
    try:
        supabase.table("users").update({"is_banned": False}).eq("chat_id", chat_id).execute()
        _banned_users.discard(chat_id)
        logger.info(f"[ban] Разбанен: {chat_id}")
        return True
    except Exception as e:
        logger.warning(f"[ban] Ошибка разбана: {e}")
        return False


# ─── Rate limiting ────────────────────────────────────────────────────────────

def check_rate_limit(chat_id: int) -> tuple[bool, int]:
    """
    Проверяет, не превышен ли лимит запросов.
    Возвращает (разрешено, секунд_до_разблокировки).
    """
    now = time.time()
    dq = _rate_timestamps[chat_id]

    # Удаляем старые метки вне окна
    while dq and now - dq[0] > RATE_LIMIT_WINDOW:
        dq.popleft()

    if len(dq) >= RATE_LIMIT_MESSAGES:
        # Превышен лимит — считаем сколько ждать
        wait = int(RATE_LIMIT_COOLDOWN - (now - dq[0]))
        return False, max(wait, 1)

    dq.append(now)
    return True, 0


# ─── Антиспам ─────────────────────────────────────────────────────────────────

def is_offtopic(text: str) -> bool:
    """
    Проверяет, является ли сообщение явно нетематическим.
    Возвращает True если нужно отклонить.
    """
    t = text.strip()
    if len(t) < MIN_QUESTION_LEN:
        return True
    for pattern in _OFFTOPIC_COMPILED:
        if pattern.search(t):
            return True
    return False


def log_conversation(chat_id: int, question: str, answer: str,
                     chunks_used: int = 0, ktru_found: bool = False) -> None:
    """Сохраняет пару вопрос-ответ в таблицу conversations."""
    try:
        supabase.table("conversations").insert({
            "chat_id":     chat_id,
            "question":    question[:4000],
            "answer":      answer[:8000],
            "chunks_used": chunks_used,
            "ktru_found":  ktru_found,
        }).execute()
        # Обновляем счётчик сообщений пользователя
        supabase.rpc("update_user_last_seen", {"p_chat_id": chat_id}).execute()
    except Exception as e:
        logger.warning(f"[conv] Ошибка log_conversation: {e}")


# ─── Сохранение фидбека в Supabase ────────────────────────────────────────────

def save_feedback(
    chat_id: int,
    message_id: int,
    question: str,
    answer: str,
    rating: str,
    comment: str | None = None,
) -> None:
    """Сохраняет оценку ответа в таблицу feedback."""
    try:
        supabase.table("feedback").insert({
            "chat_id":    chat_id,
            "message_id": message_id,
            "question":   question[:2000],
            "answer":     answer[:4000],
            "rating":     rating,
            "comment":    comment,
        }).execute()
        logger.info(f"[feedback] chat={chat_id} msg={message_id} rating={rating}")
    except Exception as e:
        logger.warning(f"[feedback] Ошибка сохранения: {e}")


# ─── Хендлеры ─────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветственное сообщение."""
    # Регистрируем пользователя
    if update.effective_user:
        user = update.effective_user
        if user.id not in _registered_users:
            upsert_user(user)
            _registered_users.add(user.id)

    text = (
        "Сәлеметсіз бе! / Здравствуйте! 👋\n\n"
        "Я — консультант по государственным закупкам Республики Казахстан.\n"
        "Отвечаю на русском и казахском языке.\n\n"
        "📚 БАЗА ЗНАНИЙ:\n\n"
        "🔴 ОСНОВНОЕ ЗАКОНОДАТЕЛЬСТВО:\n"
        "📋 Закон РК «О государственных закупках» от 01.07.2024 № 106-VIII\n"
        "📋 Правила осуществления госзакупок, Приказ МФ РК от 09.10.2024 № 687\n"
        "📋 Правила формирования и ведения реестров, Приказ МФ РК от 26.09.2024 № 646\n\n"
        "🔵 ПЕРЕЧНИ С ОСОБЫМ ПОРЯДКОМ ЗАКУПКИ:\n"
        "📋 Перечень ТРУ (способ определяет уполномоченный орган) — Приказ МФ РК № 546\n"
        "📋 Перечень ТРУ (закупки у ООИ) — Приказ Минтруда № 345\n"
        "📋 Перечень ТРУ (закупки у МСБ/МСП) — Приказ МФ РК № 677\n\n"
        "🟢 ДОПОЛНИТЕЛЬНЫЕ НОРМЫ:\n"
        "📋 Единая методика расчёта ДВЦ (Приказ № 260)\n"
        "📋 Правила ведения реестра КТП — казахстанское содержание (Приказ № 327)\n"
        "📋 Правила организации питания в учреждениях (Приказ МОН РК № 598)\n"
        "📋 Гражданский кодекс РК (договоры, неустойка, штрафы, ответственность)\n"
        "📋 Инструкции электронного магазина Omarket.kz\n\n"
        "❓ ПОПРОБУЙТЕ СПРОСИТЬ:\n"
        "• Какие способы закупок существуют?\n"
        "• Когда можно закупать из одного источника?\n"
        "• Как рассчитывается неустойка за просрочку?\n"
        "• Что такое демпинговая цена?\n"
        "• Что значит закупка у ООИ или МСБ?\n"
        "• Какие условия договора поставки?\n\n"
        "⚡ КОМАНДЫ:\n"
        "/help — справка по использованию\n"
        "/clear — очистить историю диалога"
    )
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Справка."""
    text = (
        "ℹ️ КАК ИСПОЛЬЗОВАТЬ БОТА\n\n"
        "✅ ЧТО ДЕЛАТЬ:\n"
        "1️⃣ Задайте вопрос на русском или казахском языке\n"
        "2️⃣ Бот найдёт ответ в официальных документах\n"
        "3️⃣ Получите ответ со ссылками на источники\n"
        "4️⃣ Оцените ответ: 👍 нравится или 👎 не нравится\n\n"
        "🌍 ЯЗЫКИ:\n"
        "Поддерживается русский и казахский языки.\n"
        "Бот определит язык вашего вопроса автоматически.\n\n"
        "💾 ИСТОРИЯ ДИАЛОГА:\n"
        "Бот помнит до 10 последних пар вопрос-ответ в рамках одного чата.\n"
        "Это помогает давать более контекстные ответы.\n"
        "Очистить: /clear\n\n"
        "📊 СИСТЕМА ОЦЕНОК:\n"
        "После каждого ответа вы можете отправить:\n"
        "👍 — нравится (ответ был полезным)\n"
        "👎 — не нравится + напишите комментарий\n"
        "Это помогает нам улучшать качество ответов.\n\n"
        "⛔ ОГРАНИЧЕНИЯ:\n"
        "• Максимум 5 вопросов за 60 секунд\n"
        "• При превышении — пауза 5 минут\n"
        "• Спам и офф-топ отклоняются\n\n"
        "📋 КОМАНДЫ:\n"
        "/start — главное меню\n"
        "/help — эта справка\n"
        "/clear — очистить историю диалога\n\n"
        "⚠️ ВАЖНО:\n"
        "Бот отвечает ТОЛЬКО на основе официальных документов базы знаний.\n"
        "Если ответа нет в базе — бот об этом скажет.\n"
        "Не содержит спекуляции, предположения или советы.\n"
        "Это не замена консультации специалиста!"
    )
    await update.message.reply_text(text)


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Очистка истории диалога."""
    chat_id = update.effective_chat.id
    conversation_histories[chat_id] = []
    pending_dislike.pop(chat_id, None)
    await update.message.reply_text("✅ История диалога очищена. Начнём заново!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка входящего сообщения."""
    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()

    if not user_text:
        return

    # ── Регистрируем/обновляем пользователя ───────────────────────────────────
    if update.effective_user and chat_id not in _registered_users:
        upsert_user(update.effective_user)
        _registered_users.add(chat_id)

    # ── Проверка бана ─────────────────────────────────────────────────────────
    if is_banned(chat_id):
        await update.message.reply_text(
            "⛔ Ваш доступ к боту ограничен. Обратитесь к администратору."
        )
        logger.warning(f"[ban] Попытка входа забаненного: {chat_id}")
        return

    # ── Rate limiting ─────────────────────────────────────────────────────────
    allowed, wait_sec = check_rate_limit(chat_id)
    if not allowed:
        minutes = wait_sec // 60
        seconds = wait_sec % 60
        time_str = f"{minutes} мин {seconds} сек" if minutes else f"{seconds} сек"
        await update.message.reply_text(
            f"⏳ Вы отправляете сообщения слишком часто.\n"
            f"Пожалуйста, подождите {time_str}."
        )
        logger.warning(f"[rate] Лимит превышен: {chat_id}")
        return

    # ── Антиспам / нетематический вопрос ─────────────────────────────────────
    if is_offtopic(user_text):
        await update.message.reply_text(
            "❓ Этот бот отвечает только на вопросы по государственным закупкам РК.\n"
            "Пожалуйста, сформулируйте вопрос по теме."
        )
        logger.info(f"[spam] Нетематический вопрос от {chat_id}: {user_text[:50]}")
        return

    # ── Проверяем: ждём ли комментарий к дизлайку? ────────────────────────────
    if chat_id in pending_dislike:
        data = pending_dislike.pop(chat_id)
        save_feedback(
            chat_id=chat_id,
            message_id=data["message_id"],
            question=data["question"],
            answer=data["answer"],
            rating="dislike",
            comment=user_text,
        )
        await update.message.reply_text("Спасибо за отзыв! 🙏 Мы учтём это.")
        return

    # ── Обычный вопрос ────────────────────────────────────────────────────────
    if chat_id not in conversation_histories:
        conversation_histories[chat_id] = []

    history = conversation_histories[chat_id]

    await update.message.chat.send_action("typing")
    logger.info(f"[chat_id={chat_id}] Вопрос: {user_text[:80]}")

    try:
        answer, chunks_used, ktru_found = answer_question(user_text, history)

        # Логируем Q&A в Supabase
        log_conversation(
            chat_id=chat_id,
            question=user_text,
            answer=answer,
            chunks_used=chunks_used,
            ktru_found=ktru_found,
        )

        # Сохраняем в историю
        history.append({"role": "user",      "content": user_text})
        history.append({"role": "assistant",  "content": answer})
        if len(history) > MAX_HISTORY_PAIRS * 2:
            conversation_histories[chat_id] = history[-MAX_HISTORY_PAIRS * 2:]

        logger.info(f"[chat_id={chat_id}] Ответ: {answer[:80]}...")

        # Разбиваем на чанки по 4096 символов
        chunks = [answer[i:i + 4096] for i in range(0, len(answer), 4096)]

        # Кнопки 👍/👎 добавляем только к последнему чанку
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("👍 Полезно",    callback_data="like"),
            InlineKeyboardButton("👎 Не полезно", callback_data="dislike"),
        ]])

        bot_msg = None
        for i, chunk in enumerate(chunks):
            is_last = (i == len(chunks) - 1)
            html_chunk = md_to_html(chunk)
            try:
                bot_msg = await update.message.reply_text(
                    html_chunk,
                    parse_mode="HTML",
                    reply_markup=keyboard if is_last else None,
                )
            except Exception:
                # Последний fallback — plain text без разметки
                bot_msg = await update.message.reply_text(
                    chunk,
                    reply_markup=keyboard if is_last else None,
                )

        # Сохраняем данные для возможного фидбека
        if bot_msg:
            context.user_data[f"q_{bot_msg.message_id}"] = user_text
            context.user_data[f"a_{bot_msg.message_id}"] = answer
            context.user_data["last_msg_id"] = bot_msg.message_id
            context.user_data["last_question"] = user_text
            context.user_data["last_answer"] = answer

    except Exception as e:
        logger.error(f"[chat_id={chat_id}] Ошибка: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ Произошла ошибка при обработке запроса. Попробуйте ещё раз.\n"
            "Если ошибка повторяется — используйте /clear и задайте вопрос заново."
        )


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатия кнопок 👍 / 👎."""
    query = update.callback_query
    await query.answer()  # убираем "часики" на кнопке

    chat_id = update.effective_chat.id
    action = query.data  # "like" или "dislike"
    message_id = query.message.message_id

    # Берём вопрос/ответ из user_data
    question = context.user_data.get("last_question", "")
    answer   = context.user_data.get("last_answer", "")

    # Убираем кнопки с сообщения
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    if action == "like":
        save_feedback(chat_id, message_id, question, answer, "like")
        await query.message.reply_text("Спасибо! Рад был помочь 👍")

    elif action == "dislike":
        # Запоминаем — ждём комментарий следующим сообщением
        pending_dislike[chat_id] = {
            "message_id": message_id,
            "question":   question,
            "answer":     answer,
        }
        await query.message.reply_text(
            "Жаль, что ответ не помог 😔\n\n"
            "Напишите, что именно было не так — это поможет улучшить бота:"
        )


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/ban <chat_id> — забанить пользователя (только для администратора)."""
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("Использование: /ban <chat_id>")
        return
    try:
        target = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный chat_id")
        return
    if ban_user(target):
        await update.message.reply_text(f"✅ Пользователь {target} заблокирован.")
        # Уведомляем самого пользователя
        try:
            await context.bot.send_message(
                target,
                "⛔ Ваш доступ к боту ограничен администратором."
            )
        except Exception:
            pass
    else:
        await update.message.reply_text("❌ Ошибка при блокировке.")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/unban <chat_id> — разбанить пользователя (только для администратора)."""
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("Использование: /unban <chat_id>")
        return
    try:
        target = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный chat_id")
        return
    if unban_user(target):
        await update.message.reply_text(f"✅ Пользователь {target} разблокирован.")
    else:
        await update.message.reply_text("❌ Ошибка при разблокировке.")


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stats — быстрая статистика (только для администратора)."""
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return
    try:
        users_res = supabase.table("users").select("*", count="exact", head=True).execute()
        msgs_res  = supabase.table("conversations").select("*", count="exact", head=True).execute()
        ban_res   = supabase.table("users").select("*", count="exact", head=True).eq("is_banned", True).execute()
        fb_res    = supabase.table("feedback").select("*", count="exact", head=True).execute()
        text = (
            "📊 Быстрая статистика\n\n"
            f"👥 Пользователей: {users_res.count}\n"
            f"💬 Сообщений: {msgs_res.count}\n"
            f"⛔ Забанено: {ban_res.count}\n"
            f"⭐ Отзывов: {fb_res.count}\n\n"
            f"🔗 Панель: https://aldan76.github.io/goszakup-bot/"
        )
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка неизвестных команд."""
    await update.message.reply_text(
        "Неизвестная команда. Используйте /help для справки."
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальный обработчик ошибок — подавляет Conflict при rolling restart."""
    if isinstance(context.error, Conflict):
        # Railway делает rolling restart — временный конфликт, игнорируем
        logger.warning("Conflict (rolling restart) — игнорируем")
        return
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)


# ─── Запуск ───────────────────────────────────────────────────────────────────

def main() -> None:
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN не задан в .env")

    app = Application.builder().token(token).build()

    # Загружаем список забаненных при старте
    load_banned_users()

    # Порядок важен: CallbackQueryHandler должен быть раньше MessageHandler
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("help",   help_command))
    app.add_handler(CommandHandler("clear",  clear))
    app.add_handler(CommandHandler("ban",    ban_command))
    app.add_handler(CommandHandler("unban",  unban_command))
    app.add_handler(CommandHandler("stats",  admin_stats))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^(like|dislike)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown))
    app.add_error_handler(error_handler)

    logger.info("Бот запущен (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
