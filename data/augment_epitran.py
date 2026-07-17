#!/usr/bin/env python3
"""Augmentiert die DE-Wortdatenbank mit epitran-generierten IPA-Einträgen.

Optimierte Version: Lädt existierende Wörter in ein Set, verarbeitet
nur neue Wörter mit Batch-Inserts.
"""

import json
import sqlite3
import sys
import time
from pathlib import Path

import epitran

DATA_DIR = Path(__file__).parent
DB_PATH = DATA_DIR / "de_words.db"
JSONL_PATH = DATA_DIR / "kaikki-de.jsonl"


def augment_db(limit: int = 0, batch_size: int = 1000):
    epi = epitran.Epitran("deu-Latn")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")

    # Alle existierenden Wörter in ein Set laden (blitzschnell)
    existing = set()
    for (word,) in conn.execute("SELECT word FROM words"):
        existing.add(word)

    print(f"Vorhanden: {len(existing):,} Einträge")
    print(f"→ Verarbeite {JSONL_PATH.name} (~368K Zeilen)...")

    batch = []
    added = 0
    scanned = 0
    start = time.time()

    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if limit and added >= limit:
                break

            scanned += 1
            if scanned % 50000 == 0:
                elapsed = time.time() - start
                rate = scanned / elapsed
                remaining = (368000 - scanned) / rate if rate > 0 else 0
                print(
                    f"\r  {scanned:,} Zeilen ({rate:.0f}/s) "
                    f"+{added:,} neu  "
                    f"~{remaining:.0f}s verbleibend  ",
                    end="",
                )

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            word = entry.get("word", "")
            if not word or "redirect" in entry or word in existing:
                continue

            try:
                ipa = epi.transliterate(word)
                if ipa and ipa != word:
                    batch.append((word, ipa.strip()))
                    existing.add(word)  # Merken für Duplikat-Prüfung

                    if len(batch) >= batch_size:
                        conn.executemany(
                            "INSERT OR IGNORE INTO words (word, ipa) VALUES (?, ?)",
                            batch,
                        )
                        added += len(batch)
                        batch = []
            except Exception:
                continue

    # Rest-Batch
    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO words (word, ipa) VALUES (?, ?)",
            batch,
        )
        added += len(batch)

    # FTS5 neu bauen
    print(f"\n  → Baue FTS5-Index neu...")
    conn.execute("INSERT INTO words_fts(words_fts) VALUES('rebuild')")
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    elapsed = time.time() - start
    db_size = DB_PATH.stat().st_size / 1024 / 1024
    print(f"  ✓ {added:,} neue Einträge in {elapsed:.0f}s")
    print(f"  📦 Gesamt: {total:,} Wörter, {db_size:.1f} MB")
    conn.close()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="Max neue Einträge")
    p.add_argument("--batch", type=int, default=1000, help="Batch-Größe")
    args = p.parse_args()

    if not DB_PATH.exists():
        print("✗ DB nicht gefunden. Führe zuerst 'python ingest_de.py' aus.")
        sys.exit(1)

    augment_db(limit=args.limit, batch_size=args.batch)
