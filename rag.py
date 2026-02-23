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
            codes_str = f"\n   Коды ЕКТРУ: {codes[:500]}" if codes else ""
            block.append(
                f"\n  {item['num']}. {item['nazvanie']}{razdel_str}\n"
                f"  Способ закупки: {item['sposob']}"
                f"{codes_str}"
            )
        sections.append("\n".join(block))

    return "# ПЕРЕЧНИ ТРУ С ОСОБЫМ ПОРЯДКОМ ЗАКУПКИ\n\n" + "\n\n".join(sections)


# ─── Детектор вопросов про площадки ──────────────────────────────────────────

# Триггеры для goszakup.gov.kz
GOSZAKUP_TRIGGER_WORDS = [
    "goszakup", "госзакуп", "портал госзакупок", "портал закупок",
    "веб-портал", "вебпортал", "как войти на портал", "личный кабинет заказчика",
    "личный кабинет поставщика", "эцп", "электронная цифровая подпись",
    "ncalayer", "нклеер", "нкалаер", "казтокен", "kalkan",
    "как зарегистрироваться", "регистрация на портале", "авторизация",
    "план госзакупок", "план закупок", "создать объявление", "разместить объявление",
    "конкурсная документация", "заявка на участие", "ценовое предложение",
    "электронный конкурс", "аукцион", "запрос ценовых предложений", "зцп",
    "из одного источника", "договор закупки", "протокол", "отчёт о закупке",
    "нет заявок", "признан несостоявшимся", "жалоба", "апелляция",
    "навигация по порталу", "как работать с порталом",
]

# Триггеры для omarket.kz
OMARKET_TRIGGER_WORDS = [
    "omarket", "омаркет", "электронный магазин", "эл.магазин",
    "интернет-магазин закупок", "магазин госзакупок",
    "как купить через магазин", "заявка в магазин", "оферта",
    "каталог товаров", "корзина закупок", "добавить в корзину",
    "карточка товара", "поставщик в магазине", "подать оферту",
    "разместить товар", "прайс лист", "прайс-лист поставщика",
    "подтверждение заявки", "отказ в заявке", "статус заявки",
    "электронный магазин закупок",
]


def detect_platform(question: str) -> str | None:
    """
    Определяет, относится ли вопрос к конкретной площадке.
    Возвращает 'goszakup', 'omarket' или None (нет специфики площадки).
    Прямое упоминание названия площадки имеет приоритет над контекстными триггерами.
    """
    q = question.lower()

    # Прямые названия площадок — высший приоритет
    has_omarket   = any(t in q for t in ["omarket", "омаркет"])
    has_goszakup  = any(t in q for t in ["goszakup", "госзакуп"])

    if has_omarket and not has_goszakup:
        return "omarket"
    if has_goszakup and not has_omarket:
        return "goszakup"

    # Контекстные триггеры (без учёта прямых названий)
    gz_score = sum(1 for t in GOSZAKUP_TRIGGER_WORDS
                   if t not in ("goszakup", "госзакуп") and t in q)
    om_score  = sum(1 for t in OMARKET_TRIGGER_WORDS
                    if t not in ("omarket", "омаркет") and t in q)

    if gz_score == 0 and om_score == 0:
        return None
    return "goszakup" if gz_score >= om_score else "omarket"


# ─── Детектор вопросов про Налоговый кодекс ──────────────────────────────────

# Триггерные слова для поиска в Налоговом кодексе (tax)
TAX_CODE_TRIGGERS = [
    # НДС
    "НДС", "ндс", "налог на добавленную стоимость", "добавленная стоимость",
    "налоговая база", "налоговая ставка", "счет фактура", "счет-фактура",
    "электронный счет", "авансовый платеж", "авансовый счет",
    # Налоговые льготы
    "налоговые льготы", "налоговая льгота", "льгота по НДС",
    "упрощенное налогообложение", "усн", "льготный режим",
    # Налоговые резиденты
    "налоговый резидент", "нерезидент", "налоговый статус",
    # Учет доходов/расходов
    "признание дохода", "признание расходов", "налоговый учет",
    "вычитаемые расходы", "экономически обоснованные",
    # Налоговый контроль
    "налоговая проверка", "налоговые органы", "налоговая задолженность",
    "пени по налогам", "штрафные санкции", "налоговое правонарушение",
    # Бухгалтерский учет
    "бухгалтерский учет", "проводка", "счет", "баланс", "отчетность",
    "финансовая отчетность", "налоговая декларация",
    # Общие
    "налог", "налоги", "налоговый", "бухгалтерия", "аккаунтинг",
]


def needs_tax_code(question: str) -> bool:
    """
    Проверяет, нужно ли дополнительно искать нормы Налогового кодекса.
    Возвращает True если вопрос касается НДС, налоговых льгот, учета и т.п.
    """
    q = question.lower()
    return any(t in q for t in TAX_CODE_TRIGGERS)


# ─── Детектор вопросов про Гражданский кодекс ────────────────────────────────

# Триггерные слова для поиска в ГК РК (civil_code)
CIVIL_CODE_TRIGGERS = [
    # Договорное право
    "договор", "договора", "договоре", "договором", "договорных",
    "оферта", "оферту", "оферты", "акцепт", "акцепта",
    "заключение договора", "расторжение договора", "изменение договора",
    # Обязательства
    "обязательство", "обязательства", "обязательств", "обязательствах",
    "исполнение обязательства", "прекращение обязательства",
    # Ответственность
    "неустойка", "неустойки", "неустойку", "штраф", "штрафа", "штрафные",
    "пеня", "пени", "убытки", "убытков", "возмещение убытков",
    "ущерб", "ущерба", "реальный ущерб", "упущенная выгода",
    "ответственность сторон", "имущественная ответственность",
    # Купля-продажа и поставка
    "поставка товара", "договор поставки", "купля-продажа",
    "покупатель", "продавец", "поставщик обязан",
    # Гражданский кодекс
    "гражданский кодекс", "гк рк", "ст. гк", "статья гк",
    "нормы гк", "по гк", "согласно гк",
    # Сделки и форма
    "недействительная сделка", "ничтожная сделка",
    "письменная форма", "электронная форма договора",
    # Иск и претензия
    "иск", "претензия", "исковая давность", "срок давности",
    # Казахские эквиваленты
    "шарт", "шарттың", "шартты", "өтемақы", "айыппұл",
]


def needs_civil_code(question: str) -> bool:
    """
    Проверяет, нужно ли дополнительно искать нормы ГК РК.
    Возвращает True если вопрос касается договорного права, ответственности и т.п.
    """
    q = question.lower()
    return any(t in q for t in CIVIL_CODE_TRIGGERS)


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
    Также применяет замену аббревиатур и синонимов для расширения поиска.
    """
    # Замена аббревиатур и синонимов на слова из текстов чанков
    SYNONYMS = {
        "ктп":  "товаропроизводителей",
        "двц":  "внутристрановой",
        "ооо":  "организация",
        "мсб":  "предпринимательство",
        "мсп":  "предпринимательство",
        "оои":  "инвалидностью",
        "смр":  "строительно-монтажные",
        "тру":  "товаров",
        "фот":  "труда",
        "нпа":  "нормативный",
        "казахстанское содержание": "товаропроизводителей",
        "казахстанского содержания": "товаропроизводителей",
        "казахстанском содержании": "товаропроизводителей",
    }
    q = question.lower()
    # Многословные замены сначала
    for phrase, replacement in SYNONYMS.items():
        if " " in phrase:
            q = q.replace(phrase, replacement)
    words = re.sub(r"[^\w\s]", " ", q).split()
    expanded = []
    for w in words:
        if w in SYNONYMS and " " not in SYNONYMS[w]:
            expanded.append(SYNONYMS[w])
        else:
            expanded.append(w)
    keywords = [w for w in expanded if w not in STOPWORDS and len(w) > 2]
    if not keywords:
        keywords = question.lower().split()[:3]
    return " & ".join(keywords[:6])


# ─── Поиск в Supabase ─────────────────────────────────────────────────────────

def search_supabase(question: str, top_n: int = 6,
                    platform: str | None = None) -> list[dict]:
    """
    Ищет релевантные чанки в Supabase через PostgreSQL full-text search.
    Если platform задан ('goszakup'/'omarket'/'law') — фильтрует по нему.
    Возвращает список чанков отсортированных по релевантности.
    """
    tsquery = build_tsquery(question)
    params = {"query_text": tsquery, "match_count": top_n}
    if platform:
        params["platform_filter"] = platform

    try:
        result = supabase.rpc("search_chunks", params).execute()
        if result.data:
            return result.data
    except Exception:
        pass

    # Fallback: OR вместо AND
    try:
        params_or = dict(params)
        params_or["query_text"] = " | ".join(tsquery.split(" & "))
        result = supabase.rpc("search_chunks", params_or).execute()
        if result.data:
            return result.data
    except Exception:
        pass

    return []


def build_context(chunks: list[dict]) -> str:
    """Формирует текст контекста из найденных чанков."""
    parts = []
    for chunk in chunks:
        header = chunk.get("article_title") or chunk.get("chapter") or ""
        platform = chunk.get("source_platform", "")
        platform_label = f" [{platform.upper()}]" if platform and platform != "law" else ""
        parts.append(
            f"[{chunk['id']}] {chunk['document_short']}{platform_label} | {header}\n"
            f"Ссылка: {chunk['official_url']}\n"
            f"{chunk['text']}\n"
            f"{'=' * 60}"
        )
    return "\n".join(parts)


# ─── Основная функция ─────────────────────────────────────────────────────────

def answer_question(question: str, conversation_history: list) -> tuple[str, int, bool]:
    """
    Пятишаговый поиск:
      Шаг 1 — Перечни ТРУ (КТРУ, ООИ, МСБ)
      Шаг 2 — Инструкции площадок (goszakup / omarket) если вопрос про них
      Шаг 3 — Нормы Закона и Правил госзакупок
      Шаг 4 — Статьи ГК РК (договоры, ответственность, неустойка) — если нужно
      Шаг 5 — Нормы Налогового кодекса (НДС, льготы, учет) — если нужно

    Args:
        question: Вопрос пользователя.
        conversation_history: История диалога.

    Returns:
        Tuple: (ответ Claude, количество найденных чанков, был ли найден КТРУ)
    """
    # ── Шаг 1: Перечень ТРУ ───────────────────────────────────────────────────
    ktru_items = check_ktru_perechen(question)
    ktru_context = build_ktru_context(ktru_items)

    # ── Шаг 2: Определяем платформу и ищем инструкции ────────────────────────
    platform = detect_platform(question)
    platform_chunks = []
    platform_context = ""

    if platform:
        # Ищем сначала по конкретной платформе (приоритетно)
        platform_chunks = search_supabase(question, top_n=3, platform=platform)
        if platform_chunks:
            platform_label = "GOSZAKUP.GOV.KZ" if platform == "goszakup" else "OMARKET.KZ"
            platform_context = (
                f"# ИНСТРУКЦИИ ПО РАБОТЕ С ПОРТАЛОМ {platform_label}\n\n"
                + build_context(platform_chunks)
            )

    # ── Шаг 3: Поиск по нормативным чанкам (закон, правила) ──────────────────
    # Если вопрос строго про площадку — законодательные нормы менее важны,
    # берём меньше. Если общий вопрос — берём полный объём.
    law_top_n = 3 if platform_chunks else 4
    law_chunks = search_supabase(question, top_n=law_top_n, platform="law")

    # Если фильтр по 'law' не дал результатов (старые чанки без source_platform)
    # — ищем без фильтра (обратная совместимость)
    if not law_chunks and not platform_chunks:
        law_chunks = search_supabase(question, top_n=4)

    # ── Шаг 4: Нормы ГК РК (если вопрос про договоры, ответственность, etc.) ──
    civil_chunks = []
    if needs_civil_code(question):
        civil_chunks = search_supabase(question, top_n=3, platform="civil_code")

    # ── Шаг 5: Нормы Налогового кодекса (если вопрос про НДС, налоги, учет) ─────
    tax_chunks = []
    if needs_tax_code(question):
        tax_chunks = search_supabase(question, top_n=3, platform="tax")

    all_chunks = platform_chunks + law_chunks + civil_chunks + tax_chunks

    if not all_chunks and not ktru_items:
        return (
            "По вашему вопросу не найдено релевантных материалов в базе знаний.\n"
            "Попробуйте переформулировать вопрос или уточните название площадки.",
            0, False
        )

    # ── Сборка контекста ───────────────────────────────────────────────────────
    context_parts = []
    if ktru_context:
        context_parts.append(ktru_context)
    if platform_context:
        context_parts.append(platform_context)
    if law_chunks:
        context_parts.append("# НОРМАТИВНЫЕ ДОКУМЕНТЫ\n\n" + build_context(law_chunks))
    if civil_chunks:
        context_parts.append("# ГРАЖДАНСКИЙ КОДЕКС РК (РЕЛЕВАНТНЫЕ СТАТЬИ)\n\n" + build_context(civil_chunks))
    if tax_chunks:
        context_parts.append("# НАЛОГОВЫЙ КОДЕКС РК (НАЛОГИ И УЧЕТ)\n\n" + build_context(tax_chunks))

    context = "\n\n".join(context_parts)
    system = SYSTEM_PROMPT + "\n\n" + context

    messages = conversation_history + [{"role": "user", "content": question}]

    # Retry при rate limit (до 3 попыток с паузой)
    for attempt in range(3):
        try:
            response = anthropic_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                system=system,
                messages=messages,
            )
            return response.content[0].text, len(all_chunks), bool(ktru_items)
        except Exception as e:
            err = str(e)
            if "rate_limit" in err and attempt < 2:
                import time
                time.sleep(20)
                continue
            raise


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
            answer, chunks_used, ktru_found = answer_question(question, history)
            print(f"\nОтвет (чанков={chunks_used}, ктру={ktru_found}):\n{answer}\n")
            print("-" * 60)
            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": answer})
            if len(history) > 20:
                history = history[-20:]
        except Exception as e:
            import traceback
            traceback.print_exc()
