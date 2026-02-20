-- Таблица для хранения чанков документов госзакупок РК
-- Запустить в Supabase → SQL Editor

-- Включаем full-text search для русского языка
-- (используем simple конфигурацию так как ru не всегда доступна)

create table if not exists chunks (
    id          text primary key,         -- например: zakon_st16, pravila_gl17
    document_short  text not null,        -- "Закон о госзакупках"
    document_name   text not null,        -- полное название
    source_type     text not null,        -- "law" или "rules"
    chapter         text,
    chapter_num     integer,
    article_num     integer,
    article_title   text,
    punkt_range     integer[],
    text            text not null,
    official_url    text not null,
    char_count      integer,
    -- колонка для full-text search
    fts             tsvector generated always as (
        to_tsvector('simple', coalesce(article_title, '') || ' ' || text)
    ) stored
);

-- Индекс для быстрого full-text search
create index if not exists chunks_fts_idx on chunks using gin(fts);

-- Индекс по типу документа
create index if not exists chunks_source_type_idx on chunks(source_type);

-- Функция поиска по тексту (вызывается из Python)
create or replace function search_chunks(query_text text, match_count int default 6)
returns table (
    id text,
    document_short text,
    document_name text,
    source_type text,
    chapter text,
    chapter_num integer,
    article_num integer,
    article_title text,
    punkt_range integer[],
    text text,
    official_url text,
    char_count integer,
    rank real
)
language sql
as $$
    select
        c.id,
        c.document_short,
        c.document_name,
        c.source_type,
        c.chapter,
        c.chapter_num,
        c.article_num,
        c.article_title,
        c.punkt_range,
        c.text,
        c.official_url,
        c.char_count,
        ts_rank(c.fts, to_tsquery('simple', query_text)) as rank
    from chunks c
    where c.fts @@ to_tsquery('simple', query_text)
    order by rank desc
    limit match_count;
$$;
