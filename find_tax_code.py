"""
find_tax_code.py — Найти актуальный код Налогового кодекса РК на adilet.zan.kz

Пробует известные коды и проверяет какой работает.
"""

import httpx
import re

def check_tax_code(code: str) -> bool:
    """Проверяет существует ли документ с таким кодом."""
    url = f"https://adilet.zan.kz/rus/docs/{code}"

    try:
        response = httpx.get(url, timeout=5, follow_redirects=True)

        # Если вернулось что-то кроме 404 и пустой страницы
        if response.status_code == 200:
            # Проверяем что это действительно Налоговый кодекс
            if "налоговый кодекс" in response.text.lower() or "tax code" in response.text.lower():
                return True
        return False
    except:
        return False


def main():
    print("=" * 70)
    print("SEARCH FOR TAX CODE ON ADILET.ZAN.KZ")
    print("=" * 70 + "\n")

    # Known possible codes for Tax Code
    possible_codes = [
        "K080000210_",      # Налоговый кодекс от 2008 г
        "K080000210",       # Без подчеркивания
        "K1700000210_",     # Возможно обновленная версия
        "K1700000210",
        "K190000210_",
        "K190000210",
        "K200000210_",
        "K200000210",
    ]

    print("Проверяю коды документов:\n")

    found_codes = []

    for code in possible_codes:
        print(f"  Checking {code:20}", end=" ... ")
        if check_tax_code(code):
            print("OK FOUND!")
            found_codes.append(code)
        else:
            print("NOT FOUND")

    print("\n" + "=" * 70)

    if found_codes:
        print(f"[SUCCESS] Found {len(found_codes)} versions of Tax Code:")
        for code in found_codes:
            print(f"   {code}: https://adilet.zan.kz/rus/docs/{code}")

        print(f"\nRecommended code: {found_codes[0]}")
        print(f"Update parse_tax_code.py line:")
        print(f'TAX_CODE_ID = "{found_codes[0]}"')
    else:
        print("[FAILED] Tax Code not found")
        print("\nTry searching at https://adilet.zan.kz/rus/search/docs")
        print("Check URL in browser - code will look like K...")


if __name__ == "__main__":
    main()
