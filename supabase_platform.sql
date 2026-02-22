-- ============================================================
-- Расширение таблицы chunks для поддержки инструкций площадок
-- Запустить в Supabase SQL Editor
-- ============================================================

-- ─── Шаг 1: Добавляем колонку source_platform ─────────────────
ALTER TABLE chunks
  ADD COLUMN IF NOT EXISTS source_platform TEXT DEFAULT 'law';

-- Проставляем 'law' для существующих чанков законов/правил
UPDATE chunks
  SET source_platform = 'law'
  WHERE source_platform IS NULL OR source_platform = '';

-- Индекс для быстрой фильтрации по платформе
CREATE INDEX IF NOT EXISTS idx_chunks_source_platform
  ON chunks(source_platform);

-- ─── Шаг 2: Обновлённая функция поиска с фильтром ─────────────
-- Теперь принимает необязательный параметр platform_filter
-- Если NULL — ищет по всем платформам (старое поведение)

CREATE OR REPLACE FUNCTION search_chunks(
    query_text   TEXT,
    match_count  INT  DEFAULT 6,
    platform_filter TEXT DEFAULT NULL   -- 'goszakup', 'omarket', 'law' или NULL = все
)
RETURNS TABLE (
    id              TEXT,
    document_short  TEXT,
    document_name   TEXT,
    source_type     TEXT,
    source_platform TEXT,
    chapter         TEXT,
    article_title   TEXT,
    official_url    TEXT,
    text            TEXT,
    rank            REAL
)
LANGUAGE sql
AS $$
    SELECT
        c.id,
        c.document_short,
        c.document_name,
        c.source_type,
        c.source_platform,
        c.chapter,
        c.article_title,
        c.official_url,
        c.text,
        ts_rank(to_tsvector('russian', c.text), to_tsquery('russian', query_text)) AS rank
    FROM chunks c
    WHERE
        to_tsvector('russian', c.text) @@ to_tsquery('russian', query_text)
        AND (platform_filter IS NULL OR c.source_platform = platform_filter)
    ORDER BY rank DESC
    LIMIT match_count;
$$;

-- ─── Шаг 3: RLS политика для новых строк инструкций ───────────
-- anon может читать чанки инструкций (уже есть общая политика SELECT)
-- Если нет — добавляем:
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'chunks' AND policyname = 'anon_select_chunks'
    ) THEN
        ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "anon_select_chunks" ON chunks
            FOR SELECT TO anon USING (true);
        CREATE POLICY "service_role_all_chunks" ON chunks
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

-- ─── Проверка ──────────────────────────────────────────────────
SELECT
    source_platform,
    source_type,
    COUNT(*) as count
FROM chunks
GROUP BY source_platform, source_type
ORDER BY source_platform, source_type;
