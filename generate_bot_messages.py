"""
generate_bot_messages.py — Автоматически генерирует /start и /help сообщения из chunks

Парсит все chunks_*.json файлы, собирает статистику документов
и генерирует актуальные приветствие и справку для Telegram бота.

Запуск:
    python generate_bot_messages.py --output bot_messages.py

Это создаст файл bot_messages.py с переменными START_MESSAGE и HELP_MESSAGE
которые можно импортировать в bot.py
"""

import json
import os
import argparse
from pathlib import Path
from collections import defaultdict


def load_chunks_statistics():
    """Загружает статистику из всех chunks_*.json файлов."""
    data_dir = Path(__file__).parent / "data"

    stats = defaultdict(int)
    doc_info = defaultdict(dict)

    chunks_files = sorted(data_dir.glob("chunks_*.json"))

    for chunks_file in chunks_files:
        platform = chunks_file.stem.replace("chunks_", "")

        try:
            with open(chunks_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)

            stats[platform] = len(chunks)

            # Получаем информацию о документе из первого чанка
            if chunks:
                first_chunk = chunks[0]
                doc_info[platform] = {
                    "document_short": first_chunk.get("document_short", platform),
                    "document_name": first_chunk.get("document_name", platform),
                    "source_platform": first_chunk.get("source_platform", platform),
                }
        except Exception as e:
            print(f"[WARN] Error reading {chunks_file}: {e}")

    return stats, doc_info


def generate_start_message(stats, doc_info):
    """Генерирует содержание /start сообщения."""

    total_chunks = sum(stats.values())

    msg = (
        "Сәлеметсіз бе! / Здравствуйте! 👋\n\n"
        "Я — консультант по государственным закупкам Республики Казахстан.\n"
        "Отвечаю на русском и казахском языке.\n\n"
        "📚 БАЗА ЗНАНИЙ:\n\n"
    )

    # Группируем по категориям
    categories = {
        "ОСНОВНОЕ ЗАКОНОДАТЕЛЬСТВО": ["zakon", "pravila", "reestrov"],
        "ПЕРЕЧНИ ТРУ С ОСОБЫМ ПОРЯДКОМ": ["ktru"],
        "НАЛОГИ И УЧЕТ": ["tax"],
        "ДОГОВОРЫ И ОТВЕТСТВЕННОСТЬ": ["civil_code"],
        "ИНСТРУКЦИИ ПЛОЩАДОК": ["omarket", "goszakup"],
        "ДОПОЛНИТЕЛЬНЫЕ НОРМЫ": ["ktp", "dvc", "pitanie"],
    }

    emojis = {
        "ОСНОВНОЕ ЗАКОНОДАТЕЛЬСТВО": "🔴",
        "ПЕРЕЧНИ ТРУ С ОСОБЫМ ПОРЯДКОМ": "🔵",
        "НАЛОГИ И УЧЕТ": "💰",
        "ДОГОВОРЫ И ОТВЕТСТВЕННОСТЬ": "📋",
        "ИНСТРУКЦИИ ПЛОЩАДОК": "🟢",
        "ДОПОЛНИТЕЛЬНЫЕ НОРМЫ": "🟡",
    }

    for category, platforms in categories.items():
        category_chunks = 0
        has_content = False

        for platform in platforms:
            if platform in stats:
                has_content = True
                category_chunks += stats[platform]

        if has_content:
            emoji = emojis.get(category, "📋")
            msg += f"{emoji} {category}:\n"

            for platform in platforms:
                if platform in stats and stats[platform] > 0:
                    doc_name = doc_info[platform].get("document_name", platform)
                    chunks_count = stats[platform]
                    msg += f"📄 {doc_name} ({chunks_count} разделов)\n"

            msg += "\n"

    msg += (
        "❓ ПРИМЕРЫ ВОПРОСОВ:\n"
        "• Какие способы закупок существуют?\n"
        "• Когда можно закупать из одного источника?\n"
        "• Как рассчитывается неустойка за просрочку?\n"
        "• Что такое демпинговая цена?\n"
        "• Какие налоговые льготы у МСБ?\n"
        "• Как выставить электронный счет-фактуру?\n"
        "• Какие условия договора поставки?\n\n"
        "⚡ КОМАНДЫ:\n"
        "/help — справка по использованию\n"
        "/clear — очистить историю диалога\n\n"
        f"📊 В базе: {total_chunks}+ разделов документов"
    )

    return msg


def generate_help_message(stats):
    """Генерирует содержание /help сообщения."""

    msg = (
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

    return msg


def generate_python_file(start_msg, help_msg, output_file):
    """Генерирует Python файл с сообщениями."""

    content = '''"""
bot_messages.py — Автоматически сгенерированные сообщения для Telegram бота

ВАЖНО: Этот файл генерируется автоматически скриптом generate_bot_messages.py
При добавлении новых документов в data/chunks_*.json нужно пересоздать этот файл:

    python generate_bot_messages.py --output bot_messages.py

Не редактируй этот файл вручную!
"""

'''

    # Экранируем строки для Python
    def escape_string(s):
        return repr(s)[1:-1]  # Убираем кавычки repr()

    content += 'START_MESSAGE = (\n'
    for line in start_msg.split('\n'):
        content += f'    "{escape_string(line)}\\n"\n'
    content += ')\n\n'

    content += 'HELP_MESSAGE = (\n'
    for line in help_msg.split('\n'):
        content += f'    "{escape_string(line)}\\n"\n'
    content += ')\n'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[OK] Generated: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate /start and /help messages for Telegram bot")
    parser.add_argument("--output", default="bot_messages.py", help="Output Python file")
    parser.add_argument("--print-only", action="store_true", help="Only print, don't save")
    args = parser.parse_args()

    print("=" * 70)
    print("GENERATE BOT MESSAGES FROM CHUNKS")
    print("=" * 70 + "\n")

    stats, doc_info = load_chunks_statistics()

    print("DOCUMENT STATISTICS:")
    total = sum(stats.values())
    for platform, count in sorted(stats.items()):
        doc_name = doc_info[platform].get("document_name", platform)
        print(f"  {platform:20} - {count:3} sections ({doc_name})")
    print(f"  {'TOTAL':20} - {total:3} sections\n")

    start_msg = generate_start_message(stats, doc_info)
    help_msg = generate_help_message(stats)

    if args.print_only:
        print("=" * 70)
        print("/START MESSAGE:")
        print("=" * 70)
        print(start_msg)
        print("\n" + "=" * 70)
        print("/HELP MESSAGE:")
        print("=" * 70)
        print(help_msg)
    else:
        generate_python_file(start_msg, help_msg, args.output)
        print(f"[OK] Usage in bot.py:\n")
        print(f"  from bot_messages import START_MESSAGE, HELP_MESSAGE\n")
        print(f"  # In start() function:")
        print(f"  await update.message.reply_text(START_MESSAGE)\n")
        print(f"  # In help_command() function:")
        print(f"  await update.message.reply_text(HELP_MESSAGE)")


if __name__ == "__main__":
    main()
