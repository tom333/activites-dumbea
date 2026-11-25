"""Nettoyage de texte."""

import re
import unicodedata

# Mojibake observé dans le RNA NC (ftfy ne le corrige pas).
MOJIBAKE = {
    "Ú": "è",
    "ఠ": "°",
    "à°": "°",
    "ÃŽ": "ô",
    "Ã ": "à ",
}


def fix_text(s: str | None) -> str:
    if not s:
        return ""
    for bad, good in MOJIBAKE.items():
        s = s.replace(bad, good)
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str | None) -> str:
    """Minuscules, sans accents ni ponctuation : pour comparer et chercher."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()
