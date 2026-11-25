"""Rapprochement des fiches de l'annuaire municipal avec le RNA, par similarité de nom.

Score = couverture des mots du nom annuaire par le titre RNA, pondérée par la rareté
des mots (IDF) : « club » ou « dumbea » comptent peu, « oasis » ou « koryo » beaucoup.
Complété par une similarité caractère à caractère pour les écritures collées/séparées
(« Taekwondo » / « TAE KWONDO »).
"""

import math
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher

from .clean import fix_text, norm

DUMBEA = "98805"
STOP = {
    "association",
    "asso",
    "de",
    "du",
    "des",
    "la",
    "le",
    "les",
    "l",
    "d",
    "et",
    "a",
    "au",
    "aux",
    "en",
    "pour",
}
SYNONYMES = {
    "ape": ["parents", "eleves"],
    "nc": ["nouvelle", "caledonie"],
    "cie": ["compagnie"],
}
SEUIL = 0.7


def tokens(nom: str) -> set[str]:
    out = set()
    for t in norm(nom).split():
        out.update(SYNONYMES.get(t, [t]))
    return {t for t in out if t not in STOP and len(t) > 1}


def _compact(nom: str, tri: bool) -> str:
    """Mots significatifs collés : « Inter-âge » == « INTERAGE »."""
    mots = [t for t in norm(nom).split() if t not in STOP]
    return "".join(sorted(mots) if tri else mots)


def _similarite_car(a: str, b: str) -> float:
    return max(
        SequenceMatcher(None, _compact(a, tri), _compact(b, tri)).ratio()
        for tri in (False, True)
    )


def rna_titre(r: dict) -> str:
    return fix_text(r.get("title") or r.get("short_title"))


class Matcher:
    def __init__(self, rna: list[dict]):
        self.rna = rna
        self.toks = [tokens(rna_titre(r)) for r in rna]
        df = Counter(t for ts in self.toks for t in ts)
        self.idf = defaultdict(
            lambda: math.log(len(rna)),
            {t: math.log(len(rna) / n) for t, n in df.items()},
        )
        self.index = defaultdict(list)
        for i, ts in enumerate(self.toks):
            for t in ts:
                self.index[t].append(i)

    def _w(self, ts: set[str]) -> float:
        return sum(self.idf[t] for t in ts)

    def _score_nom(self, nom: str, i: int) -> float:
        a, b = tokens(nom), self.toks[i]
        if not a or not b:
            return 0.0
        commun = self._w(a & b)
        mots = 0.7 * commun / self._w(a) + 0.3 * commun / self._w(b)
        car = _similarite_car(nom, rna_titre(self.rna[i]))
        return max(mots, car if car >= 0.9 else 0.0)

    def score(self, nom: str, i: int) -> float:
        # Avec et sans parenthèse finale : « ASD Basket-ball (ASD Basket-ball) »
        sans_parenthese = re.sub(r"\s*\([^)]*\)\s*$", "", nom)
        s = max(self._score_nom(nom, i), self._score_nom(sans_parenthese, i))
        if self.rna[i].get("com_code_asso") == DUMBEA:
            s += 0.05  # à score proche, préférer une association domiciliée à Dumbéa
        return s

    def best(self, nom: str) -> tuple[dict | None, float]:
        candidats = {i for t in tokens(nom) for i in self.index.get(t, [])}
        if not candidats:
            return None, 0.0
        i = max(candidats, key=lambda i: self.score(nom, i))
        return self.rna[i], round(self.score(nom, i), 2)


def match_annuaire(
    annuaire: list[dict],
    rna: list[dict],
    corrections: dict[str, str] | None = None,
    seuil: float = SEUIL,
) -> dict[int, tuple[dict, float]]:
    """Index fiche annuaire -> (fiche RNA, score) pour les rapprochements >= seuil.

    `corrections` : nom annuaire -> id RNA imposé ("" = aucune correspondance).
    """
    corrections = corrections or {}
    par_id = {r["id"]: r for r in rna}
    m = Matcher(rna)
    out = {}
    for i, e in enumerate(annuaire):
        if e["nom"] in corrections:
            if r := par_id.get(corrections[e["nom"]]):
                out[i] = (r, 1.0)
            continue
        r, s = m.best(e["nom"])
        if r is not None and s >= seuil:
            out[i] = (r, s)
    return out


SEUIL_RIDET = 0.9  # mots fréquents (« dumbea », « sur mer », « college ») : seuil haut


def match_ridet(noms: dict[str, str], ridet: list[dict]) -> dict[str, dict]:
    """Clé de fiche -> fiche RIDET, rapprochement par nom, un pour un (meilleur score)."""
    # Pas de com_code_asso : le bonus « domicilié à Dumbéa » ne départagerait rien ici.
    m = Matcher([{"id": cle, "title": nom} for cle, nom in noms.items()])
    meilleurs: dict[str, tuple[float, dict]] = {}
    for rec in ridet:
        best, s = m.best(rec.get("designation") or rec.get("nom_complet") or "")
        if best and s >= SEUIL_RIDET and s > meilleurs.get(best["id"], (0, None))[0]:
            meilleurs[best["id"]] = (s, rec)
    return {cle: rec for cle, (_, rec) in meilleurs.items()}
