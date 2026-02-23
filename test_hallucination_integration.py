#!/usr/bin/env python3
"""
Тестирование интеграции системы предотвращения галлюцинаций в RAG
Проверяет, что система ловит конкретные примеры, которые пользователь reported
"""

import sys
sys.stdout.recoding = 'utf-8'

from hallucination_prevention import (
    HallucinationDetector,
    HallucinationLevel,
    validate_answer_for_hallucinations
)

# ─── ПРИМЕРЫ ГАЛЛЮЦИНАЦИЙ, КОТОРЫЕ ПОЛЬЗОВАТЕЛЬ REPORTED ───────────────────

def test_user_reported_hallucination():
    """
    КРИТИЧЕСКИЙ ПРИМЕР: Пользователь сказал, что бот выдал:
    "Нужны следующие документы:
    1. Акт об изменении договора
    2. Документ о выделении дополнительных средств
    3. Согласие обеих сторон на изменение суммы договора"

    ПРАВИЛЬНЫЙ ОТВЕТ: Нужно только дополнительное соглашение
    """
    print("\n" + "="*80)
    print("TEST 1: КРИТИЧЕСКИЙ ПРИМЕР - Галлюцинация про документы")
    print("="*80)

    # Галлюцинирующий ответ, который выдал бот
    hallucinating_answer = """
Нужны следующие документы:
1. Акт об изменении договора - Документ, который составляется для фиксации внесённых изменений
2. Документ о выделении дополнительных средств - Подтверждение того, что заказчик выделил дополнительные средства
3. Согласие обеих сторон на изменение - Письменное согласие обеих сторон договора на изменение условий

Только после подготовки этих трёх документов можно приступать к изменению договора.
    """

    # Чанки источников (из реальной базы)
    source_chunks = [
        {
            "id": "law_001",
            "text": "Изменения договора совершаются в той же форме, что и договор. "
                    "Стороны должны подписать дополнительное соглашение.",
            "chapter": "Пункт 13.2 Типового договора",
            "source_platform": "law"
        }
    ]

    detector = HallucinationDetector()
    result = detector.detect(hallucinating_answer, source_chunks)

    print(f"\nУровень риска: {result['level'].value}")
    print(f"Уверенность: {result['confidence']:.0%}")
    print(f"Привязка к источникам: {result['source_coverage']:.0%}")

    print(f"\nОбнаруженные проблемы ({len(result['detected_issues'])} шт.):")
    for issue in result["detected_issues"]:
        print(f"\n[{issue['level'].value.upper()}] {issue['type']}")
        print(f"Сообщение: {issue['message']}")
        if 'detected_text' in issue:
            print(f"Обнаруженный текст: '{issue['detected_text']}'")

    print(f"\nРекомендации:")
    for rec in result["recommendations"]:
        print(f"  • {rec}")

    # ПРОВЕРКА УСПЕХА
    success = (
        result["level"] == HallucinationLevel.HIGH_RISK and
        len(result["detected_issues"]) >= 3 and
        result["confidence"] < 0.5
    )

    if success:
        print("\n[OK] PASS: Система корректно обнаружила галлюцинацию!")
    else:
        print("\n[FAIL] FAIL: Система не обнаружила галлюцинацию должным образом")

    return success


def test_correct_answer():
    """
    Проверяем, что корректный ответ не флагируется как галлюцинация
    """
    print("\n" + "="*80)
    print("TEST 2: Корректный ответ - НЕ должен флагируться как галлюцинация")
    print("="*80)

    correct_answer = """
Для изменения договора поставки необходимо подготовить дополнительное соглашение.

Согласно Пункту 13.2 Типового договора, изменения договора совершаются в той же форме,
что и договор. Дополнительное соглашение должно быть подписано обеими сторонами.

После подписания дополнительного соглашения все измененные условия вступают в силу и
становятся обязательными для исполнения.
    """

    source_chunks = [
        {
            "id": "law_001",
            "text": "Пункт 13.2 Типового договора: Изменения договора совершаются в той же форме что и договор",
            "chapter": "Типовой договор",
            "source_platform": "law"
        },
        {
            "id": "law_002",
            "text": "Дополнительное соглашение к договору подписывается обеими сторонами в соответствии с законом РК",
            "chapter": "Порядок изменения договора",
            "source_platform": "law"
        },
        {
            "id": "law_003",
            "text": "После подписания дополнительного соглашения все измененные условия вступают в силу",
            "chapter": "Вступление в силу изменений",
            "source_platform": "law"
        },
        {
            "id": "law_004",
            "text": "Измененные условия договора становятся обязательными для исполнения обеими сторонами",
            "chapter": "Обязательность изменений",
            "source_platform": "law"
        }
    ]

    detector = HallucinationDetector()
    result = detector.detect(correct_answer, source_chunks)

    print(f"\nУровень риска: {result['level'].value}")
    print(f"Уверенность: {result['confidence']:.0%}")
    print(f"Привязка к источникам: {result['source_coverage']:.0%}")

    if result["detected_issues"]:
        print(f"\nОбнаруженные проблемы ({len(result['detected_issues'])} шт.):")
        for issue in result["detected_issues"]:
            print(f"  [{issue['level'].value}] {issue['message']}")
    else:
        print(f"\nПроблем не обнаружено [OK]")

    # ПРОВЕРКА УСПЕХА
    # Корректный ответ не должен содержать красные флаги и должен иметь нет критических проблем
    has_red_flags = any(i['type'] == 'red_flag' for i in result['detected_issues'])
    success = (not has_red_flags) and len(result["detected_issues"]) <= 1

    if success:
        print("\n[OK] PASS: Корректный ответ не флагируется как галлюцинация!")
    else:
        print("\n[FAIL] FAIL: Корректный ответ ошибочно флагируется")

    return success


def test_partially_hallucinating_answer():
    """
    Ответ, который частично верен, но содержит неверные детали
    """
    print("\n" + "="*80)
    print("TEST 3: Частичная галлюцинация - Корректная информация + выдумка")
    print("="*80)

    partial_answer = """
Для изменения договора поставки нужно подготовить дополнительное соглашение.

Кроме того, обычно требуется акт об изменении договора и документ о выделении средств.

Дополнительное соглашение должно быть подписано обеими сторонами в соответствии с законом.
    """

    source_chunks = [
        {
            "id": "law_001",
            "text": "Дополнительное соглашение подписывается обеими сторонами",
            "chapter": "Изменения договора",
            "source_platform": "law"
        }
    ]

    detector = HallucinationDetector()
    result = detector.detect(partial_answer, source_chunks)

    print(f"\nУровень риска: {result['level'].value}")
    print(f"Уверенность: {result['confidence']:.0%}")
    print(f"Привязка к источникам: {result['source_coverage']:.0%}")

    print(f"\nОбнаруженные проблемы ({len(result['detected_issues'])} шт.):")
    for issue in result["detected_issues"]:
        severity = issue.get('severity', 'INFO')
        print(f"  [{severity}] {issue['type']}: {issue['message']}")

    # ПРОВЕРКА УСПЕХА
    has_red_flags = any(i['type'] == 'red_flag' for i in result['detected_issues'])
    has_uncertainty = any(i['type'] == 'uncertainty_indicator' for i in result['detected_issues'])

    success = has_red_flags and has_uncertainty

    if success:
        print("\n[OK] PASS: Система обнаружила и красные флаги И неуверенность!")
    else:
        print("\n[FAIL] FAIL: Система не полностью обнаружила проблемы")

    return success


def test_validate_answer_function():
    """
    Тестируем встроенную функцию validate_answer_for_hallucinations()
    которая используется в RAG
    """
    print("\n" + "="*80)
    print("TEST 4: Функция validate_answer_for_hallucinations()")
    print("="*80)

    answer = """
Нужны следующие документы для изменения договора:
1. Акт об изменении договора
2. Согласие обеих сторон на изменение
3. Документ о выделении средств
    """

    source_chunks = [
        {
            "id": "law_01",
            "text": "Изменения совершаются путем подписания дополнительного соглашения",
            "chapter": "Договорное право",
            "source_platform": "law"
        }
    ]

    validation = validate_answer_for_hallucinations(answer, source_chunks)

    print(f"\nis_safe: {validation['is_safe']}")
    print(f"level: {validation['level']}")
    print(f"confidence: {validation['confidence']:.0%}")
    print(f"source_coverage: {validation['source_coverage']:.0%}")

    print(f"\nCritical Issues ({len(validation['critical_issues'])} шт.):")
    for issue in validation["critical_issues"]:
        print(f"  - {issue['message']}")

    print(f"\nWarnings ({len(validation['warnings'])} шт.):")
    for warning in validation["warnings"]:
        print(f"  - {warning['message']}")

    # ПРОВЕРКА УСПЕХА
    success = (
        not validation["is_safe"] and
        validation["confidence"] < 0.6 and
        len(validation["critical_issues"]) > 0
    )

    if success:
        print("\n[OK] PASS: validate_answer_for_hallucinations() работает корректно!")
    else:
        print("\n[FAIL] FAIL: Функция валидации не работает должным образом")

    return success


def main():
    """Запустить все тесты"""
    print("\n")
    print("=" * 80)
    print(" " * 20 + "ТЕСТИРОВАНИЕ ПРЕДОТВРАЩЕНИЯ ГАЛЛЮЦИНАЦИЙ")
    print(" " * 20 + "Integration Test Suite")
    print("=" * 80)

    tests = [
        ("User Reported Hallucination", test_user_reported_hallucination),
        ("Correct Answer", test_correct_answer),
        ("Partial Hallucination", test_partially_hallucinating_answer),
        ("Validation Function", test_validate_answer_function),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n[ERROR] ERROR: {str(e)}")
            results.append((name, False))

    # ─── ИТОГОВАЯ СТАТИСТИКА ───────────────────────────────────────
    print("\n" + "="*80)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"  {status}: {name}")

    print(f"\nВсего: {passed}/{total} тестов пройдено")

    if passed == total:
        print("\n[SUCCESS] ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("Система предотвращения галлюцинаций работает корректно.")
        return 0
    else:
        print("\n[WARN] НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        return 1


if __name__ == "__main__":
    exit(main())
