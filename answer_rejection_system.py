"""
Answer Rejection System для Goszakup Bot
Отклоняет ненадежные ответы и предлагает вместо них помощь по проверяемым вопросам

Решение проблемы: Бот давал неточные ответы вместо того, чтобы отказаться от ответа
Цель: 100% точность только из проверенной базы знаний
"""

from enum import Enum
from dataclasses import dataclass
from typing import Tuple, Optional


class AnswerReliability(Enum):
    """Уровни надежности ответа"""
    HIGHLY_RELIABLE = "highly_reliable"      # >= 0.85
    RELIABLE = "reliable"                    # 0.70-0.84
    QUESTIONABLE = "questionable"            # 0.50-0.69
    UNRELIABLE = "unreliable"                # < 0.50


@dataclass
class RejectionReason:
    """Причина отклонения ответа"""
    reason_code: str
    description: str
    confidence_score: float
    recommendation: str


class AnswerRejectionSystem:
    """
    Система отклонения ненадежных ответов

    Правила:
    1. Если confidence < 0.50 → ОТКЛОНИТЬ
    2. Если обнаружены critical hallucinations → ОТКЛОНИТЬ
    3. Если сценарий требует специализированной консультации → ОТКЛОНИТЬ
    4. Если множественные противоречивые интерпретации → ОТКЛОНИТЬ
    """

    # Пороги принятия ответов
    MINIMUM_CONFIDENCE = 0.50
    MEDIUM_CONFIDENCE = 0.70
    HIGH_CONFIDENCE = 0.85

    # Сценарии, требующие отказа (даже при высокой confidence)
    CONSULTATION_REQUIRED_SCENARIOS = {
        "vat_amendment": {
            "keywords": ["НДС", "добавление НДС", "договор без НДС"],
            "reason": "Требует анализа конкретной бюджетной ситуации",
            "department": "Финансовый отдел + Уполномоченный орган"
        },
        "contract_modification": {
            "keywords": ["изменение договора", "существенные условия", "изменение суммы"],
            "reason": "Требует обоснования соответствия пункту 2 ст.18 Закона",
            "department": "Юридический отдел + Организатор закупок"
        },
        "procurement_rules_ambiguity": {
            "keywords": ["может быть", "возможно", "вероятно", "предположительно"],
            "reason": "Содержит предположения вместо четких норм",
            "department": "Уполномоченный орган по госзакупкам"
        }
    }

    @staticmethod
    def should_reject_answer(
        answer: str,
        confidence: float,
        has_critical_issues: bool,
        is_multiple_interpretations: bool,
        source_coverage: float
    ) -> Tuple[bool, Optional[RejectionReason]]:
        """
        Определить, нужно ли отклонить ответ

        Args:
            answer: Текст ответа от бота
            confidence: Уровень уверенности (0.0-1.0)
            has_critical_issues: Есть ли критические проблемы (галлюцинации)
            is_multiple_interpretations: Несколько противоречивых интерпретаций
            source_coverage: Процент покрытия источниками (0.0-1.0)

        Returns:
            (should_reject: bool, reason: RejectionReason or None)
        """

        # ПРАВИЛО 1: Низкая confidence → ОТКЛОНИТЬ
        if confidence < AnswerRejectionSystem.MINIMUM_CONFIDENCE:
            return True, RejectionReason(
                reason_code="LOW_CONFIDENCE",
                description=f"Уверенность в ответе только {confidence:.0%}",
                confidence_score=confidence,
                recommendation="Переформулируйте вопрос или проконсультируйтесь с профильным органом"
            )

        # ПРАВИЛО 2: Критические проблемы (галлюцинации) → ОТКЛОНИТЬ
        if has_critical_issues:
            return True, RejectionReason(
                reason_code="CRITICAL_HALLUCINATIONS",
                description="Обнаружены выдуманные нормы или документы",
                confidence_score=confidence,
                recommendation="Используйте источники, указанные в справочнике /docs"
            )

        # ПРАВИЛО 3: Множественные противоречивые интерпретации → ОТКЛОНИТЬ
        if is_multiple_interpretations:
            return True, RejectionReason(
                reason_code="MULTIPLE_INTERPRETATIONS",
                description="Ответ содержит несколько противоречивых вариантов",
                confidence_score=confidence,
                recommendation="Вопрос требует консультации со специалистом"
            )

        # ПРАВИЛО 4: Низкое покрытие источниками → ОТКЛОНИТЬ
        if source_coverage < 0.70:
            return True, RejectionReason(
                reason_code="INSUFFICIENT_SOURCE_COVERAGE",
                description=f"Только {source_coverage:.0%} ответа основано на источниках",
                confidence_score=confidence,
                recommendation="Результаты поиска неполные. Проверьте источники вручную"
            )

        # Если все проверки пройдены
        return False, None

    @staticmethod
    def get_rejection_message(reason: RejectionReason) -> str:
        """
        Сгенерировать пользовательское сообщение об отклонении

        Args:
            reason: Причина отклонения

        Returns:
            Форматированное сообщение для пользователя
        """

        messages = {
            "LOW_CONFIDENCE": f"""
[WARNING] НЕТОЧНЫЙ ОТВЕТ - ТРЕБУЕТСЯ КОНСУЛЬТАЦИЯ

Причина: {reason.description}

К сожалению, я не могу дать надежный ответ на этот вопрос, так как уверенность
только {reason.confidence_score:.0%}. Это означает, что ответ содержит предположения,
а не точные нормы.

РЕКОМЕНДАЦИЯ: {reason.recommendation}

[TIP] Совет: Попробуйте переформулировать вопрос, указав:
- Конкретный пункт нормативного документа
- Конкретный сценарий (например: "договор на сумму X без НДС")
- Конкретный источник документа

[LINK] Справочник: Используйте /docs для ссылок на официальные источники
""",

            "CRITICAL_HALLUCINATIONS": f"""
[ERROR] ОБНАРУЖЕНЫ ОШИБКИ В ОТВЕТЕ - ОТВЕТ ОТКЛОНЕН

Причина: {reason.description}

В моем предыдущем ответе были упомянуты документы или нормы,
которые НЕ существуют в законодательстве РК.

РЕКОМЕНДАЦИЯ: {reason.recommendation}

[IMPORTANT] ВАЖНО: Не полагайтесь на этот ответ!

Обратитесь к официальным источникам:
[DOCS] https://adilet.zan.kz/ - Законодательство РК
[DOCS] https://wiki.omarket.kz/ - Инструкции Omarket
[DOCS] https://wiki.goszakup.gov.kz/ - Инструкции Goszakup
""",

            "MULTIPLE_INTERPRETATIONS": f"""
[UNCLEAR] НЕОДНОЗНАЧНЫЙ ОТВЕТ - ТРЕБУЕТСЯ КОНСУЛЬТАЦИЯ

Причина: {reason.description}

Ваш вопрос имеет несколько возможных толкований в зависимости от вашей
конкретной ситуации. Я не могу выбрать один правильный вариант без
дополнительной информации.

РЕКОМЕНДАЦИЯ: {reason.recommendation}

Уточните следующее и задайте вопрос снова:
- Конкретная ситуация (пример, цифры, даты)
- Какой документ вас интересует (договор, план закупок и т.д.)
- Какой именно шаг вас затрудняет

[CONTACT] Если остаются вопросы: обратитесь к уполномоченному органу по госзакупкам
""",

            "INSUFFICIENT_SOURCE_COVERAGE": f"""
[DATA] ОТВЕТ НА ОСНОВЕ НЕПОЛНЫХ ИСТОЧНИКОВ - ОТКЛОНЕН

Причина: {reason.description}

Поиск в базе знаний дал неполные результаты. Это может означать, что:
- Вопрос покрывается не нормативными документами, а специальными инструкциями
- Вопрос требует анализа сразу нескольких нормативных актов

РЕКОМЕНДАЦИЯ: {reason.recommendation}

Попробуйте:
1. Переформулировать вопрос более конкретно
2. Указать, какой документ вас интересует (закон, договор, инструкция)
3. Обратиться к официальному справочнику /docs
"""
        }

        return messages.get(reason.reason_code, str(reason.description))

    @staticmethod
    def detect_multiple_interpretations(answer: str) -> bool:
        """
        Определить, содержит ли ответ несколько противоречивых вариантов

        Признаки:
        - "Вариант 1...", "Вариант 2..."
        - "Возможно...", "Может быть..."
        - "С одной стороны...", "С другой стороны..."
        """

        patterns = [
            "вариант 1",
            "вариант 2",
            "возможно",
            "может быть",
            "с одной стороны",
            "с другой стороны",
            "либо",
            "либо",
            "или",
            "⚠️ вариант",
            "предположительно"
        ]

        answer_lower = answer.lower()
        variant_count = sum(1 for pattern in patterns if pattern in answer_lower)

        # Если найдено 3+ признака неоднозначности → это "множественные интерпретации"
        return variant_count >= 3


# ПРИМЕР ИСПОЛЬЗОВАНИЯ В RAG PIPELINE
def process_answer_with_rejection(
    question: str,
    answer: str,
    validation_result: dict,  # Из hallucination_prevention.validate_answer_for_hallucinations()
    source_chunks: list
) -> Tuple[str, bool]:
    """
    Обработать ответ с проверкой на отклонение

    Args:
        question: Вопрос пользователя
        answer: Ответ от Claude
        validation_result: Результат валидации (из hallucination_prevention.py)
        source_chunks: Список использованных chunks

    Returns:
        (final_answer: str, was_accepted: bool)
    """

    # Подготовить параметры
    confidence = validation_result.get("confidence", 0.0)
    has_critical = len(validation_result.get("critical_issues", [])) > 0
    is_multiple = AnswerRejectionSystem.detect_multiple_interpretations(answer)
    source_coverage = validation_result.get("source_coverage", 0.0)

    # Проверить, нужно ли отклонить
    should_reject, reason = AnswerRejectionSystem.should_reject_answer(
        answer=answer,
        confidence=confidence,
        has_critical_issues=has_critical,
        is_multiple_interpretations=is_multiple,
        source_coverage=source_coverage
    )

    if should_reject:
        # ОТКЛОНИТЬ ответ и показать сообщение об отклонении
        rejection_message = AnswerRejectionSystem.get_rejection_message(reason)
        return rejection_message, False
    else:
        # ПРИНЯТЬ ответ (если нужно, добавить предупреждение)
        if confidence < 0.85:
            answer += f"\n\n⚠️ Примечание: Это ответ основан на {confidence:.0%} уверенности. " \
                     f"Проверьте источники если вопрос критически важен."

        return answer, True


if __name__ == "__main__":
    # ТЕСТ: Примерный ответ (как в примере пользователя)
    test_answer = """
    Ситуация с добавлением НДС к уже заключённому договору без НДС

    Возможные варианты:
    ⚠️ Вариант 1 (вероятно правильный): Если НДС — это новые/дополнительные средства, то может потребоваться новая закупка (новый пункт плана) для НДС.
    ⚠️ Вариант 2: Если средства на НДС в составе переквалификации бюджета, возможна корректировка договора с обоснованием соответствия пункту 2 статьи 18 Закона.

    Рекомендация: Уточните у вашего уполномоченного органа...
    """

    test_validation = {
        "confidence": 0.15,
        "critical_issues": [
            {"message": "Новый пункт плана НЕ нужен, это одна закупка"},
            {"message": "Проверьте наличие пункта 2 ст.18 в Законе"}
        ],
        "source_coverage": 0.35,
        "warnings": []
    }

    # Проверить
    should_reject, reason = AnswerRejectionSystem.should_reject_answer(
        answer=test_answer,
        confidence=test_validation["confidence"],
        has_critical_issues=len(test_validation["critical_issues"]) > 0,
        is_multiple_interpretations=AnswerRejectionSystem.detect_multiple_interpretations(test_answer),
        source_coverage=test_validation["source_coverage"]
    )

    print("="*80)
    print("ТЕСТ: Анализ ответа бота")
    print("="*80)
    print(f"\nВопрос пользователя: Договор без НДС + новые средства на НДС = нужен новый пункт плана?")
    print(f"\nОтвет бота ОТКЛОНЕН? {should_reject}")

    if should_reject:
        print(f"Причина отклонения: {reason.reason_code}")
        print(f"Описание: {reason.description}")
        print(f"Confidence: {reason.confidence_score:.0%}")
        print(f"\nСообщение пользователю:")
        print(AnswerRejectionSystem.get_rejection_message(reason))
    else:
        print("❌ ОШИБКА: Ответ должен был быть отклонен!")
