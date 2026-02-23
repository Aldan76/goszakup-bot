#!/usr/bin/env python3
"""
Phase 4 testing for SECONDARY conflicting norms detection
Tests the two new conflict types: электронная_подпись_vs_исключения and дискриминация
"""

import sys
sys.path.insert(0, '.')

from rag import answer_question

# Test cases for secondary conflict types
test_suites = {
    "электронная_подпись_vs_исключения": {
        "description": "Type 4 (SECONDARY): Electronic Signature vs Exceptions (Foreign docs, special forms)",
        "expected_markers": ["КОНФЛИКТ НОРМ", "иностранный", "исключение", "закон об эцп"],
        "tests": [
            {
                "question": "Можно ли требовать электронную подпись для документов об иностранной регистрации компании?",
                "context": "Поставщик из соседней страны предоставляет документы местной регистрации"
            },
            {
                "question": "Правомерно ли заказчик требует ЭЦП для завещания как доказательства правовой способности наследника?",
                "context": "Завещание по законодательству требует нотариального удостоверения, не ЭЦП"
            },
            {
                "question": "Нарушает ли требование ЭЦП Закон об электронной цифровой подписи если документ выдан иностранным государством?",
                "context": "Международные операции с документами, выданными другой страной"
            },
            {
                "question": "Что делать если в конкурсной документации требуется ЭЦП для всех документов, включая договор дарения недвижимости?",
                "context": "Конфликт между пунктом 40 (ЭЦП) и исключениями Закона об ЭЦП"
            },
            {
                "question": "Можно ли требовать электронную подпись для документа о праве собственности на земельный участок?",
                "context": "Документ содержит информацию о недвижимом имуществе"
            }
        ]
    },
    "дискриминация_полный_анализ": {
        "description": "Type 5 (SECONDARY): Comprehensive Discrimination Analysis",
        "expected_markers": ["КОНФЛИКТ НОРМ", "дискриминация", "статья 9", "барьер"],
        "tests": [
            {
                "question": "Можно ли требовать одновременно ISO 9001, ISO 14001, ISO 45001 И OHSAS 18001 как условие участия в закупке на сумму 500 000 тенге?",
                "context": "Множественные требования аккредитации для малой закупки, дискриминируют МСП"
            },
            {
                "question": "Нарушает ли недискриминационный принцип требование 'опыт работы на аналогичных проектах минимум 15 лет'?",
                "context": "Требование исключает молодые компании с опытными специалистами"
            },
            {
                "question": "Правомерно ли требование о том что все члены команды проекта должны быть зарегистрированы в городе Алматы?",
                "context": "Косвенная географическая дискриминация по месту нахождения"
            },
            {
                "question": "Можно ли заказчику требовать минимум 500 сотрудников как условие участия в закупке консалтинговых услуг?",
                "context": "Требование касается размера компании, а не компетенции или возможности выполнить контракт"
            },
            {
                "question": "Является ли дискриминационным требование 'Участник должен быть членом ассоциации X (не упомянутой в пунктах 40-42)'?",
                "context": "Скрытое требование членства в организации вне исчерпывающего перечня оснований"
            },
            {
                "question": "Нарушает ли статью 9 требование 'Компания должна быть зарегистрирована до 2015 года'?",
                "context": "Это исключает молодые компании несвязанным с компетенцией образом"
            },
            {
                "question": "Можно ли требовать 'Только компании зарегистрированные как АО (не ООО и не ИП)' без объяснения причин?",
                "context": "Требование по форме собственности без связи с компетенцией"
            }
        ]
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 80)
print("PHASE 4 SECONDARY CONFLICTS TEST SUITE")
print("Testing: электронная_подпись_vs_исключения + дискриминация (ПОЛНЫЙ АНАЛИЗ)")
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
    success_rate = 100 * suite_passed // len(suite['tests']) if len(suite['tests']) > 0 else 0
    print(f"Success rate: {suite_passed}/{len(suite['tests'])} ({success_rate}%)")

    overall_passed += suite_passed
    overall_failed += suite_failed
    overall_errors += suite_errors

# Results section
print(f"\n{'=' * 80}")
print("OVERALL RESULTS - PHASE 4 SECONDARY CONFLICTS")
print(f"{'=' * 80}")

total_tests = overall_passed + overall_failed + overall_errors
success_rate = 100 * overall_passed // total_tests if total_tests > 0 else 0

print(f"\nPASSED:  {overall_passed}")
print(f"FAILED:  {overall_failed}")
print(f"ERRORS:  {overall_errors}")
print(f"TOTAL:   {total_tests}")
print(f"\nSuccess Rate: {success_rate}%")

if success_rate >= 80:
    print(f"\n[OK] Phase 4 SECONDARY Conflicts Testing PASSED")
    print(f"     Both secondary conflict types detected correctly in {overall_passed} cases")
elif success_rate >= 60:
    print(f"\n[WARN] Phase 4 SECONDARY Testing PARTIALLY PASSED")
    print(f"     {overall_failed} tests failed - needs investigation")
else:
    print(f"\n[FAIL] Phase 4 SECONDARY Testing FAILED")
    print(f"     Only {success_rate}% success rate - needs fixes")

print(f"\n{'=' * 80}")
