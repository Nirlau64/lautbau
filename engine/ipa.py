"""IPA-Konvertierung: Englisches Wort → IPA via eng_to_ipa (CMUdict)."""

import eng_to_ipa


def en_to_ipa(word: str) -> str:
    """Konvertiert englisches Wort zu IPA.

    Args:
        word: Englisches Wort (z.B. "though")

    Returns:
        IPA-String mit Stress-Markern (z.B. "ðoʊ")
    """
    result = eng_to_ipa.convert(word)
    # Mehrere Aussprachen (*-separiert) — erste nehmen
    if "*" in result:
        result = result.split("*")[0].strip()
    return result.strip()


def strip_stress(ipa: str) -> tuple[str, int | None]:
    """Entfernt Stress-Markierungen, gibt Position des Primary Stress zurück.

    ˈ = primary stress, ˌ = secondary stress (ignoriert)

    Returns:
        (clean_ipa, stress_index) — stress_index ist 0-basiert im cleanen String
    """
    stress_idx = None
    clean = []
    stress_count = 0
    for ch in ipa:
        if ch == "ˈ":
            stress_idx = len(clean)
        elif ch == "ˌ":
            pass  # secondary stress ignorieren
        else:
            clean.append(ch)
    return "".join(clean), stress_idx
