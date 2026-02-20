# Goszakup Bot — Консультант по госзакупкам РК

Telegram-бот, отвечающий на вопросы по государственным закупкам Казахстана строго по официальным документам.

## Документы в базе знаний

1. **Закон РК «О государственных закупках»** от 01.07.2024 № 106-VIII ЗРК — 29 статей
2. **Правила осуществления государственных закупок** — Приказ МФ РК от 09.10.2024 № 687 — 19 глав

Итого: **68 чанков**, хранятся в Supabase PostgreSQL (full-text search).

## Архитектура

```
Вопрос пользователя (Telegram)
       ↓
Telegram Bot (python-telegram-bot 21.6)
       ↓
PostgreSQL Full-Text Search (Supabase)
→ top-6 релевантных чанков
       ↓
Claude API (claude-haiku-4-5-20251001)
→ ответ со ссылками на статьи/пункты
       ↓
Ответ пользователю в Telegram
```

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка окружения

```bash
copy .env.example .env
# Заполни .env своими данными
```

Переменные в `.env`:
```
TELEGRAM_TOKEN=...
ANTHROPIC_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
```

### 3. Настройка Supabase

1. Создай проект на [supabase.com](https://supabase.com)
2. В SQL Editor выполни `supabase_setup.sql`
3. Загрузи чанки: `python upload_chunks.py`

### 4. Тест RAG без Telegram

```bash
python rag.py
```

### 5. Запуск бота

```bash
python bot.py
```

## Деплой на Railway.app

1. Создай проект на [railway.app](https://railway.app)
2. Подключи GitHub-репозиторий
3. Добавь переменные окружения:
   - `TELEGRAM_TOKEN`
   - `ANTHROPIC_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
4. Railway запустит `python bot.py` через Procfile

## Структура проекта

```
goszakup-bot/
├── bot.py              # Telegram-хендлеры
├── rag.py              # Supabase FTS + Claude API
├── parse_docx.py       # Парсер .docx → JSON чанки
├── upload_chunks.py    # Загрузка чанков в Supabase
├── supabase_setup.sql  # SQL: таблица + индексы + функция поиска
├── data/
│   ├── chunks_all.json
│   ├── chunks_zakon.json
│   └── chunks_pravila.json
├── prompts/
│   └── system_prompt.txt
├── .env.example
├── requirements.txt
├── Procfile            # worker: python bot.py
└── README.md
```

## Тестовые вопросы

1. Когда можно закупать из одного источника?
2. Как рассчитывается неустойка за просрочку?
3. Что такое демпинговая цена и какие меры применяются?
4. Что такое электронный магазин и как через него закупать?
5. Как поставщик попадает в реестр недобросовестных участников?
6. Какие квалификационные требования предъявляются к поставщику?
7. В течение какого срока можно подать жалобу?
8. Когда закупки проводятся через единый организатор?
