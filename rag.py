"""
rag.py — Логика поиска через Supabase + генерация ответа через Claude API.

Архитектура (двухшаговый поиск):
  Шаг 1: Проверка перечней ТРУ (ktru_perechen) — три типа:
          - upolnomoch_organ: Приказ МФ №546 — способ определяет уполномоченный орган
          - ooi: Приказ Минтруда №345 — закупается у организаций инвалидов
          - msb: Приказ МФ №677 — закупается у субъектов МСБ/МСП
  Шаг 2: Поиск по chunks (PostgreSQL full-text) — релевантные нормы закона/правил.
  Итог: Claude получает оба контекста и даёт полный ответ.
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

# ─── Ключевые слова для детекции вопросов о способе закупки ──────────────────

# Если вопрос содержит эти слова — проверяем перечни ТРУ (все три типа)
KTRU_TRIGGER_WORDS = [
    # Приказ №546 — уполномоченный орган
    "способ закупки", "способ осуществления", "каким способом", "как закупать",
    "строительно-монтажные", "строительные работы", "смр",
    "проектно-сметная документация", "проектно-сметной",
    "технико-экономическое обоснование", "тэо",
    "экспертиза проектов", "вневедомственная экспертиза",
    "инжиниринговые услуги", "технический надзор",
    "управление проектами",
    "опасные отходы", "утилизация отходов", "переработка отходов",
    "услуги связи",
    "перечень тру", "перечень товаров", "уполномоченный орган",
    "приказ 546", "приказ №546",
    "рейтингово-балльная",
    # Приказ №345 — ООИ (организации инвалидов)
    "инвалид", "оои", "организация инвалидов", "объединение инвалидов",
    "лица с инвалидностью", "приказ 345", "приказ №345",
    "постельное белье", "одеяло", "матрас", "мебель", "халат", "пижам",
    "спецодежда", "рабочая одежда", "саженец", "рассада", "клининг",
    "прачечн", "полиграф",
    # Приказ №677 — МСБ/МСП
    "малый бизнес", "средний бизнес", "мсб", "мсп",
    "малое предпринимательство", "среднее предпринимательство",
    "субъект мсп", "субъект мсб", "приказ 677", "приказ №677",
    "50000 мрп", "50 000 мрп",
]


def check_ktru_perechen(question: str) -> list[dict]:
    """
    Шаг 1: Проверяет, касается ли вопрос позиций из Перечня ТРУ (Приказ №546).
    Если да — возвращает найденные позиции из таблицы ktru_perechen.
    Поиск: полнотекстовый по полю nazvanie (russian stemming).
    """
    q_lower = question.lower()

    # Быстрая проверка: содержит ли вопрос триггерные слова
    has_trigger = any(t in q_lower for t in KTRU_TRIGGER_WORDS)

    # Всегда ищем — если есть хотя бы один существительный из сферы закупок
    try:
        # Строим tsquery из вопроса для поиска в nazvanie
        words = re.sub(r"[^\w\s]", " ", q_lower).split()
        stopwords_ru = {
            "что", "как", "для", "при", "или", "это", "из", "по", "в", "на", "с",
            "и", "а", "но", "не", "да", "то", "же", "ли", "есть", "если", "когда",
            "где", "кто", "чем", "так", "все", "можно", "нужно", "надо",
            "который", "какой", "свой", "этот", "тот", "один", "быть", "может",
            "какие", "каким", "какой", "какие", "каком",
        }
        keywords = [w for w in words if w not in stopwords_ru and len(w) > 3][:5]

        if not keywords:
            return []

        tsquery = " | ".join(keywords)  # OR-поиск для широкого охвата

        result = supabase.rpc(
            "search_ktru_perechen",
            {"query_text": tsquery}
        ).execute()

        if result.data:
            return result.data

        # Fallback: прямой поиск по ILIKE если RPC не дал результатов
        if has_trigger:
            # Берём самое длинное ключевое слово для поиска
            best_kw = max(keywords, key=len) if keywords else None
            if best_kw and len(best_kw) > 4:
                result = supabase.table("ktru_perechen").select("*").ilike(
                    "nazvanie", f"%{best_kw}%"
                ).execute()
                return result.data or []

    except Exception:
        pass

    return []


def build_ktru_context(ktru_items: list[dict]) -> str:
    """
    Форматирует найденные позиции перечней в контекст для Claude.
    Группирует по типу перечня (upolnomoch_organ / ooi / msb).
    """
    if not ktru_items:
        return ""

    # Метаданные по каждому типу перечня
    PERECHEN_META = {
        "upolnomoch_organ": {
            "title": "ПЕРЕЧЕНЬ ТРУ — СПОСОБ ЗАКУПКИ ОПРЕДЕЛЯЕТ УПОЛНОМОЧЕННЫЙ ОРГАН",
            "npa":   "Приказ МФ РК от 15.08.2024 №546 (рег. №34933)",
            "url":   "https://adilet.zan.kz/rus/docs/V2400034933",
        },
        "ooi": {
            "title": "ПЕРЕЧЕНЬ ТРУ — ЗАКУПАЮТСЯ У ОРГАНИЗАЦИЙ ЛИЦ С ИНВАЛИДНОСТЬЮ (ООИ)",
            "npa":   "Приказ Минтруда и соцзащиты РК от 03.09.2024 №345 (рег. №35032)",
            "url":   "https://adilet.zan.kz/rus/docs/V2400035032",
        },
        "msb": {
            "title": "ПЕРЕЧЕНЬ ТРУ — ЗАКУПАЮТСЯ У СУБЪЕКТОВ МСБ/МСП",
            "npa":   "Приказ МФ РК от 08.10.2024 №677 (рег. №35226)",
            "url":   "https://adilet.zan.kz/rus/docs/V2400035226",
        },
    }

    # Группируем по типу
    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in ktru_items:
        ptype = item.get("perechen_type", "upolnomoch_organ")
        groups[ptype].append(item)

    sections = []
    for ptype, items in groups.items():
        meta = PERECHEN_META.get(ptype, {
            "title": f"ПЕРЕЧЕНЬ ({ptype})",
            "npa": "", "url": "",
        })
        block = [
            f"## {meta['title']}",
            f"Источник: {meta['npa']}",
            f"URL: {meta['url']}",
            "",
            "Позиции из Перечня, соответствующие запросу:",
        ]
        for item in items:
            razdel = item.get("razdel") or ""
            razdel_str = f" [{razdel}]" if razdel else ""
            codes = item.get("ektru_codes") or ""
            codes_str = f"\n   Коды ЕКТРУ: {codes[:100]}" if codes else ""
            block.append(
                f"\n  {item['num']}. {item['nazvanie']}{razdel_str}\n"
                f"  Способ закупки: {item['sposob']}"
                f"{codes_str}"
            )
        sections.append("\n".join(block))

    return "# ПЕРЕЧНИ ТРУ С ОСОБЫМ ПОРЯДКОМ ЗАКУПКИ\n\n" + "\n\n".join(sections)


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
    Двухшаговый поиск: сначала перечень ТРУ (Приказ №546),
    потом нормы из chunks. Отвечает через Claude.

    Args:
        question: Вопрос пользователя.
        conversation_history: История диалога.

    Returns:
        Ответ Claude со ссылками на статьи/пункты.
    """
    # ── Шаг 1: Проверяем перечень ТРУ (Приказ №546) ───────────────────────────
    ktru_items = check_ktru_perechen(question)
    ktru_context = build_ktru_context(ktru_items)

    # ── Шаг 2: Поиск по chunks (нормы Закона и Правил) ────────────────────────
    chunks = search_supabase(question, top_n=6)

    if not chunks and not ktru_items:
        return (
            "По вашему вопросу не найдено релевантных статей в базе знаний.\n"
            "Попробуйте переформулировать вопрос, используя юридические термины."
        )

    # ── Сборка контекста ───────────────────────────────────────────────────────
    context_parts = []
    if ktru_context:
        context_parts.append(ktru_context)
    if chunks:
        context_parts.append("# НАЙДЕННЫЕ ДОКУМЕНТЫ\n\n" + build_context(chunks))

    context = "\n\n".join(context_parts)
    system = SYSTEM_PROMPT + "\n\n" + context

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
