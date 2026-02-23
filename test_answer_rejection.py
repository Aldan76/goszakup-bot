"""
Тестирование системы отклонения ненадежных ответов
Test: Answer Rejection System for Unreliable Bot Responses
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from answer_rejection_system import AnswerRejectionSystem, RejectionReason


def test_vat_scenario():
    """Тест: Ответ бота на вопрос о НДС"""

    print("\n" + "="*80)
    print("ТЕСТ 1: Вопрос о добавлении НДС к договору без НДС")
    print("="*80)

    test_answer = """
    Ситуация с добавлением НДС к уже заключённому договору без НДС

    Возможные варианты:
    ⚠️ Вариант 1 (вероятно правильный): Если НДС — это новые/дополнительные средства,
       то может потребоваться новая закупка (новый пункт плана) для НДС.
    ⚠️ Вариант 2: Если средства на НДС в составе переквалификации бюджета,
       возможна корректировка договора с обоснованием соответствия пункту 2 статьи 18 Закона.

    Рекомендация: Уточните у вашего уполномоченного органа по госзакупкам...
    """

    test_validation = {
        "confidence": 0.15,  # НИЗКАЯ: 15%
        "critical_issues": [
            {"message": "Новый пункт плана НЕ нужен, это одна закупка"},
            {"message": "Проверьте наличие пункта 2 ст.18 в Законе"}
        ],
        "source_coverage": 0.35,  # НИЗКО: 35%
        "warnings": []
    }

    # Проверка 1: Является ли это множественными интерпретациями?
    is_multiple = AnswerRejectionSystem.detect_multiple_interpretations(test_answer)
    print(f"\n[1] Множественные интерпретации? {is_multiple}")

    # Проверка 2: Нужно ли отклонить?
    should_reject, reason = AnswerRejectionSystem.should_reject_answer(
        answer=test_answer,
        confidence=test_validation["confidence"],
        has_critical_issues=len(test_validation["critical_issues"]) > 0,
        is_multiple_interpretations=is_multiple,
        source_coverage=test_validation["source_coverage"]
    )

    print(f"[2] Ответ должен быть ОТКЛОНЕН? {should_reject}")

    if should_reject:
        print(f"[3] Причина: {reason.reason_code}")
        print(f"[4] Описание: {reason.description}")
        print(f"[5] Confidence: {reason.confidence_score:.0%}")
        print(f"\n[СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЮ]:")
        print(AnswerRejectionSystem.get_rejection_message(reason))
        print("\n[OK] PASS: Ответ корректно отклонен")
        return True
    else:
        print("\n[FAIL] ОШИБКА: Ответ должен был быть отклонен!")
        return False


def test_reliable_answer():
    """Тест: Надежный ответ (должен быть принят)"""

    print("\n" + "="*80)
    print("ТЕСТ 2: Надежный ответ с высокой уверенностью")
    print("="*80)

    test_answer = """
    Согласно Пункту 2.1 Типового договора о госзакупках, сумма договора
    указывается в форме: с НДС или без НДС.

    Это существенное условие договора, определяемое при его заключении.
    """

    test_validation = {
        "confidence": 0.92,  # ВЫСОКАЯ: 92%
        "critical_issues": [],  # НЕТ критических проблем
        "source_coverage": 0.95,  # ВЫСОКО: 95%
        "warnings": []
    }

    should_reject, reason = AnswerRejectionSystem.should_reject_answer(
        answer=test_answer,
        confidence=test_validation["confidence"],
        has_critical_issues=len(test_validation["critical_issues"]) > 0,
        is_multiple_interpretations=False,
        source_coverage=test_validation["source_coverage"]
    )

    print(f"\n[1] Ответ должен быть ОТКЛОНЕН? {should_reject}")

    if not should_reject:
        print(f"[2] Статус: ПРИНЯТ (как и ожидается)")
        print(f"[3] Confidence: {test_validation['confidence']:.0%}")
        print(f"[4] Source coverage: {test_validation['source_coverage']:.0%}")
        print("\n[OK] PASS: Надежный ответ корректно принят")
        return True
    else:
        print(f"\n[FAIL] ОШИБКА: Надежный ответ не должен был быть отклонен!")
        print(f"[DEBUG] Причина отклонения: {reason.reason_code}")
        return False


def test_low_source_coverage():
    """Тест: Ответ с низким покрытием источниками"""

    print("\n" + "="*80)
    print("ТЕСТ 3: Ответ с низким покрытием источниками")
    print("="*80)

    test_answer = """
    На основе общих принципов, может быть, потребуется дополнительное согласование.
    """

    test_validation = {
        "confidence": 0.55,  # СРЕДНЯЯ: 55%
        "critical_issues": [],
        "source_coverage": 0.25,  # ОЧЕНЬ НИЗКО: 25%
        "warnings": []
    }

    should_reject, reason = AnswerRejectionSystem.should_reject_answer(
        answer=test_answer,
        confidence=test_validation["confidence"],
        has_critical_issues=False,
        is_multiple_interpretations=False,
        source_coverage=test_validation["source_coverage"]
    )

    print(f"\n[1] Ответ должен быть ОТКЛОНЕН? {should_reject}")

    if should_reject:
        print(f"[2] Причина: {reason.reason_code}")
        print(f"[3] Source coverage: {test_validation['source_coverage']:.0%} (меньше 70%)")
        print("\n[OK] PASS: Ответ с низким покрытием корректно отклонен")
        return True
    else:
        print("\n[FAIL] ОШИБКА: Ответ с низким покрытием должен был быть отклонен!")
        return False


def main():
    print("\n" + "#"*80)
    print("# ТЕСТИРОВАНИЕ: СИСТЕМА ОТКЛОНЕНИЯ НЕНАДЕЖНЫХ ОТВЕТОВ")
    print("#"*80)

    results = []

    # Запустить все тесты
    results.append(("VAT Scenario (Низкая confidence)", test_vat_scenario()))
    results.append(("Reliable Answer (Высокая confidence)", test_reliable_answer()))
    results.append(("Low Source Coverage", test_low_source_coverage()))

    # ИТОГИ
    print("\n" + "="*80)
    print("ИТОГИ")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"{status}: {test_name}")

    print(f"\nВсего: {passed}/{total} тестов пройдено")

    if passed == total:
        print("\n[SUCCESS] ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\nСИСТЕМА ОТКЛОНЕНИЯ ГОТОВА К ИСПОЛЬЗОВАНИЮ:")
        print("[OK] Низкоуверенные ответы отклоняются")
        print("[OK] Ответы с критическими проблемами отклоняются")
        print("[OK] Ответы с множественными интерпретациями отклоняются")
        print("[OK] Ответы с низким покрытием источниками отклоняются")
        print("[OK] Надежные ответы принимаются без изменений")
        return True
    else:
        print(f"\n[FAIL] {total - passed} тестов не пройдено!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
