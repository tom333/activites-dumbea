"""Extraction des fiches de l'annuaire des associations du site de la Ville de Dumbéa.

Structure des pages (Drupal) : des blocs `.field--name-field-item-body` contenant, dans
l'ordre du document :
- des titres `h1` : soit une lettre (index alphabétique, ignoré), soit une rubrique ;
- des `li > strong > u` : rubrique d'activité (ex. « AÏKIDO ») ;
- des `p` commençant par `<strong>Nom</strong>` puis Tél., Mail, liens : une fiche.
"""

import re

from bs4 import BeautifulSoup, Tag

PHONE_RE = re.compile(r"\b\d{2}[ .]?\d{2}[ .]?\d{2}\b")


def _text(el: Tag) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def _premiere_ligne(p: Tag) -> tuple[str, str]:
    """(nom, descriptif) : texte avant le premier <br> non initial, l'italique à part.

    Le nom est parfois éclaté sur plusieurs balises
    (`<strong>A</strong><span><strong>ssociation Valentin-Haüy</strong></span>`) ;
    le descriptif est en italique (`<em>(football et volley-ball)</em>`).
    """
    nom, desc = [], []
    for node in p.descendants:
        if isinstance(node, Tag):
            if node.name == "br" and "".join(nom).strip():
                break
        else:
            (desc if node.find_parent("em") else nom).append(str(node))

    def colle(parts: list[str]) -> str:
        return re.sub(r"\s+", " ", "".join(parts)).strip()

    # « Nom (<em>descriptif</em>) » : retirer la parenthèse ouvrante orpheline du nom.
    return re.sub(r"[\s(–-]+$", "", colle(nom)), colle(desc).strip("()")


def _parse_entry(p: Tag, categorie: str, rubrique: str | None) -> dict | None:
    if not p.find("strong"):
        return None
    nom, description = _premiere_ligne(p)
    links = [a.get("href", "") for a in p.find_all("a")]
    texte = _text(p)
    if not nom or not ("Tél" in texte or "Mail" in texte or links):
        return None
    reste = texte[texte.find("Tél") :] if "Tél" in texte else ""
    return {
        "nom": nom,
        "description": description or None,
        "categorie": categorie,
        "rubrique": rubrique,
        "tels": [re.sub(r"\D", "", t) for t in PHONE_RE.findall(reste)],
        "emails": [
            h.removeprefix("mailto:").strip() for h in links if h.startswith("mailto:")
        ],
        "facebook": next((h for h in links if "facebook.com" in h), None),
        "site": next(
            (h for h in links if h.startswith("http") and "facebook.com" not in h), None
        ),
    }


def parse_page(html: str, categorie: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    rubrique = None
    for body in soup.select(".field--name-field-item-body"):
        for el in body.find_all(["h1", "h2", "h3", "h4", "li", "p"]):
            if el.find_parent("table"):
                continue  # tableaux de navigation
            if el.name in ("h1", "h2", "h3", "h4"):
                titre = _text(el)
                if len(titre) > 1:
                    rubrique = titre
            elif el.name == "li":
                if el.find("u") or el.find("strong"):
                    rubrique = _text(el)
            elif entry := _parse_entry(el, categorie, rubrique):
                entries.append(entry)
    return entries


def parse_annuaire(pages: dict[str, str]) -> list[dict]:
    return [e for categorie, html in pages.items() for e in parse_page(html, categorie)]
