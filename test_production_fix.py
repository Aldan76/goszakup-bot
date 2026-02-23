#!/usr/bin/env python3
"""
Тест для проверки production исправления (2026-02-23)
Валидирует что supplier contract question теперь будет принята

Проблема была: Bot отклонял "Поставщик не подписал договор в сроки" с "INSUFFICIENT_SOURCE_COVERAGE (60%)"
Решение: Снизили пороги MINIMUM_CONFIDENCE (0.35→0.25) и INSUFFICIENT_SOURCE_COVERAGE (0.70→0.50)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from answer_rejection_system import AnswerRejectionSystem


def test_production_scenario():
    """
    Тестировать production scenario: Supplier contract question с 60% coverage
    """
    print("\n" + "="*80)
    print("PRODUCTION ИСПРАВЛЕНИЕ ТЕСТ")
    print("="*80)

    print("\nСценарий: Вопрос о поставщике, не подписавшем договор")
    print("Production данные (из реального бота): confidence ~0.40, coverage 60%")

    # Имитация production данных
    test_cases = [
        {
            "name": "Production case: Supplier contract (coverage 60%)",
            "confidence": 0.40,
            "source_coverage": 0.60,
            "has_critical_issues": False,
            "is_multiple_interpretations": False,
            "expected_reject": False,  # Должен быть ПРИНЯТ
            "reason": "Даже с 60% coverage, с хорошей confidence и без критических проблем - должен быть принят"
        },
        {
            "name": "Boundary case: Coverage 50% (новый порог)",
            "confidence": 0.40,
            "source_coverage": 0.50,
            "has_critical_issues": False,
            "is_multiple_interpretations": False,
            "expected_reject": False,  # На пороге, должен быть ПРИНЯТ
            "reason": "Coverage точно на пороге 0.50, должен быть принят"
        },
        {
            "name": "Boundary case: Coverage 49% (ниже порога)",
            "confidence": 0.40,
            "source_coverage": 0.49,
            "has_critical_issues": False,
            "is_multiple_interpretations": False,
            "expected_reject": True,  # ОТКЛОНЕН
            "reason": "Coverage ниже порога 0.50, должен быть отклонен"
        },
        {
            "name": "Confidence boundary: 0.25 (новый минимум)",
            "confidence": 0.25,
            "source_coverage": 0.70,
            "has_critical_issues": False,
            "is_multiple_interpretations": False,
            "expected_reject": False,  # На пороге, должен быть ПРИНЯТ
            "reason": "Confidence точно на пороге 0.25, должен быть принят"
        },
        {
            "name": "Confidence boundary: 0.24 (ниже порога)",
            "confidence": 0.24,
            "source_coverage": 0.70,
            "has_critical_issues": False,
            "is_multiple_interpretations": False,
            "expected_reject": True,  # ОТКЛОНЕН
            "reason": "Confidence ниже порога 0.25, должен быть отклонен"
        },
        {
            "name": "Old threshold would reject: 60% coverage with 0.70 threshold",
            "confidence": 0.40,
            "source_coverage": 0.60,
            "has_critical_issues": False,
            "is_multiple_interpretations": False,
            "expected_reject": False,  # NEW: Принят с новым порогом 0.50
            "reason": "С новым порогом 0.50 - этот случай теперь ПРИНЯТ (было отклонено с 0.70)"
        }
    ]

    results = []

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'-'*80}")
        print(f"Тест {i}: {test['name']}")
        print(f"{'-'*80}")
        print(f"Параметры:")
        print(f"  confidence: {test['confidence']:.0%}")
        print(f"  source_coverage: {test['source_coverage']:.0%}")
        print(f"  has_critical_issues: {test['has_critical_issues']}")
        print(f"  is_multiple_interpretations: {test['is_multiple_interpretations']}")
        print(f"\nОжидаемый результат: {'ОТКЛОНЕН' if test['expected_reject'] else 'ПРИНЯТ'}")
        print(f"Причина: {test['reason']}")

        # Запустить проверку
        should_reject, reason = AnswerRejectionSystem.should_reject_answer(
            answer="Test answer",
            confidence=test['confidence'],
            has_critical_issues=test['has_critical_issues'],
            is_multiple_interpretations=test['is_multiple_interpretations'],
            source_coverage=test['source_coverage']
        )

        actual_result = "ОТКЛОНЕН" if should_reject else "ПРИНЯТ"
        expected_result = "ОТКЛОНЕН" if test['expected_reject'] else "ПРИНЯТ"

        print(f"\nАктуальный результат: {actual_result}")

        if should_reject:
            print(f"Причина отклонения: {reason.reason_code}")
            print(f"Описание: {reason.description}")

        # Проверить что результат совпадает
        test_passed = (should_reject == test['expected_reject'])

        if test_passed:
            print(f"[OK] PASS - Результат совпадает")
            results.append(True)
        else:
            print(f"[FAIL] FAIL - Ожидалось {expected_result}, получено {actual_result}")
            results.append(False)

    # Итоги
    print(f"\n{'='*80}")
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print(f"{'='*80}")

    passed = sum(1 for r in results if r)
    total = len(results)

    print(f"\nПройдено: {passed}/{total} тестов")

    if passed == total:
        print("\n[OK] ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\n[OK] PRODUCTION ИСПРАВЛЕНИЕ ГОТОВО:")
        print("  - MINIMUM_CONFIDENCE: 0.35 -> 0.25")
        print("  - INSUFFICIENT_SOURCE_COVERAGE: 0.70 -> 0.50")
        print("\n[OK] Supplier contract question теперь будет ПРИНЯТ (был отклонен)")
        print("  - Production confidence: ~0.40 [OK] (выше нового порога 0.25)")
        print("  - Production coverage: 60% [OK] (выше нового порога 50%)")
        return True
    else:
        print(f"\n[FAIL] {total - passed} тестов не пройдено!")
        return False


if __name__ == "__main__":
    success = test_production_scenario()

    print("\n" + "="*80)
    print("ФИНАЛЬНЫЙ СТАТУС")
    print("="*80)

    if success:
        print("\n[OK] PRODUCTION ИСПРАВЛЕНИЕ ВАЛИДИРОВАНО")
        print("\nСледующие шаги:")
        print("1. git add . && git commit -m 'Fix: Lower rejection thresholds for production'")
        print("2. git push origin main")
        print("3. Railway автоматически развернет обновления")
        print("4. Бот начнет принимать supplier contract questions с 60% coverage")
        sys.exit(0)
    else:
        print("\n[FAIL] Некоторые тесты не прошли")
        sys.exit(1)
