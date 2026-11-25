"""Téléchargement des sources brutes, avec cache disque dans data/raw/."""

import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
REF = ROOT / "data" / "ref"

USER_AGENT = "asso-dumbea/0.1 (annuaire associatif local)"

RNA_EXPORT = (
    "https://data.gouv.nc/api/explore/v2.1/catalog/datasets/rna-nc/exports/json"
)

ANNUAIRE_BASE = "https://www.ville-dumbea.nc/"
# slug de page -> catégorie mairie
ANNUAIRE_PAGES = {
    "associations-sportives": "Sport",
    "associations-culturelles": "Culture",
    "associations-de-quartier": "Quartier",
    "associations-scolaires": "Scolaire",
    "autres-associations": "Autres",
}


def _download(url: str, dest: Path, refresh: bool, params: dict | None = None) -> Path:
    if dest.exists() and not refresh:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = httpx.get(
        url,
        params=params,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=120,
    )
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def load_rna(refresh: bool = False) -> list[dict]:
    """Toutes les associations actives de Nouvelle-Calédonie.

    On prend tout le territoire (et pas seulement Dumbéa) car certaines associations
    de l'annuaire municipal ont leur siège déclaré dans une autre commune.
    """
    path = _download(
        RNA_EXPORT,
        RAW / "rna-nc-actives.json",
        refresh,
        params={"where": 'position="Active"'},
    )
    return json.loads(path.read_text(encoding="utf-8"))


def load_annuaire_pages(refresh: bool = False) -> dict[str, str]:
    """HTML des pages de l'annuaire municipal, indexé par catégorie mairie."""
    pages = {}
    for slug, categorie in ANNUAIRE_PAGES.items():
        dest = RAW / "annuaire" / f"{slug}.html"
        fetched = refresh or not dest.exists()
        _download(ANNUAIRE_BASE + slug, dest, refresh)
        if fetched:
            time.sleep(1)  # politesse envers le site de la mairie
        pages[categorie] = dest.read_text(encoding="utf-8")
    return pages


def load_waldec() -> dict[str, str]:
    """Nomenclature WALDEC des objets sociaux : code -> libellé."""
    lines = (
        (REF / "nomenclature_waldec.csv").read_text(encoding="utf-8-sig").splitlines()
    )
    codes = {}
    for line in lines[1:]:
        parent_id, parent_lib, code, lib = line.split(";", 3)
        codes[parent_id] = parent_lib
        codes[code] = lib
    return codes


RIDET_API = "https://annuaire-entreprises.gouv.nc/api/v1/recherche"


def load_ridet(refresh: bool = False) -> list[dict]:
    """Associations du RIDET (annuaire-entreprises.gouv.nc) dont le nom ou l'adresse
    contient « dumbea ». L'API n'offre qu'une recherche plein texte, 25 résultats/page."""
    dest = RAW / "ridet-dumbea.json"
    if refresh or not dest.exists():
        out, page = [], 1
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60) as client:
            while True:
                resp = client.get(
                    RIDET_API, params={"q": "dumbea", "page": page, "per_page": 25}
                )
                resp.raise_for_status()
                d = resp.json()
                out += d["results"]
                if page >= d["total_pages"]:
                    break
                page += 1
                time.sleep(0.5)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    records = json.loads(dest.read_text(encoding="utf-8"))
    return [r for r in records if "ASSOCIATION" in (r.get("forme_juridique") or "")]


DATA_ES = "https://equipements.sports.gouv.fr/api/explore/v2.1/catalog/datasets/data-es/exports/json"


def load_equipements(refresh: bool = False) -> list[dict]:
    """Équipements sportifs de Dumbéa (Data ES, ministère chargé des Sports)."""
    path = _download(
        DATA_ES,
        RAW / "data-es-dumbea.json",
        refresh,
        params={"where": 'new_code="98805"'},
    )
    return json.loads(path.read_text(encoding="utf-8"))
