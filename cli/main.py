#!/usr/bin/env python3
"""LautBau CLI — Phonetische Aussprachehilfe durch muttersprachliche Wortbausteine."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="laubau",
        description="Phonetische Aussprachehilfe — zerlegt englische Wörter in deutsche Wortbausteine.",
        epilog="Beispiel: laubau though",
    )
    parser.add_argument(
        "word", nargs="+",
        help="Englisches Wort (z.B. 'though'). Mehrere Wörter möglich.",
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float, default=0.5,
        help="Maximale panphon-Distanz (0=exakt, 0.5=locker, default: 0.5)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Detaillierte Ausgabe mit Segment-Infos",
    )
    parser.add_argument(
        "--db", type=str, default=None,
        help="Pfad zur de_words.db (default: data/de_words.db)",
    )

    args = parser.parse_args()

    db_path = Path(args.db) if args.db else PROJECT_ROOT / "data" / "de_words.db"
    if not db_path.exists():
        print(f"✗ Datenbank nicht gefunden: {db_path}")
        print("  Führe zuerst 'python data/ingest_de.py' aus.")
        sys.exit(1)

    from engine.pipeline import LautBau

    lb = LautBau(db_path=db_path)

    for word in args.word:
        try:
            result = lb.pronounce(word, threshold=args.threshold, verbose=args.verbose)
            print(result)
            if len(args.word) > 1:
                print()
        except Exception as e:
            print(f"✗ '{word}': {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()
