#!/usr/bin/env python3
"""
Quick Phase 4 test - Single sample question for each secondary conflict type
"""

import sys
sys.path.insert(0, '.')

from rag import answer_question

# Quick validation tests
tests = [
    {
        "name": "Secondary 1: EDS Exceptions (Foreign docs)",
        "question": "Можно ли требовать ЭЦП для документов об иностранной регистрации компании?",
        "expected": ["КОНФЛИКТ НОРМ", "WARNING", "пункт 40"]
    },
    {
        "name": "Secondary 2: Discrimination (Multiple certifications)",
        "question": "Можно ли требовать одновременно ISO 9001, 14001 И 45001 как условие участия в закупке на 500 000 тенге?",
        "expected": ["КОНФЛИКТ НОРМ", "WARNING", "статья 9"]
    }
]

print("=" * 80)
print("QUICK PHASE 4 SECONDARY CONFLICTS VALIDATION")
print("=" * 80)

passed = 0
failed = 0

for test in tests:
    print(f"\n[Test] {test['name']}")
    print(f"Q: {test['question']}")

    try:
        answer, chunk_count, _ = answer_question(test['question'], [])

        # Check for expected markers
        found_markers = sum(1 for marker in test['expected'] if marker.lower() in answer.lower())

        if found_markers >= 2:  # At least 2 markers found
            print(f"[PASS] {found_markers}/{len(test['expected'])} markers detected")
            print(f"       Answer length: {len(answer)} chars")
            # Safe preview that handles encoding
            try:
                preview = answer.replace('\n', ' ')[:100].encode('ascii', 'ignore').decode('ascii')
                if preview:
                    print(f"       Preview: {preview}...")
            except:
                print(f"       (preview encoding error - but answer is valid)")
            passed += 1
        else:
            print(f"[FAIL] Only {found_markers}/{len(test['expected'])} markers detected")
            missing = [m for m in test['expected'] if m.lower() not in answer.lower()]
            print(f"       Missing: {missing}")
            failed += 1

    except Exception as e:
        print(f"[ERROR] {str(e)[:80]}")
        failed += 1

print(f"\n{'=' * 80}")
print(f"RESULTS: {passed}/{len(tests)} passed ({100*passed//len(tests)}%)")
print(f"{'=' * 80}")

if passed == len(tests):
    print("[OK] Phase 4 secondary conflicts working correctly!")
else:
    print(f"[WARN] {failed} tests failed - check implementations")
