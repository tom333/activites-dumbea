"""Construit web/public/data/associations.json à partir du RNA et de l'annuaire municipal.

Usage : uv run python -m asso.build [--refresh]
"""

import json
import sys
from collections import Counter
from datetime import date

from . import classify
from .annuaire import parse_annuaire
from .clean import fix_text, norm
from .equipements import installations, load_carte_mairie
from .geocode import Geocoder
from .match import DUMBEA, match_annuaire, match_ridet, rna_titre
from .sources import (
    REF,
    ROOT,
    load_annuaire_pages,
    load_equipements,
    load_ridet,
    load_rna,
    load_waldec,
)

OUT = ROOT / "web" / "public" / "data" / "associations.json"
ANNEES_RECENTE = 5
PETITS_MOTS = {
    "de",
    "du",
    "des",
    "la",
    "le",
    "les",
    "et",
    "a",
    "à",
    "au",
    "aux",
    "en",
    "pour",
    "sur",
}


def is_dumbea(r: dict) -> bool:
    return r.get("com_code_asso") == DUMBEA or norm(r.get("com_name_asso")).startswith(
        "dumbea"
    )


def joli_nom(s: str) -> str:
    """Les titres RNA sont souvent en majuscules et entre guillemets."""
    s = fix_text(s).strip(" \"'«»")
    if s != s.upper():
        return s
    mots = []
    for i, w in enumerate(s.lower().split(" ")):
        if i and w in PETITS_MOTS:
            mots.append(w)
        elif w[:2] in ("l'", "d'"):
            mots.append(w[:2] + w[2:3].upper() + w[3:])
        else:
            mots.append(w[:1].upper() + w[1:])
    return " ".join(mots)


def load_corrections() -> dict[str, str]:
    lignes = (REF / "rapprochements.csv").read_text(encoding="utf-8").splitlines()[1:]
    return {
        nom: rna_id
        for nom, rna_id, _ in (ligne.split(";", 2) for ligne in lignes if ligne)
    }


def statut(mairie: list, r: dict | None, aujourd_hui: date) -> str:
    if mairie:
        return "confirmee"  # listée par la mairie
    derniere = (r or {}).get("declaration_date") or (r or {}).get("creation_date") or ""
    seuil = aujourd_hui.replace(year=aujourd_hui.year - ANNEES_RECENTE).isoformat()
    return "recente" if derniere >= seuil else "ancienne"


def adresse_rna(r: dict) -> str:
    parties = [
        r.get(k)
        for k in (
            "street_number_asso",
            "street_type_asso",
            "street_name_asso",
            "comp_address_asso",
        )
    ]
    return fix_text(" ".join(p for p in parties if p))


def fiche(
    cle: str,
    r: dict | None,
    mairie: list[dict],
    waldec: dict,
    geo: Geocoder,
    today: date,
    ridet: dict | None = None,
) -> dict:
    m0 = mairie[0] if mairie else {}
    nom = m0.get("nom") or joli_nom(rna_titre(r))
    objet = fix_text(r.get("object")) if r else ""
    codes = list(
        dict.fromkeys(
            c for k in ("social_object1", "social_object2") if (c := (r or {}).get(k))
        )
    )
    # Rubrique et descriptif de l'annuaire mairie (« Danse », « football et volley-ball »)
    rubriques = list(
        dict.fromkeys(x for e in mairie for x in (e["rubrique"], e["description"]) if x)
    )
    libelles = [waldec.get(c, "") for c in codes]

    # Activités « sûres » : nom, rubrique mairie, code WALDEC (hors parenthèses d'exemples).
    texte_fort = norm(
        " ".join([nom, *rubriques, *(lib.split("(")[0] for lib in libelles)])
    )
    activites = classify.activites(texte_fort)
    # Activité déclarée au RIDET : texte libre court, traité comme l'objet RNA.
    ape = fix_text((ridet or {}).get("ape")).lstrip("* ")
    texte_tout = norm(" ".join([nom, *rubriques, objet, ape]))
    age_min, age_max = classify.ages(texte_tout)

    publiable = bool(r) and r.get("ispublic") == "oui"
    loc = geo.locate(r, precise=publiable) if r and is_dumbea(r) else None
    if not loc and ridet:
        # Adresse d'établissement RIDET : seulement pour situer le quartier, jamais affichée
        # (elle contient parfois le nom d'un particulier, « chez M. … »).
        for e in ridet.get("etablissements") or []:
            if e.get("ville_physique") == "DUMBEA" and e.get("adresse_physique"):
                loc = geo.locate(
                    {"street_name_asso": e["adresse_physique"]}, precise=False
                )
                if loc:
                    break

    contact = {
        "tels": list(dict.fromkeys(t for e in mairie for t in e["tels"])),
        "emails": list(dict.fromkeys(x for e in mairie for x in e["emails"])),
        "facebook": next((e["facebook"] for e in mairie if e["facebook"]), None),
        "site": next((e["site"] for e in mairie if e["site"]), None)
        or (r or {}).get("website"),
    }
    out = {
        "id": cle,
        "nom": nom,
        "genre": classify.genre(m0.get("categorie"), m0.get("rubrique"), codes),
        "activites": activites,
        "activites_objet": [
            a for a in classify.activites(norm(f"{objet} {ape}")) if a not in activites
        ],
        "rubriques": rubriques,
        "publics": classify.publics(texte_tout),
        "age_min": age_min,
        "age_max": age_max,
        "objet": objet,
        "objets_sociaux": [lib for lib in libelles if lib],
        "statut": statut(mairie, r, today),
        "creation": (r or {}).get("creation_date"),
        "derniere_declaration": (r or {}).get("declaration_date"),
        "contact": {k: v for k, v in contact.items() if v},
        "adresse": adresse_rna(r) if publiable else None,
        "hors_dumbea": bool(r) and not is_dumbea(r),
        "rna_id": (r or {}).get("id"),
        "ridet": (ridet or {}).get("rid"),
        "ridet_radiee": (ridet or {}).get("etat_rid") == "R",
        "sources": (["mairie"] if mairie else [])
        + (["rna"] if r else [])
        + (["ridet"] if ridet else []),
        **(loc or {}),
    }
    return {k: v for k, v in out.items() if v not in (None, [], {}, "", False)}


def main(refresh: bool = False) -> None:
    today = date.today()
    waldec = load_waldec()
    rna = load_rna(refresh)
    annuaire = parse_annuaire(load_annuaire_pages(refresh))
    matches = match_annuaire(annuaire, rna, load_corrections())

    groupes: dict[str, tuple[dict | None, list[dict]]] = {}
    for i, e in enumerate(annuaire):
        r = matches[i][0] if i in matches else None
        cle = r["id"] if r else "mairie-" + norm(e["nom"]).replace(" ", "-")
        groupes.setdefault(cle, (r, []))[1].append(e)
    for r in rna:
        if is_dumbea(r):
            groupes.setdefault(r["id"], (r, []))

    # RIDET rapproché sur la dénomination officielle RNA uniquement (plus fiable que les
    # noms d'usage de l'annuaire mairie).
    noms = {cle: rna_titre(r) for cle, (r, _) in groupes.items() if r}
    ridet = match_ridet(noms, load_ridet(refresh))

    geo = Geocoder()
    try:
        fiches = [
            fiche(cle, r, mairie, waldec, geo, today, ridet.get(cle))
            for cle, (r, mairie) in groupes.items()
        ]
    finally:
        geo.save()
    fiches.sort(
        key=lambda f: (
            {"confirmee": 0, "recente": 1, "ancienne": 2}[f["statut"]],
            norm(f["nom"]),
        )
    )

    lieux = installations(load_equipements(refresh), load_carte_mairie())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "genere_le": today.isoformat(),
                "genres": classify.GENRES,
                "associations": fiches,
                "equipements": lieux,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    print(f"{len(fiches)} associations -> {OUT.relative_to(ROOT)}")
    print(
        f"annuaire mairie : {len(annuaire)} fiches, {len(matches)} rapprochées du RNA"
    )
    print("statut :", dict(Counter(f["statut"] for f in fiches)))
    print("genre :", dict(Counter(f["genre"] for f in fiches)))
    radiees = sum(f.get("ridet_radiee", False) for f in fiches)
    print(f"RIDET : {len(ridet)} fiches rapprochées, dont {radiees} radiées")
    print(f"lieux de pratique (Data ES + carte mairie) : {len(lieux)} installations")
    print(
        "précision carte :", dict(Counter(f.get("precision", "aucune") for f in fiches))
    )
    sans = [e["nom"] for i, e in enumerate(annuaire) if i not in matches]
    print(f"annuaire sans correspondance RNA ({len(sans)}) :", "; ".join(sans))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
