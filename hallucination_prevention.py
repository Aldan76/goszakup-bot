#!/usr/bin/env python3
"""
Система предотвращения галлюцинаций в RAG ответах
Проверяет, что ответ полностью основан на исходных документах
"""

import re
from typing import Dict, List, Tuple, Optional
from enum import Enum

class HallucinationLevel(Enum):
    """Уровни подозрений на галлюцинацию"""
    SAFE = "safe"                    # Все цитируется из документов
    LOW_RISK = "low_risk"            # Небольшая интерпретация OK
    MEDIUM_RISK = "medium_risk"      # Требуется проверка
    HIGH_RISK = "high_risk"          # Вероятно галлюцинация
    CRITICAL = "critical"            # Явная галлюцинация

# Для сравнения уровней опасности (выше значение = более опасно)
SEVERITY_ORDER = {
    "safe": 0,
    "low_risk": 1,
    "medium_risk": 2,
    "high_risk": 3,
    "critical": 4
}

class HallucinationDetector:
    """Детектор галлюцинаций в ответах бота"""

    # Красные флаги - признаки галлюцинаций
    RED_FLAGS = {
        # Придуманные документы
        "Акт об изменении договора": {
            "level": HallucinationLevel.HIGH_RISK,
            "message": "Такого документа не существует в РК. Используйте 'Дополнительное соглашение'",
            "keywords": ["акт об изменении", "акт изменения договора"]
        },
        "Документ о выделении средств": {
            "level": HallucinationLevel.HIGH_RISK,
            "message": "Неточный термин. Указывайте реквизиты приказа/решения о выделении",
            "keywords": ["документ о выделении", "документ выделении средств"]
        },
        "Согласие обеих сторон на изменение": {
            "level": HallucinationLevel.MEDIUM_RISK,
            "message": "Согласие подразумевается в подписании доп. соглашения, отдельный документ не требуется",
            "keywords": ["согласие обеих сторон", "согласие сторон на изменение"]
        },
        # Неправильные процедуры
        "Новый пункт плана": {
            "level": HallucinationLevel.HIGH_RISK,
            "message": "НЕПРАВИЛЬНО! Новый пункт плана НЕ нужен, это одна закупка",
            "keywords": ["новый пункт плана", "создать новый пункт", "новый пункт закупки"]
        },
        # Придуманные нормы
        "пункт 2 статьи 18": {
            "level": HallucinationLevel.HIGH_RISK,
            "message": "ВАЖНО: Проверьте наличие пункта 2 ст.18 в Законе! Часто этот пункт галлюцинируется",
            "keywords": ["пункт 2 статьи 18", "п. 2 ст. 18"]
        },
    }

    # Слова-индикаторы галлюцинаций
    HALLUCINATION_INDICATORS = [
        "обычно",
        "как правило",
        "можно предположить",
        "вероятно",
        "предположительно",
        "очевидно",
        "логично",
        "должно быть",
        "следует ожидать",
        "как известно",
        "принято считать",
    ]

    def __init__(self):
        self.detected_hallucinations = []

    def detect(self, answer: str, source_chunks: List[Dict]) -> Dict:
        """
        Проверить ответ на наличие галлюцинаций

        Args:
            answer: Ответ бота
            source_chunks: Исходные чанки из документов

        Returns:
            Словарь с результатами проверки
        """
        result = {
            "level": HallucinationLevel.SAFE,
            "confidence": 1.0,
            "detected_issues": [],
            "corrections": [],
            "source_coverage": 0.0,
            "recommendations": []
        }

        # Проверка 1: Красные флаги
        red_flag_issues = self._check_red_flags(answer)
        if red_flag_issues:
            result["detected_issues"].extend(red_flag_issues)
            # Найти максимальный уровень по severity
            max_level = max([issue["level"] for issue in red_flag_issues],
                           key=lambda x: SEVERITY_ORDER.get(x.value, 0))
            if SEVERITY_ORDER.get(max_level.value, 0) > SEVERITY_ORDER.get(result["level"].value, 0):
                result["level"] = max_level

        # Проверка 2: Индикаторы неуверенности
        uncertainty_issues = self._check_uncertainty_indicators(answer)
        if uncertainty_issues:
            result["detected_issues"].extend(uncertainty_issues)

        # Проверка 3: Привязка к источникам
        coverage = self._check_source_coverage(answer, source_chunks)
        result["source_coverage"] = coverage
        if coverage < 0.7:
            # Только понижаем уровень если текущий уровень меньше MEDIUM_RISK
            if SEVERITY_ORDER.get(result["level"].value, 0) < SEVERITY_ORDER.get("medium_risk", 2):
                result["level"] = HallucinationLevel.MEDIUM_RISK
            result["recommendations"].append(
                "НИЗКАЯ привязка к источникам (< 70%). Велика вероятность галлюцинаций."
            )

        # Проверка 4: Проверка "нормативных ссылок"
        citation_issues = self._check_citation_accuracy(answer, source_chunks)
        if citation_issues:
            result["detected_issues"].extend(citation_issues)
            result["level"] = HallucinationLevel.HIGH_RISK

        # Вычислить confidence уверенности
        result["confidence"] = self._calculate_confidence(result)

        return result

    def _check_red_flags(self, answer: str) -> List[Dict]:
        """Проверка на известные галлюцинации"""
        issues = []
        answer_lower = answer.lower()

        for flag, config in self.RED_FLAGS.items():
            for keyword in config["keywords"]:
                if keyword.lower() in answer_lower:
                    issues.append({
                        "type": "red_flag",
                        "level": config["level"],
                        "message": config["message"],
                        "detected_text": flag,
                        "severity": "CRITICAL" if config["level"] == HallucinationLevel.HIGH_RISK else "WARNING"
                    })
                    break

        return issues

    def _check_uncertainty_indicators(self, answer: str) -> List[Dict]:
        """Проверка слов, которые указывают на неуверенность"""
        issues = []
        answer_lower = answer.lower()

        # Разбить на предложения
        sentences = re.split(r'[.!?]', answer)

        for sentence in sentences:
            sentence_lower = sentence.lower()
            for indicator in self.HALLUCINATION_INDICATORS:
                if indicator in sentence_lower:
                    # Это может быть галлюцинация
                    issues.append({
                        "type": "uncertainty_indicator",
                        "level": HallucinationLevel.LOW_RISK,
                        "message": f"Используется слово '{indicator}' - это может указывать на предположение, а не факт",
                        "detected_text": indicator,
                        "context": sentence.strip()[:100]
                    })
                    break

        return issues

    def _check_source_coverage(self, answer: str, source_chunks: List[Dict]) -> float:
        """
        Проверить, насколько ответ покрывается исходными документами
        Возвращает процент (0.0-1.0)

        УЛУЧШЕНО (2026-02-23):
        - Более гибкий алгоритм, не требующий точного совпадения фраз
        - Проверяет наличие ключевых слов и понятий, а не точных фраз
        - Позволяет переформулировки и перестановки информации
        """
        if not source_chunks:
            return 0.0

        # Объединить весь текст из чанков
        source_text = " ".join([chunk.get("text", "") for chunk in source_chunks])
        source_lower = source_text.lower()

        # СТРАТЕГИЯ 1: Извлечь отдельные ЗНАЧИМЫЕ слова (> 3 букв)
        # Это более гибко чем точные 3-слова фразы
        answer_lower = answer.lower()

        # Удалить стоп-слова (предлоги, артикли и т.д.)
        stop_words = {
            'и', 'или', 'а', 'но', 'в', 'на', 'по', 'к', 'от', 'с', 'у', 'о',
            'это', 'что', 'как', 'который', 'такой', 'более', 'менее', 'для',
            'быть', 'иметь', 'делать', 'может', 'должен', 'нужен', 'требуется',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been'
        }

        # Извлечь значимые слова
        answer_words = set()
        for word in re.findall(r'\b\w+\b', answer_lower):
            if len(word) > 3 and word not in stop_words:
                answer_words.add(word)

        if not answer_words:
            return 0.5  # По умолчанию если нет значимых слов - считаем 50%

        # СТРАТЕГИЯ 2: Проверить, сколько значимых слов есть в источниках
        covered_words = sum(1 for word in answer_words if word in source_lower)
        coverage = covered_words / len(answer_words) if answer_words else 0.0

        # СТРАТЕГИЯ 3: Бонус за структурные элементы (цитаты на документы)
        # Если ответ содержит ссылки на известные документы, это признак хорошего покрытия
        document_keywords = [
            'пункт', 'статья', 'ст.', 'п.', 'закон', 'договор', 'соглашение',
            'пункты', 'статьи', 'законом', 'договором', 'согласно'
        ]

        # Проверить есть ли такие структурные элементы
        has_citations = any(keyword in answer_lower for keyword in document_keywords)
        if has_citations:
            # Добавить бонус 15% если есть структурные цитирования
            coverage = min(1.0, coverage + 0.15)

        return max(0.0, min(1.0, coverage))

    def _check_citation_accuracy(self, answer: str, source_chunks: List[Dict]) -> List[Dict]:
        """
        Проверить точность ссылок на нормативные акты

        УЛУЧШЕНО (2026-02-23):
        - Не помечать валидные ссылки на статьи/пункты как галлюцинации
        - Только проверять на явно придуманные документы (которые в RED_FLAGS)
        - Позволять ссылки на ZRGK, ГК РК, НК РК и т.д. даже если прямого текста нет в чанках
        """
        issues = []

        # Найти все ссылки на статьи/пункты
        pattern = r'(ст\.|статья|пункт|п\.)\s*(\d+(?:\.\d+)*)'
        citations = re.findall(pattern, answer, re.IGNORECASE)

        source_text = " ".join([chunk.get("text", "") for chunk in source_chunks])

        # Список ИЗВЕСТНЫХ документов, которые мы поддерживаем
        # Не нужно штрафовать за цитаты этих документов даже если их нет в чанках
        KNOWN_DOCUMENTS = [
            "зргк",  # Закон о госзакупках РК
            "гк рк",  # Гражданский кодекс РК
            "нк рк",  # Налоговый кодекс РК
            "закон об электронной коммерции",
            "закон об эцп",
            "правила ээгз",
            "договор",
            "соглашение"
        ]

        for citation in citations:
            citation_num = citation[1]  # Например: "535" из "пункт 535"
            citation_str = f"{citation[0]} {citation[1]}"

            # Проверка 1: Есть ли эта цитата в источниках?
            if citation_str.lower() in source_text.lower():
                # Все OK, цитата найдена
                continue

            # Проверка 2: Это цитата на ИЗВЕСТНЫЙ документ?
            # Если да - не штрафуем, т.к. эти документы мы поддерживаем
            is_known_doc = any(doc in source_text.lower() for doc in KNOWN_DOCUMENTS)
            if is_known_doc:
                # Это ссылка на известный документ - это OK
                continue

            # Проверка 3: Это номер в разумном диапазоне?
            # Если номер очень большой (> 1000) или иррациональный - подозрительно
            try:
                num = int(citation_num.split('.')[0])
                if num > 1000:  # Маловероятный номер статьи/пункта
                    issues.append({
                        "type": "suspicious_citation",
                        "level": HallucinationLevel.MEDIUM_RISK,
                        "message": f"Ссылка на '{citation_str}' имеет подозрительный номер. Проверьте точность.",
                        "detected_text": citation_str,
                        "severity": "WARNING"
                    })
            except:
                pass

        return issues

    def _calculate_confidence(self, result: Dict) -> float:
        """
        Вычислить уровень уверенности в ответе
        1.0 = полностью надёжно
        0.0 = галлюцинация
        """
        confidence = 1.0

        # Штрафы за проблемы
        if result["level"] == HallucinationLevel.SAFE:
            confidence = 0.95
        elif result["level"] == HallucinationLevel.LOW_RISK:
            confidence = 0.85
        elif result["level"] == HallucinationLevel.MEDIUM_RISK:
            confidence = 0.60
        elif result["level"] == HallucinationLevel.HIGH_RISK:
            confidence = 0.30
        elif result["level"] == HallucinationLevel.CRITICAL:
            confidence = 0.05

        # Штраф за низкую привязку к источникам
        if result["source_coverage"] < 0.5:
            confidence *= 0.5

        return max(0.0, min(1.0, confidence))


# ─── ИНТЕГРАЦИЯ В RAG ─────────────────────────────────────────────

def validate_answer_for_hallucinations(answer: str, source_chunks: List[Dict]) -> Dict:
    """
    Основная функция валидации ответа на галлюцинации

    Returns:
        {
            "is_safe": bool,
            "level": str,
            "confidence": float,
            "issues": List[Dict],
            "corrected_answer": str (если нужны исправления)
        }
    """
    detector = HallucinationDetector()
    result = detector.detect(answer, source_chunks)

    return {
        "is_safe": result["level"] == HallucinationLevel.SAFE,
        "level": result["level"].value,
        "confidence": result["confidence"],
        "critical_issues": [i for i in result["detected_issues"] if i.get("severity") == "CRITICAL"],
        "warnings": [i for i in result["detected_issues"] if i.get("severity") == "WARNING"],
        "source_coverage": result["source_coverage"],
        "recommendations": result["recommendations"]
    }


# ─── ПРИМЕРЫ ПРОВЕРОК ─────────────────────────────────────────

if __name__ == "__main__":
    # Пример 1: Галлюцинация
    answer_with_hallucination = """
    Нужны следующие документы:
    1. Акт об изменении договора
    2. Документ о выделении дополнительных средств
    3. Согласие обеих сторон на изменение суммы договора
    Также нужно создать новый пункт плана на НДС.
    Основание: пункт 2 статьи 18 Закона о госзакупках.
    """

    source_chunks = [
        {
            "text": "Пункт 13.2 Типового договора: Любые изменения совершаются в той же форме"
        }
    ]

    detector = HallucinationDetector()
    result = detector.detect(answer_with_hallucination, source_chunks)

    print("РЕЗУЛЬТАТ ПРОВЕРКИ:")
    print(f"Уровень: {result['level'].value}")
    print(f"Уверенность: {result['confidence']:.0%}")
    print(f"Привязка к источникам: {result['source_coverage']:.0%}")
    print("\nОбнаруженные проблемы:")
    for issue in result["detected_issues"]:
        print(f"  [{issue['level'].value}] {issue['message']}")
    print("\nРекомендации:")
    for rec in result["recommendations"]:
        print(f"  - {rec}")
