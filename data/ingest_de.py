#!/usr/bin/env python3
"""Ingest: Deutsche Wortdatenbank aus kaikki.org Wiktionary-Dumps.

Lädt das deutsche JSONL, extrahiert Wort + IPA, baut SQLite-DB mit FTS5-Index.
Basiert auf Wakean Word Forge's ingest.py (vereinfacht für LautBau).
"""

import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent
DB_PATH = DATA_DIR / "de_words.db"
DE_JSONL_URL = "https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl"
DE_JSONL_PATH = DATA_DIR / "kaikki-de.jsonl"

# ── Download ────────────────────────────────────────────────────────────

def download_jsonl(url: str, dest: Path, force: bool = False) -> bool:
    """Lädt JSONL herunter, falls nicht vorhanden oder force=True."""
    if dest.exists() and not force:
        size_mb = dest.stat().st_size / 1024 / 1024
        print(f"  ✓ Bereits vorhanden: {dest.name} ({size_mb:.1f} MB)")
        return True
    
    print(f"  ↓ Lade {url} ...")
    print(f"    Das kann ein paar Minuten dauern (~500 MB)...")
    
    try:
        with urllib.request.urlopen(url) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(f"\r    {downloaded/1024/1024:.1f} MB / {total/1024/1024:.1f} MB ({pct:.0f}%)", end="")
            print()
        return True
    except Exception as e:
        print(f"\n  ✗ Download fehlgeschlagen: {e}")
        if dest.exists():
            dest.unlink()
        return False


# ── Ingest ──────────────────────────────────────────────────────────────

def ingest_jsonl(jsonl_path: Path, db_path: Path, limit: int = 0) -> int:
    """Parst JSONL und schreibt Wort+IPA in SQLite.
    
    Args:
        jsonl_path: Pfad zur JSONL-Datei
        db_path: Pfad zur SQLite-DB
        limit: 0 = alle Einträge, >0 = max N Einträge
    
    Returns:
        Anzahl der ingestierten Einträge
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    
    # Schema
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            ipa TEXT,
            language TEXT DEFAULT 'de'
        );
        CREATE INDEX IF NOT EXISTS idx_words_ipa ON words(ipa);
        CREATE VIRTUAL TABLE IF NOT EXISTS words_fts USING fts5(
            ipa,
            content='words',
            content_rowid='id'
        );
        DELETE FROM words;
    """)
    
    count = 0
    skipped_no_ipa = 0
    skipped_redirect = 0
    
    print(f"  → Parse {jsonl_path.name}...")
    start = time.time()
    
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and count >= limit:
                break
            
            if i % 50000 == 0 and i > 0:
                elapsed = time.time() - start
                rate = i / elapsed
                print(f"\r    Zeile {i:,} ({rate:.0f} Zeilen/s, {count:,} Wörter mit IPA)...", end="")
            
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            word = entry.get("word", "")
            if not word:
                continue
            
            # Redirects überspringen
            if "redirect" in entry:
                skipped_redirect += 1
                continue
            
            # IPA extrahieren
            ipa = None
            sounds = entry.get("sounds", [])
            for s in sounds:
                if "ipa" in s:
                    ipa = s["ipa"]
                    # Normalisieren: /.../ oder [...] entfernen
                    ipa = ipa.strip("/[] ")
                    break
            
            if not ipa:
                skipped_no_ipa += 1
                continue
            
            conn.execute(
                "INSERT INTO words (word, ipa) VALUES (?, ?)",
                (word, ipa)
            )
            count += 1
    
    # FTS5-Index bauen
    print(f"\n    → Baue FTS5-Index ({count:,} Einträge)...")
    conn.execute("INSERT INTO words_fts(words_fts) VALUES('rebuild')")
    
    conn.commit()
    elapsed = time.time() - start
    
    db_size = db_path.stat().st_size / 1024 / 1024 if db_path.exists() else 0
    
    print(f"  ✓ Fertig: {count:,} Wörter mit IPA in {elapsed:.0f}s")
    print(f"  ⚠ Übersprungen: {skipped_no_ipa:,} ohne IPA, {skipped_redirect:,} Redirects")
    print(f"  📦 DB-Größe: {db_size:.1f} MB")
    
    conn.close()
    return count


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="LautBau DE-Wort-DB Ingest")
    parser.add_argument("--limit", type=int, default=0, help="Max Einträge (0=alle)")
    parser.add_argument("--force-download", action="store_true", help="Neu downloaden")
    parser.add_argument("--query", type=str, help="Test-Query nach Ingest")
    args = parser.parse_args()
    
    print("=" * 50)
    print("LAUTBAU: Deutsche Wortdatenbank Ingest")
    print("=" * 50)
    
    # Download
    if not download_jsonl(DE_JSONL_URL, DE_JSONL_PATH, force=args.force_download):
        sys.exit(1)
    
    # Ingest
    count = ingest_jsonl(DE_JSONL_PATH, DB_PATH, limit=args.limit)
    
    # Test-Query
    if args.query and count > 0:
        print(f"\n  🔍 Test-Query: SUBSTR(ipa) LIKE '%{args.query}%'")
        conn = sqlite3.connect(str(DB_PATH))
        for word, ipa in conn.execute(
            "SELECT word, ipa FROM words WHERE ipa LIKE ? LIMIT 10",
            (f"%{args.query}%",)
        ):
            print(f"    {word:20s} {ipa}")
        conn.close()
    
    print("\n✓ Ingest abgeschlossen.")


if __name__ == "__main__":
    main()
