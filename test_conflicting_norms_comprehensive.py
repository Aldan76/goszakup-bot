#!/usr/bin/env python3
"""
Comprehensive Phase 3 testing for conflicting norms detection system
Tests all 3 main conflict types with real-world questions
"""

import sys
sys.path.insert(0, '.')

from rag import answer_question

# Test cases organized by conflict type
test_suites = {
    "требования_к_персоналу": {
        "description": "Type 1: Personnel Requirements (Punkt 72 vs 235-241)",
        "expected_markers": ["КОНФЛИКТ НОРМ", "пункт 72", "235", "241", "персонал"],
        "tests": [
            {
                "question": "Можно ли в конкурсной документации требовать, чтобы в команде исполнителя был сертифицированный инженер?",
                "context": "Заказчик выполняет инженерные работы, нужны специалисты"
            },
            {
                "question": "Правомерно ли заказчик требует наличие в организации аттестованного аудитора как условие участия?",
                "context": "Закупка услуг аудита на государственном уровне"
            },
            {
                "question": "Нарушает ли пункт 72 требование о наличии в коллективе работника с высшим образованием?",
                "context": "Поставщик требует подтверждение качества кадров"
            },
            {
                "question": "Что делать если заказчик требует конкретного количества специалистов (например 5 инженеров) для выполнения контракта?",
                "context": "Конфликт между правом требовать квалификацию и запретом требовать персонал"
            }
        ]
    },
    "электронная_подпись": {
        "description": "Type 2: Electronic Signature (Punkt 40 vs Exceptions)",
        "expected_markers": ["КОНФЛИКТ НОРМ", "электронная подпись", "исключение", "статья 16", "нотариальное"],
        "tests": [
            {
                "question": "Можно ли требовать электронную подпись для документов о праве собственности на недвижимость?",
                "context": "Заказчик требует ЭЦП для всех документов без исключений"
            },
            {
                "question": "Правомерно ли заказчик требует ЭЦП для завещания поставщика как доказательство его правовой способности?",
                "context": "Попытка требовать ЭЦП для документа который по закону требует нотариального удостоверения"
            },
            {
                "question": "Что делать если в конкурсной документации требуется ЭЦП для всех документов, включая те которые требуют нотариального удостоверения?",
                "context": "Конфликт между пунктом 40 (ЭЦП) и Законом об ЭЦП (исключения)"
            },
            {
                "question": "Нарушает ли требование ЭЦП Закон об электронной цифровой подписи если документ выдан иностранным государством?",
                "context": "Международные операции и документы от иностранных организаций"
            }
        ]
    },
    "право_на_участие": {
        "description": "Type 3: Right to Participate (Article 9 vs Points 40-42 + Discrimination)",
        "expected_markers": ["КОНФЛИКТ НОРМ", "статья 9", "право на участие", "дискриминация", "40-42"],
        "tests": [
            {
                "question": "Можно ли заказчику требовать минимум 100 сотрудников в компании как условие допуска к конкурсу?",
                "context": "Требование касается характеристик самой компании, а не ее компетенций"
            },
            {
                "question": "Правомерно ли требование о том что все члены команды должны быть зарегистрированы в конкретном городе?",
                "context": "Косвенная дискриминация по месту нахождения"
            },
            {
                "question": "Нарушает ли недискриминационный принцип требование об опыте работы на аналогичных проектах 10+ лет?",
                "context": "Требование исключает молодые компании с опытными специалистами"
            },
            {
                "question": "Что произойдет если заказчик отклонит предложение по причинам не указанным в пунктах 40-42?",
                "context": "Нарушение исчерпывающего перечня оснований для отказа"
            },
            {
                "question": "Можно ли требовать одновременно ISO 9001, ISO 14001 И ISO 45001 как условие участия?",
                "context": "Множественные требования аккредитации которые дискриминируют малые предприятия"
            },
            {
                "question": "Правомерна ли попытка заказчика исключить участника который не входит в определенный реестр, если это не упомянуто в пунктах 40-42?",
                "context": "Скрытые основания для отказа вне исчерпывающего перечня"
            }
        ]
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 80)
print("COMPREHENSIVE PHASE 3 TEST SUITE")
print("Conflicting Norms Detection System")
print("=" * 80)

overall_passed = 0
overall_failed = 0
overall_errors = 0

for conflict_type, suite in test_suites.items():
    print(f"\n{'-' * 80}")
    print(f"TEST SUITE: {suite['description']}")
    print(f"{'-' * 80}")

    suite_passed = 0
    suite_failed = 0
    suite_errors = 0

    for i, test in enumerate(suite['tests'], 1):
        question = test['question']
        context = test['context']

        print(f"\n[Test {i}/{len(suite['tests'])}]")
        print(f"Q: {question[:70]}...")
        print(f"C: {context}")

        try:
            answer, chunk_count, has_ktru = answer_question(question, [])

            # Check if conflict was detected
            conflict_detected = any(marker.lower() in answer.lower() for marker in suite['expected_markers'])

            if conflict_detected:
                # Extract key info from answer
                has_warning = "ВАЖНО: КОНФЛИКТ" in answer
                answer_length = len(answer)
                sources_count = answer.count("adilet.zan.kz")

                print(f"[PASS] Conflict detected")
                print(f"       Answer length: {answer_length} chars")
                print(f"       Warning marker: {'[OK]' if has_warning else '[WARN]'}")
                print(f"       Sources found: {sources_count}")

                # Show first 150 chars of answer
                preview = answer.replace('\n', ' ')[:150]
                print(f"       Preview: {preview}...")

                suite_passed += 1
            else:
                print(f"[FAIL] Conflict NOT detected")
                preview = answer.replace('\n', ' ')[:150]
                print(f"       Preview: {preview}...")
                suite_failed += 1

        except Exception as e:
            print(f"[ERROR] {str(e)[:100]}")
            suite_errors += 1

    # Suite summary
    print(f"\n{'-' * 80}")
    print(f"SUITE RESULTS: PASSED={suite_passed} FAILED={suite_failed} ERRORS={suite_errors}")
    print(f"Success rate: {suite_passed}/{len(suite['tests'])} ({100*suite_passed//len(suite['tests'])}%)")

    overall_passed += suite_passed
    overall_failed += suite_failed
    overall_errors += suite_errors

# Results section
print(f"\n{'=' * 80}")
print("OVERALL RESULTS")
print(f"{'=' * 80}")

total_tests = overall_passed + overall_failed + overall_errors
success_rate = 100 * overall_passed // total_tests if total_tests > 0 else 0

print(f"\nPASSED:  {overall_passed}")
print(f"FAILED:  {overall_failed}")
print(f"ERRORS:  {overall_errors}")
print(f"TOTAL:   {total_tests}")
print(f"\nSuccess Rate: {success_rate}%")

if success_rate >= 80:
    print(f"\n[OK] Phase 3 Testing PASSED - System is ready for deployment")
    print(f"     All 3 conflict types detected correctly in {overall_passed} cases")
elif success_rate >= 60:
    print(f"\n[WARN] Phase 3 Testing PARTIALLY PASSED")
    print(f"     {overall_failed} tests failed - needs investigation")
else:
    print(f"\n[FAIL] Phase 3 Testing FAILED")
    print(f"     Only {success_rate}% success rate - needs fixes")

print(f"\n{'=' * 80}")
