-- ============================================================
-- Миграция: добавляем поля в ktru_perechen и пересоздаём функцию
-- ============================================================

-- 1. Добавляем новые поля
ALTER TABLE ktru_perechen
    ADD COLUMN IF NOT EXISTS perechen_type text NOT NULL DEFAULT 'upolnomoch_organ';

ALTER TABLE ktru_perechen
    ADD COLUMN IF NOT EXISTS ektru_codes text;

ALTER TABLE ktru_perechen
    ADD COLUMN IF NOT EXISTS razdel text;

-- 2. СНАЧАЛА удаляем старую функцию (т.к. меняется сигнатура возвращаемых типов)
DROP FUNCTION IF EXISTS search_ktru_perechen(text);

-- 3. Создаём новую функцию с расширенными возвращаемыми полями
CREATE FUNCTION search_ktru_perechen(query_text text)
RETURNS TABLE (
    id              integer,
    num             integer,
    nazvanie        text,
    sposob          text,
    osnovaniye      text,
    npa_url         text,
    perechen_type   text,
    razdel          text,
    ektru_codes     text
)
LANGUAGE sql STABLE
AS $$
    SELECT
        k.id,
        k.num,
        k.nazvanie,
        k.sposob,
        k.osnovaniye,
        k.npa_url,
        k.perechen_type,
        k.razdel,
        k.ektru_codes
    FROM ktru_perechen k
    WHERE
        to_tsvector('russian', k.nazvanie) @@ to_tsquery('russian', query_text)
    ORDER BY k.perechen_type, k.num;
$$;

-- 4. Обновляем комментарий к таблице
COMMENT ON TABLE ktru_perechen IS
    'Сводная таблица перечней ТРУ с особым порядком закупки. '
    'perechen_type: upolnomoch_organ (Приказ МФ №546), ooi (Приказ Минтруда №345), msb (Приказ МФ №677).';

COMMENT ON FUNCTION search_ktru_perechen IS
    'Полнотекстовый поиск по всем перечням ТРУ (Приказы №546, №345, №677). '
    'Возвращает позиции отсортированные по типу перечня и номеру.';
