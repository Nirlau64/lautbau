#!/usr/bin/env python3
"""Augmentiert die DE-Wortdatenbank mit epitran-generierten IPA-Einträgen.

Liest Wörter aus der DB, die bereits IPA haben, UND fügt IPA für Wörter
aus dem kaikki-JSONL hinzu, die bisher kein IPA hatten.
"""

import json
import sqlite3
import sys
from pathlib import Path

import epitran

DATA_DIR = Path(__file__).parent
DB_PATH = DATA_DIR / "de_words.db"
JSONL_PATH = DATA_DIR / "kaikki-de.jsonl"


def augment_db(limit: int = 0):
    """Fügt IPA-Einträge via epitran hinzu."""
    epi = epitran.Epitran("deu-Latn")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    # Zähle vorhandene Einträge
    existing = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    print(f"Vorhanden: {existing:,} Einträge")

    added = 0
    skipped = 0

    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and added >= limit:
                break

            if i % 50000 == 0 and i > 0:
                print(f"\r  Zeile {i:,}... (+{added:,} neu, {skipped:,} übersprungen)", end="")

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            word = entry.get("word", "")
            if not word or "redirect" in entry:
                continue

            # Hat dieses Wort bereits IPA in der DB?
            existing_ipa = conn.execute(
                "SELECT ipa FROM words WHERE word = ? LIMIT 1", (word,)
            ).fetchone()

            if existing_ipa and existing_ipa[0]:
                skipped += 1
                continue

            # Versuche IPA via epitran zu generieren
            try:
                ipa = epi.transliterate(word)
                if not ipa or ipa == word:
                    continue
                # Normalisieren
                ipa = ipa.strip()
                conn.execute(
                    "INSERT OR IGNORE INTO words (word, ipa) VALUES (?, ?)",
                    (word, ipa),
                )
                added += 1
            except Exception:
                continue

    # FTS5 neu bauen
    print(f"\n  → Baue FTS5-Index neu...")
    conn.execute("INSERT INTO words_fts(words_fts) VALUES('rebuild')")
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    db_size = DB_PATH.stat().st_size / 1024 / 1024
    print(f"  ✓ {added:,} neue Einträge hinzugefügt")
    print(f"  ⚠ {skipped:,} bereits vorhanden")
    print(f"  📦 Gesamt: {total:,} Wörter, {db_size:.1f} MB")
    conn.close()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="Max neue Einträge (0=alle)")
    args = p.parse_args()

    if not DB_PATH.exists():
        print("✗ DB nicht gefunden. Führe zuerst 'python ingest_de.py' aus.")
        sys.exit(1)

    augment_db(limit=args.limit)
