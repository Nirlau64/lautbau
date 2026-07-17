#!/usr/bin/env python3
"""DB-Migration: Fügt tokenisierte Phonem-Sequenz + FTS5-Index hinzu.

Statt LIKE '%k%' (71K Kandidaten) → FTS5 Phrase-Query "k æ t" (~50 Kandidaten).
Das ist der entscheidende Unterschied zwischen Zufall und Suche.
"""

import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.segmenter import tokenize

DATA_DIR = Path(__file__).parent
DB_PATH = DATA_DIR / "de_words.db"


def clean_ipa_for_tokenizing(ipa: str) -> str:
    """Entfernt Stress-Marker, Silbengrenzen, Längenmarkierungen."""
    return ipa.replace("ˈ", "").replace("ˌ", "").replace(".", "").replace(" ", "").replace("̯", "")


def migrate():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")

    before = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    print(f"Wörter: {before:,}")

    # 1. Neue Spalte hinzufügen
    cols = [r[1] for r in conn.execute("PRAGMA table_info(words)")]
    if "phonemes" not in cols:
        print("→ Füge phonemes-Spalte hinzu...")
        conn.execute("ALTER TABLE words ADD COLUMN phonemes TEXT")
        conn.commit()

    # 2. IPA tokenisieren und als Space-separated String speichern
    print("→ Tokenisiere IPA...")
    total = conn.execute("SELECT COUNT(*) FROM words WHERE phonemes IS NULL").fetchone()[0]
    print(f"  {total:,} Einträge zu verarbeiten")

    batch = []
    processed = 0
    start = time.time()

    for row in conn.execute("SELECT id, ipa FROM words WHERE phonemes IS NULL"):
        wid, ipa = row
        if not ipa:
            batch.append((None, wid))
            continue

        clean = clean_ipa_for_tokenizing(ipa)
        try:
            tokens = tokenize(clean)
            phoneme_str = " ".join(tokens)
            batch.append((phoneme_str, wid))
        except Exception:
            batch.append((None, wid))

        processed += 1
        if processed % 50000 == 0:
            elapsed = time.time() - start
            rate = processed / elapsed
            print(f"\r  {processed:,}/{total:,} ({rate:.0f}/s)", end="")

            # Batch write
            conn.executemany("UPDATE words SET phonemes = ? WHERE id = ?", batch)
            batch = []

    # Rest
    if batch:
        conn.executemany("UPDATE words SET phonemes = ? WHERE id = ?", batch)

    elapsed = time.time() - start
    print(f"\r  ✓ {processed:,} tokenisiert in {elapsed:.0f}s")

    # 3. FTS5-Index auf phonemes neu bauen
    print("→ Baue FTS5-Index auf phonemes...")
    conn.execute("DROP TABLE IF EXISTS words_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE words_fts USING fts5(
            phonemes,
            content='words',
            content_rowid='id',
            tokenize='unicode61'
        )
    """)

    # FTS5 externer Index: alle Zeilen einfügen
    conn.execute("INSERT INTO words_fts(phonemes, rowid) SELECT phonemes, id FROM words WHERE phonemes IS NOT NULL")
    conn.commit()

    # 4. Verify
    sample = conn.execute("SELECT word, ipa, phonemes FROM words WHERE phonemes IS NOT NULL LIMIT 5").fetchall()
    print("\n→ Stichprobe:")
    for w, i, p in sample:
        print(f"  {w:15s} /{i:20s}/ phonemes={p}")

    # 5. FTS5 Query Test
    print("\n→ FTS5 Query Tests:")
    for query in ["k æ t", "n aɪ t", "d ɔ ɡ", "ʃ ɪ p"]:
        try:
            c = conn.execute(
                "SELECT COUNT(*) FROM words_fts WHERE words_fts MATCH ?",
                (f'"{query}"',)
            ).fetchone()[0]
            print(f"  \"{query}\" → {c:,} Kandidaten")
        except Exception as e:
            print(f"  \"{query}\" → Fehler: {e}")

    db_size = DB_PATH.stat().st_size / 1024 / 1024
    print(f"\n📦 DB: {db_size:.1f} MB")
    conn.close()


if __name__ == "__main__":
    if not DB_PATH.exists():
        print("✗ DB nicht gefunden.")
        sys.exit(1)
    migrate()
