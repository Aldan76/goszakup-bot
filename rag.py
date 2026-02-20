"""
rag.py — Логика поиска через Supabase + генерация ответа через Claude API.

Архитектура:
  Вопрос → keyword поиск в Supabase (PostgreSQL full-text) → топ чанков → Claude → ответ
"""

import os
import re
from anthropic import Anthropic
from supabase import create_client
from dotenv import load_dotenv

load_dotenv(override=True)

# ─── Клиенты ──────────────────────────────────────────────────────────────────

anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"],
)

# ─── Системный промпт ─────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "system_prompt.txt")
with open(_PROMPT_PATH, encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

# ─── Стоп-слова для поиска ────────────────────────────────────────────────────

STOPWORDS = {
    "что", "как", "для", "при", "или", "это", "из", "по", "в", "на", "с",
    "и", "а", "но", "не", "да", "то", "же", "ли", "есть", "если", "когда",
    "где", "кто", "чем", "так", "все", "можно", "нужно", "надо", "такой",
    "который", "какой", "свой", "этот", "тот", "один", "быть", "может",
}


def build_tsquery(question: str) -> str:
    """
    Преобразует вопрос в PostgreSQL tsquery.
    Например: 'демпинговая цена меры' → 'демпинговая & цена & меры'
    """
    words = re.sub(r"[^\w\s]", " ", question.lower()).split()
    keywords = [w for w in words if w not in STOPWORDS and len(w) > 2]
    if not keywords:
        # Если все слова — стоп-слова, берём первые 3 слова без фильтрации
        keywords = question.lower().split()[:3]
    return " & ".join(keywords[:6])  # максимум 6 слов


# ─── Поиск в Supabase ─────────────────────────────────────────────────────────

def search_supabase(question: str, top_n: int = 6) -> list[dict]:
    """
    Ищет релевантные чанки в Supabase через PostgreSQL full-text search.
    Возвращает список чанков отсортированных по релевантности.
    """
    tsquery = build_tsquery(question)

    try:
        result = supabase.rpc(
            "search_chunks",
            {"query_text": tsquery, "match_count": top_n}
        ).execute()

        if result.data:
            return result.data

    except Exception:
        pass

    # Fallback: если tsquery не дал результатов — пробуем OR вместо AND
    try:
        tsquery_or = " | ".join(tsquery.split(" & "))
        result = supabase.rpc(
            "search_chunks",
            {"query_text": tsquery_or, "match_count": top_n}
        ).execute()

        if result.data:
            return result.data

    except Exception:
        pass

    # Последний fallback: просто берём первые N чанков
    try:
        result = supabase.table("chunks").select(
            "id, document_short, document_name, source_type, "
            "chapter, chapter_num, article_num, article_title, "
            "punkt_range, text, official_url, char_count"
        ).limit(top_n).execute()
        return result.data or []
    except Exception:
        return []


def build_context(chunks: list[dict]) -> str:
    """Формирует текст контекста из найденных чанков."""
    parts = []
    for chunk in chunks:
        header = chunk.get("article_title") or chunk.get("chapter") or ""
        parts.append(
            f"[{chunk['id']}] {chunk['document_short']} | {header}\n"
            f"Ссылка: {chunk['official_url']}\n"
            f"{chunk['text']}\n"
            f"{'=' * 60}"
        )
    return "\n".join(parts)


# ─── Основная функция ─────────────────────────────────────────────────────────

def answer_question(question: str, conversation_history: list) -> str:
    """
    Ищет релевантные чанки в Supabase и отвечает через Claude.

    Args:
        question: Вопрос пользователя.
        conversation_history: История диалога.

    Returns:
        Ответ Claude со ссылками на статьи/пункты.
    """
    chunks = search_supabase(question, top_n=6)

    if not chunks:
        return (
            "По вашему вопросу не найдено релевантных статей в базе знаний.\n"
            "Попробуйте переформулировать вопрос, используя юридические термины."
        )

    context = build_context(chunks)
    system = SYSTEM_PROMPT + "\n\n# НАЙДЕННЫЕ ДОКУМЕНТЫ\n\n" + context

    messages = conversation_history + [{"role": "user", "content": question}]

    response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=system,
        messages=messages,
    )

    return response.content[0].text


# ─── Локальное тестирование ───────────────────────────────────────────────────

if __name__ == "__main__":
    print("RAG-бот по госзакупкам РК (Supabase + Claude)")
    print("Введите 'выход' для завершения\n")

    history = []
    while True:
        try:
            question = input("Вопрос: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            break
        if not question:
            continue
        if question.lower() in ("выход", "exit", "quit"):
            break

        chunks = search_supabase(question)
        print(f"Найдено чанков в Supabase: {len(chunks)}")
        for c in chunks:
            title = (c.get("article_title") or c.get("chapter") or "")[:55]
            print(f"  [{c['id']}] {title}")

        print("Думаю...")
        try:
            answer = answer_question(question, history)
            print(f"\nОтвет:\n{answer}\n")
            print("-" * 60)
            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": answer})
            if len(history) > 20:
                history = history[-20:]
        except Exception as e:
            import traceback
            traceback.print_exc()
