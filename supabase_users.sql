-- ============================================================
-- Таблицы для хранения пользователей и переписки бота
-- Запустить в Supabase SQL Editor
-- ============================================================

-- ─── Таблица пользователей ───────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    chat_id         BIGINT UNIQUE NOT NULL,         -- Telegram chat_id
    username        TEXT,                            -- @username (может быть NULL)
    first_name      TEXT,                            -- Имя
    last_name       TEXT,                            -- Фамилия (может быть NULL)
    language_code   TEXT,                            -- Язык пользователя (ru, kk, en...)
    is_bot          BOOLEAN DEFAULT FALSE,
    first_seen      TIMESTAMPTZ DEFAULT NOW(),       -- Дата первого обращения
    last_seen       TIMESTAMPTZ DEFAULT NOW(),       -- Дата последнего обращения
    message_count   INTEGER DEFAULT 0               -- Общее количество сообщений
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_users_chat_id ON users(chat_id);
CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen DESC);

-- ─── Таблица переписки (Q&A) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL REFERENCES users(chat_id) ON DELETE CASCADE,
    question    TEXT NOT NULL,                      -- Вопрос пользователя
    answer      TEXT NOT NULL,                      -- Ответ бота
    chunks_used INTEGER DEFAULT 0,                  -- Сколько чанков было найдено
    ktru_found  BOOLEAN DEFAULT FALSE,              -- Был ли найден КТРУ перечень
    created_at  TIMESTAMPTZ DEFAULT NOW()           -- Время Q&A
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_conversations_chat_id ON conversations(chat_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);

-- ─── Функция: обновление last_seen и message_count ───────────
CREATE OR REPLACE FUNCTION update_user_last_seen(p_chat_id BIGINT)
RETURNS VOID AS $$
BEGIN
    UPDATE users
    SET last_seen = NOW(),
        message_count = message_count + 1
    WHERE chat_id = p_chat_id;
END;
$$ LANGUAGE plpgsql;

-- ─── VIEW: Статистика для панели администратора ───────────────
CREATE OR REPLACE VIEW user_stats AS
SELECT
    u.chat_id,
    u.username,
    u.first_name,
    u.last_name,
    u.first_seen,
    u.last_seen,
    u.message_count,
    u.language_code,
    COUNT(c.id) AS conversation_count
FROM users u
LEFT JOIN conversations c ON u.chat_id = c.chat_id
GROUP BY u.id, u.chat_id, u.username, u.first_name, u.last_name,
         u.first_seen, u.last_seen, u.message_count, u.language_code
ORDER BY u.last_seen DESC;
