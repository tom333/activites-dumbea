"""Localisation du siège déclaré au RNA.

Ordre d'essai :
1. adresse postale via l'API Localisation NC (https://localisation.gouv.nc/api/openapi)
   -> précision « adresse » (numéro) ou « rue » ;
2. nom de quartier repéré dans l'adresse (data/ref/quartiers.csv) -> précision « quartier ».

Seules les associations domiciliées à Dumbéa sont placées sur la carte : un siège à
Nouméa ne dit rien du lieu de pratique à Dumbéa.
"""

import json
import math
import re
import time

import httpx

from .clean import fix_text, norm
from .sources import RAW, REF, USER_AGENT

API = "https://localisation.gouv.nc/api/search"
CACHE = RAW.parent / "cache" / "geocode.json"
SCORE_MIN = 0.6
QUARTIER_KM = 3
DUMBEA = "98805"
_BOITE_POSTALE = re.compile(r"^\s*(b\.?\s*p\.?|boite postale|cedex)\b", re.IGNORECASE)


def _quartiers() -> list[tuple[str, re.Pattern, float, float]]:
    lignes = (REF / "quartiers.csv").read_text(encoding="utf-8").splitlines()[1:]
    out = []
    for ligne in lignes:
        nom, motif, lon, lat = ligne.split(";")
        out.append((nom, re.compile(rf"\b(?:{motif})\b"), float(lon), float(lat)))
    return out


class Geocoder:
    def __init__(self):
        self.cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
        self.quartiers = _quartiers()
        self.client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30)

    def save(self):
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(self.cache, ensure_ascii=False, indent=0))

    def _search(self, q: str, citycode: str) -> dict | None:
        q = re.sub(r"[^\w' -]+", " ", q).strip()  # l'API rejette ()"/ etc. (400)
        key = f"{citycode}|{q}"
        if key not in self.cache:
            params = {"q": q, "citycode": citycode, "index": "address", "limit": 1}
            resp = self.client.get(API, params=params)
            if resp.status_code == 400:
                self.cache[key] = None  # requête non analysable : pas de résultat
            else:
                resp.raise_for_status()
                features = resp.json().get("features", [])
                self.cache[key] = features[0] if features else None
            time.sleep(0.05)
        return self.cache[key]

    def _quartier_proche(self, lon: float, lat: float) -> dict | None:
        nom, _, qlon, qlat = min(
            self.quartiers, key=lambda q: (q[2] - lon) ** 2 + (q[3] - lat) ** 2
        )
        km = math.hypot((qlon - lon) * 103, (qlat - lat) * 111)  # ~km à 22°S
        return self._quartier(nom, qlon, qlat) if km <= QUARTIER_KM else None

    @staticmethod
    def _quartier(nom: str, lon: float, lat: float) -> dict:
        return {"lat": lat, "lon": lon, "precision": "quartier", "quartier": nom}

    def locate(self, r: dict, precise: bool) -> dict | None:
        """{lat, lon, precision, quartier?} pour une fiche RNA domiciliée à Dumbéa, sinon None.

        precise=False (publication web non autorisée au RNA) : on ne renvoie que le quartier.
        """
        rue = fix_text(r.get("street_name_asso"))
        if rue and not _BOITE_POSTALE.match(rue):
            q = " ".join(
                fix_text(r.get(k))
                for k in ("street_number_asso", "street_type_asso", "street_name_asso")
            ).strip()
            f = self._search(q, DUMBEA)
            p = f["properties"] if f else {}
            if p.get("score", 0) >= SCORE_MIN and p.get("type") in (
                "housenumber",
                "street",
            ):
                lon, lat = f["geometry"]["coordinates"]
                if not precise:
                    if quartier := self._quartier_proche(lon, lat):
                        return quartier
                else:
                    precision = "adresse" if p["type"] == "housenumber" else "rue"
                    return {"lat": lat, "lon": lon, "precision": precision}

        champs = ("comp_address_asso", "namedplace_address_asso", "street_name_asso")
        texte = norm(" ".join(fix_text(r.get(k)) for k in champs))
        for nom, rx, lon, lat in self.quartiers:
            if rx.search(texte):
                return self._quartier(nom, lon, lat)
        return None
