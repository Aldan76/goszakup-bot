"""
bot.py — Telegram-бот консультант по госзакупкам РК.

Запуск:
    python bot.py

Переменные окружения (.env):
    TELEGRAM_TOKEN      — токен от BotFather
    ANTHROPIC_API_KEY   — ключ Claude API
"""

import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv
from rag import answer_question

load_dotenv()

# ─── Логирование ──────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Хранилище истории диалогов ───────────────────────────────────────────────
# Ключ: chat_id (int), значение: список сообщений
conversation_histories: dict[int, list] = {}
MAX_HISTORY_PAIRS = 10  # храним последние N пар вопрос/ответ


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
        "ℹ️ *Как использовать бота*\n\n"
        "Просто задайте вопрос на русском или казахском языке.\n\n"
        "Бот найдёт ответ в официальных документах и укажет источник.\n\n"
        "*Команды:*\n"
        "/start — начало работы\n"
        "/clear — очистить историю диалога\n"
        "/help — эта справка\n\n"
        "*Важно:* бот отвечает только на основе Закона и Правил о госзакупках РК. "
        "Для вопросов вне этих документов обращайтесь к официальным органам."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Очистка истории диалога."""
    chat_id = update.effective_chat.id
    conversation_histories[chat_id] = []
    await update.message.reply_text("✅ История диалога очищена. Начнём заново!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка входящего сообщения."""
    chat_id = update.effective_chat.id
    question = update.message.text.strip()

    if not question:
        return

    # Инициализация истории для нового пользователя
    if chat_id not in conversation_histories:
        conversation_histories[chat_id] = []

    history = conversation_histories[chat_id]

    # Показываем индикатор набора
    await update.message.chat.send_action("typing")

    logger.info(f"[chat_id={chat_id}] Вопрос: {question[:80]}")

    try:
        answer = answer_question(question, history)

        # Сохраняем в историю
        history.append({"role": "user",      "content": question})
        history.append({"role": "assistant",  "content": answer})

        # Ограничиваем историю
        if len(history) > MAX_HISTORY_PAIRS * 2:
            conversation_histories[chat_id] = history[-MAX_HISTORY_PAIRS * 2:]

        logger.info(f"[chat_id={chat_id}] Ответ: {answer[:80]}...")

        # Отправляем ответ — разбиваем если длиннее 4096 символов
        chunks = [answer[i:i + 4096] for i in range(0, len(answer), 4096)]
        for chunk in chunks:
            try:
                # Сначала пробуем с Markdown
                await update.message.reply_text(chunk, parse_mode="Markdown")
            except Exception:
                # Если Markdown сломался (спецсимволы) — отправляем plain text
                await update.message.reply_text(chunk)

    except Exception as e:
        logger.error(f"[chat_id={chat_id}] Ошибка: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ Произошла ошибка при обработке запроса. Попробуйте ещё раз.\n"
            "Если ошибка повторяется — используйте /clear и задайте вопрос заново."
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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_command))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown))

    logger.info("Бот запущен (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
