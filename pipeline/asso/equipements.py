"""Lieux de pratique : installations sportives de Dumbéa.

Sources :
- Data ES (ministère chargé des Sports) : installations, équipements, activités possibles ;
- carte « Les infrastructures et leurs activités » de la Ville (2022), transcrite dans
  data/ref/lieux_activites_mairie.csv : activités réellement proposées par complexe.

Aucune source ne dit quel club utilise quelle salle : on n'invente pas ce lien.
"""

import re
from collections import defaultdict

from . import classify
from .clean import fix_text, norm
from .sources import REF

# Étiquettes non sportives déclenchées par des noms de lieux (« Rivière », « parcours de santé »).
HORS_SPORT = {"environnement", "santé", "cultures du Pacifique"}


def _true(v) -> bool:
    return str(v).lower() in ("true", "oui", "1")


def _activites(*textes: str) -> list[str]:
    return [
        a for a in classify.activites(norm(" ".join(textes))) if a not in HORS_SPORT
    ]


def load_carte_mairie() -> list[dict]:
    lignes = (
        (REF / "lieux_activites_mairie.csv").read_text(encoding="utf-8").splitlines()
    )
    cles = lignes[0].split(";")
    return [
        dict(zip(cles, ligne.split(";"), strict=True)) for ligne in lignes[1:] if ligne
    ]


def installations(equipements: list[dict], carte_mairie: list[dict]) -> list[dict]:
    groupes = defaultdict(list)
    for e in equipements:
        if not _true(e.get("inst_hs_bool")) and e.get("equip_coordonnees"):
            groupes[e["inst_numero"]].append(e)

    lieux = {}
    for num, eqs in groupes.items():
        pratiques = sorted({a for e in eqs for a in (e.get("aps_name") or [])})
        types = sorted({e["equip_type_name"] for e in eqs if e.get("equip_type_name")})
        pos = eqs[0]["equip_coordonnees"]  # équipements regroupés à quelques mètres
        lieux[f"es-{num}"] = {
            "id": f"es-{num}",
            "nom": fix_text(eqs[0].get("inst_nom")),
            "adresse": fix_text(eqs[0].get("inst_adresse")),
            "lat": pos["lat"],
            "lon": pos["lon"],
            "pratiques": [fix_text(re.split(r"\s*/\s*", p)[0]) for p in pratiques],
            "types": types,
            "_texte": " ".join(
                [*pratiques, *types, *(e.get("equip_nom") or "" for e in eqs)]
            ),
            "acces_libre": any(_true(e.get("equip_acc_libre")) for e in eqs),
            "sources": ["data-es"],
        }

    for ligne in carte_mairie:
        lieu = lieux.get(ligne["installation"])
        if lieu is None:  # lieu absent de Data ES : coordonnées dans le fichier
            lieu = lieux[ligne["installation"]] = {
                "id": ligne["installation"],
                "nom": ligne["lieu_carte_mairie"],
                "lat": float(ligne["lat"]),
                "lon": float(ligne["lon"]),
                "_texte": "",
                "sources": [],
            }
        lieu["activites_mairie"] = [a.strip() for a in ligne["activites"].split(",")]
        lieu["complexe"] = ligne["lieu_carte_mairie"]
        lieu["sources"].append("carte-mairie-2022")

    out = []
    for lieu in lieux.values():
        lieu["activites"] = _activites(
            lieu.pop("_texte"), *lieu.get("activites_mairie", [])
        )
        out.append({k: v for k, v in lieu.items() if v not in (None, [], "", False)})
    return sorted(out, key=lambda i: norm(i["nom"]))
