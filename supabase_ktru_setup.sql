-- ============================================================
-- Таблица ktru_perechen — Перечень ТРУ с предустановленным
-- способом закупки (Приказ МФ РК №546 от 15.08.2024)
-- ============================================================

CREATE TABLE IF NOT EXISTS ktru_perechen (
    id              serial primary key,
    num             integer not null,                 -- порядковый номер в перечне
    nazvanie        text not null,                    -- наименование товаров, работ, услуг
    sposob          text not null,                    -- способ осуществления госзакупок
    osnovaniye      text not null,                    -- НПА-основание
    npa_url         text not null,                    -- ссылка на НПА
    updated_at      timestamptz default now()
);

-- Индекс для полнотекстового поиска по наименованию
CREATE INDEX IF NOT EXISTS ktru_perechen_fts_idx
    ON ktru_perechen
    USING gin(to_tsvector('russian', nazvanie));

-- Комментарий к таблице
COMMENT ON TABLE ktru_perechen IS
    'Перечень ТРУ, по которым способ госзакупок определяется уполномоченным органом (МФ РК). '
    'Источник: Приказ МФ РК от 15.08.2024 №546, рег. №34933.';


-- ============================================================
-- Функция полнотекстового поиска по перечню ТРУ
-- Используется rag.py (шаг 1 двухшагового поиска)
-- ============================================================

CREATE OR REPLACE FUNCTION search_ktru_perechen(query_text text)
RETURNS TABLE (
    id          integer,
    num         integer,
    nazvanie    text,
    sposob      text,
    osnovaniye  text,
    npa_url     text
)
LANGUAGE sql STABLE
AS $$
    SELECT
        k.id,
        k.num,
        k.nazvanie,
        k.sposob,
        k.osnovaniye,
        k.npa_url
    FROM ktru_perechen k
    WHERE
        to_tsvector('russian', k.nazvanie) @@ to_tsquery('russian', query_text)
    ORDER BY k.num;
$$;

COMMENT ON FUNCTION search_ktru_perechen IS
    'Полнотекстовый поиск по наименованиям в перечне ТРУ (Приказ №546). '
    'Вызывается из rag.py на шаге 1 поиска. query_text — tsquery на русском.';
