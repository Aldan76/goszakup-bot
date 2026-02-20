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
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
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
    text = (
        "Сәлеметсіз бе! / Здравствуйте! 👋\n\n"
        "Я — консультант по государственным закупкам Республики Казахстан.\n\n"
        "Отвечаю строго по двум официальным документам:\n"
        "📋 Закон РК «О государственных закупках» от 01.07.2024 № 106-VIII\n"
        "📋 Правила осуществления госзакупок, Приказ МФ РК от 09.10.2024 № 687\n\n"
        "Примеры вопросов:\n"
        "• Какие способы закупок существуют?\n"
        "• Когда можно закупать из одного источника?\n"
        "• Как рассчитывается неустойка за просрочку?\n"
        "• Что такое демпинговая цена?\n\n"
        "/help — помощь\n"
        "/clear — очистить историю диалога"
    )
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Справка."""
    text = (
        "ℹ️ Как использовать бота\n\n"
        "Просто задайте вопрос на русском или казахском языке.\n\n"
        "Бот найдёт ответ в официальных документах и укажет источник.\n\n"
        "Команды:\n"
        "/start — начало работы\n"
        "/clear — очистить историю диалога\n"
        "/help — эта справка\n\n"
        "Важно: бот отвечает только на основе Закона и Правил о госзакупках РК."
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
        answer = answer_question(user_text, history)

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


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка неизвестных команд."""
    await update.message.reply_text(
        "Неизвестная команда. Используйте /help для справки."
    )


# ─── Запуск ───────────────────────────────────────────────────────────────────

def main() -> None:
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN не задан в .env")

    app = Application.builder().token(token).build()

    # Порядок важен: CallbackQueryHandler должен быть раньше MessageHandler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_command))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^(like|dislike)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown))

    logger.info("Бот запущен (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
