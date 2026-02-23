"""
Test platform detection - pokazat' как бот razlichaet goszakup vs omarket
"""
import sys
sys.path.insert(0, '.')
from rag import detect_platform

test_questions = [
    # Javnie nazvanija (vysshij prioritet)
    ("Kак загрузить документы на omarket?", "omarket", "Explicit name"),
    ("Как работать с goszakup?", "goszakup", "Explicit name"),
    ("omarket vs goszakup - kakaja raznica?", None, "Both named"),
    
    # Kontekstnie triggery
    ("Как разместить товар через электронный магазин?", "omarket", "Context: e-shop"),
    ("Как добавить товар в прайс-лист?", "omarket", "Context: price list"),
    ("Как создать объявление о закупке?", "goszakup", "Context: procurement"),
    ("Как подать ценовое предложение?", "goszakup", "Context: price offer"),
    
    # Neodnosnachnye (PROBLEMNYE!)
    ("Как загрузить документы?", None, "AMBIGUOUS: both have uploads"),
    ("Как зарегистрироваться?", "goszakup", "goszakup has 'registracija'"),
    ("Как создать аккаунт?", None, "AMBIGUOUS: no triggers"),
    ("Как подать заявку?", "goszakup", "goszakup has 'zajavka'"),
    ("Как работать с каталогом?", "omarket", "omarket has 'katalog'"),
    
    # Real'nye neodnosnachnye voprosy
    ("Как загрузить файлы на портал?", None, "Vague - either platform"),
    ("Что делать если не удалось загрузить документ?", None, "Vague problem"),
]

print("PLATFORM DETECTION TEST")
print("="*70)

ambiguous_count = 0
for question, expected, reason in test_questions:
    detected = detect_platform(question)
    status = "[OK]" if detected == expected else "[AMBIG]"
    if detected != expected:
        ambiguous_count += 1
    print(f"{status} {question}")
    print(f"    Expected: {expected:10s} Got: {detected}")

print(f"\n{'='*70}")
print(f"RESULT: {ambiguous_count} ambiguous/uncertain detections")
