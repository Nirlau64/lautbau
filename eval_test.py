#!/usr/bin/env python3
"""Evaluation: 20 Testwörter für LautBau MVP."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.pipeline import LautBau
from engine.renderer import _use_ansi

TEST_WORDS = [
    # Kurze, häufige Wörter
    ("cat", "Katze, einfach"),
    ("dog", "Hund, einfach"),
    ("fish", "Fisch, einfach"),
    ("house", "Haus, einfach"),
    ("water", "Wasser, häufig"),
    # Schwierigere Laute
    ("though", "th-Laut + Diphthong"),
    ("through", "th-Laut + r"),
    ("knight", "stummes k, Diphthong"),
    ("squirrel", "schwierig für Deutsche"),
    ("beautiful", "mehrsilbig"),
    # Alltagswörter
    ("restaurant", "Lehnwort"),
    ("comfortable", "mehrsilbig, viele Schwa"),
    ("island", "stummes s"),
    ("photograph", "ph + Diphthong"),
    ("weather", "th-Laut"),
    # Minimalpaare
    ("ship", "kurzer Vokal"),
    ("sheep", "langer Vokal"),
    ("bat", "æ-Laut"),
    ("bet", "ɛ-Laut"),
    ("boot", "langer Vokal"),
]


def main():
    lb = LautBau()
    use_ansi = _use_ansi()

    print("=" * 60)
    print("LAUTBAU EVALUATION — 20 Testwörter")
    print("=" * 60)
    print()

    for word, description in TEST_WORDS:
        print(f"▶ {word} ({description})")
        try:
            result = lb.pronounce(word, threshold=0.5, verbose=False)
            # For non-ANSI terminals, strip ANSI codes for clean output
            if not use_ansi:
                import re
                result = re.sub(r'\033\[\d+m', '', result)
            print(f"  {result}")
        except Exception as e:
            print(f"  ✗ FEHLER: {e}")
        print()


if __name__ == "__main__":
    main()
