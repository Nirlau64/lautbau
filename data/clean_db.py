#!/usr/bin/env python3
"""Bereinigt die DE-Wortdatenbank von nicht-deutschen Einträgen."""

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent
DB_PATH = DATA_DIR / "de_words.db"


def is_german_word(word: str) -> bool:
    """Heuristik: Ist das ein deutsches Wort?"""
    # Enthält Wort Leerzeichen? → Fremder Eintrag
    if " " in word:
        return False

    # Enthält es offensichtlich nicht-deutsche Zeichen?
    if any(c in word for c in "áéíóúýàèìòùãõñêâîôûëï"):
        return False

    # Reine ASCII-Wörter ohne deutsche Merkmale sind verdächtig
    # (viele englische Wörter haben DE-Wiktionary-Einträge)
    has_german_char = any(c in word for c in "äöüßÄÖÜ")
    has_german_cluster = any(
        cluster in word.lower()
        for cluster in ("sch", "ch", "ck", "tz", "pf", "ei", "ie", "eu", "äu")
    )

    # Kurze ASCII-Wörter ohne deutsche Merkmale → wahrscheinlich fremd
    if not has_german_char and not has_german_cluster:
        # Nur behalten wenn es ein typisch deutsches Muster hat
        # (z.B. Großschreibung = deutsches Substantiv)
        if word[0].isupper():
            return True
        return False

    return True


def clean_db():
    conn = sqlite3.connect(str(DB_PATH))
    before = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]

    # Nicht-deutsche Einträge löschen
    conn.execute("DELETE FROM words WHERE word LIKE '% %'")  # Multi-Wort
    removed = before - conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    print(f"  - {removed:,} Multi-Wort-Einträge entfernt")

    # Iterativ durchgehen und is_german_word prüfen
    to_delete = []
    for row in conn.execute("SELECT id, word FROM words"):
        if not is_german_word(row[1]):
            to_delete.append(row[0])

    if to_delete:
        # Batch delete in chunks
        for i in range(0, len(to_delete), 1000):
            chunk = to_delete[i : i + 1000]
            conn.execute(
                f"DELETE FROM words WHERE id IN ({','.join('?' * len(chunk))})",
                chunk,
            )

    conn.execute("INSERT INTO words_fts(words_fts) VALUES('rebuild')")
    conn.commit()

    after = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    db_size = DB_PATH.stat().st_size / 1024 / 1024
    print(f"  - {len(to_delete):,} nicht-deutsche Einträge entfernt")
    print(f"  📦 {before:,} → {after:,} Wörter ({db_size:.1f} MB)")
    conn.close()


if __name__ == "__main__":
    if not DB_PATH.exists():
        print("✗ DB nicht gefunden.")
    else:
        print("Bereinige deutsche Wortdatenbank...")
        clean_db()
