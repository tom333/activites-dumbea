"""Classification par règles : genre, activités, public visé, tranche d'âge.

Tout est appliqué sur du texte normalisé (`clean.norm` : minuscules, sans accents ni
ponctuation), d'où des motifs comme « va a » pour « va'a ».
"""

import re

GENRES = {
    "sport": "Sport & plein air",
    "culture": "Culture & arts",
    "loisirs": "Loisirs & animation",
    "education": "Éducation & jeunesse",
    "solidarite": "Solidarité, santé & social",
    "quartier": "Quartier & vie locale",
    "environnement": "Environnement & animaux",
    "communautes": "Communautés, amicales & religion",
    "autres": "Autres",
}

# Thème parent WALDEC (3 premiers chiffres) -> genre
WALDEC_GENRE = {
    "011": "sport", "013": "sport",
    "006": "culture", "010": "culture",
    "007": "loisirs", "009": "loisirs", "034": "loisirs",
    "015": "education", "016": "education",
    "003": "solidarite", "004": "solidarite", "017": "solidarite", "018": "solidarite",
    "019": "solidarite", "020": "solidarite", "021": "solidarite", "032": "solidarite",
    "030": "quartier",
    "024": "environnement",
    "014": "communautes", "040": "communautes",
}  # fmt: skip

# Catégorie / rubrique de l'annuaire municipal -> genre (prioritaire sur le RNA)
MAIRIE_GENRE = {
    "Sport": "sport",
    "Culture": "culture",
    "Quartier": "quartier",
    "Scolaire": "education",
    "Animalier": "environnement",
    "Environnement": "environnement",
    "Caritatif": "solidarite",
    "Solidarité / santé / handicap": "solidarite",
    "Socio-éducatif": "education",
    "Loisirs divers": "loisirs",
    "Évenementiel": "loisirs",
}

# Activité -> motifs regex (sur texte normalisé). Une association peut en avoir plusieurs.
ACTIVITES = {
    "danse": r"dans(e|es|eurs?|euses?)|dance|ori tahiti|hip hop|zumba|salsa|kizomba|country|tamure|ballet|modern jazz|break ?dance",
    "ori tahiti": r"ori tahiti|tamure|otea|aparima|danses? polynesiennes?|danses? tahitiennes?",
    "hip-hop": r"hip ?hop|break ?dance|krump",
    "zumba": r"zumba",
    "musique": r"musique|musical(e|es)?|musiciens?|orchestre|fanfare|guitare|piano|ukulele|an?gklung|solfege|chant choral",
    "chant": r"chants?|chorales?|choeurs?",
    "théâtre": r"theatre|comedie|improvisation|marionnettes?",
    "cirque": r"cirque|jonglage|acrobaties?",
    "arts plastiques": r"peinture|dessin|sculpture|arts plastiques|arts graphiques|poterie|ceramique",
    "photo & vidéo": r"photo|photographie|video|cinema|audiovisuel",
    "artisanat": r"artisanat|couture|tressage|vannerie|tricot|broderie|patchwork",
    "lecture & écriture": r"lecture|livres?|bibliotheque|litterature|ecriture|contes?|poesie",
    "langues": r"langues?|anglais|linguistique",
    "football": r"football|foot|futsal|soccer",
    "rugby": r"rugby",
    "basket": r"basket|basketball|basket ball",
    "handball": r"handball|hand ball",
    "volley": r"volley|volleyball|volley ball",
    "baseball": r"baseball|softball",
    "tennis": r"tennis(?! de table)",
    "tennis de table": r"tennis de table|ping pong",
    "badminton": r"badminton",
    "squash": r"squash",
    "athlétisme & course": r"athletisme|athletic|athle|course a pied|course sur piste|running|trail|jogging|marathon|run|saut en (?:longueur|hauteur)",
    "cyclisme": r"cyclisme|cycliste|velo|vtt|bmx",
    "natation": r"natation|nage|aquatique|sauvetage|baignade|aquagym",
    "plongée": r"plongee|apnee|subaquatiques?|chasse sous marine",
    "va'a": r"va a|vaa|pirogues?|waka",
    "voile & glisse": r"voile|nautisme|kite ?surf|planche a voile|catamaran|surf|bodyboard|paddle|glisse",
    "kayak": r"kayak|canoe",
    "arts martiaux": r"arts? martia(l|ux)|judo|jujitsu|ju jitsu|jiu jitsu|karate|taekwondo|tae kwondo|aikido|kung fu|wushu|silat|kendo|capoeira|self defense|krav maga",
    "judo": r"judo|jujitsu|ju jitsu|jiu jitsu",
    "karaté": r"karate",
    "taekwondo": r"taekwondo|tae kwondo",
    "aïkido": r"aikido",
    "boxe & combat": r"boxe|aeroboxe|boxing|kick ?boxing|muay thai|mma|fight|lutte|sports de combat",
    "gym & fitness": r"gym|gymnastique|gymnique|fitness|musculation|crossfit|pilates|aerobic|remise en forme|renforcement musculaire|workout|tai ?chi|stretching|forme et de sante",
    "yoga": r"yoga",
    "force athlétique": r"force athletique|halterophilie|powerlifting|barbell",
    "équitation": r"equitation|equestre|chevaux|cheval|poneys?|cavaliers?|rodeo|ranch|hippique|dressage|saut d obstacles?|concours complet",
    "golf": r"golf",
    "pétanque": r"petanque|boules?|boulistes?",
    "échecs": r"echecs",
    "randonnée": r"randonnees?|rando|pedestre|marche nordique|trekking|course d orientation|orientation",
    "escalade": r"escalade|grimpe|canyoning",
    "roller & skate": r"roller|skate|skateboard|rolling|trottinette",
    "sports mécaniques": r"karting|kart|moto|motocross|automobiles?|jet ?ski|jet cross|4 ?x ?4|quad|rallye|enduro",
    "sports aériens": r"ulm|aviation|aeromodelisme|parachutisme|parapente|aeroclub",
    "tir": r"tir|tir a l arc|ball trap|carabine|pistolet",
    "pêche & chasse": r"peche|chasse(?! sous marine)",
    "sport canin": r"canin|cynophile|agility",
    "jardinage": r"jardins?|jardinage|potager|maraichage|permaculture",
    "environnement": r"environnement|nature|ecologie|biodiversite|riviere|reboisement|dechets|recyclage|pollution",
    "animaux": r"animaux|animale?|protection animale|chats",
    "soutien scolaire": r"aide aux devoirs|soutien scolaire|accompagnement scolaire|alphabetisation",
    "informatique": r"informatique|numerique|robotique|codage|programmation",
    "scoutisme": r"scouts?|scoutisme|guides de france|eclaireurs",
    "jeux": r"jeux de societe|jeux video|e ?sport|ludotheque|bridge|belote|scrabble",
    "cuisine": r"cuisine|culinaire|gastronomie|patisserie",
    "santé": r"sante|malades?|maladies?|patients|diabet(e|iques)|dialyses?|cancer|sida|dons? de sang",
    "handicap": r"handicaps?|handicapes?|handisport|handikart",
    "aide alimentaire": r"aide alimentaire|colis alimentaires?|epicerie solidaire|banque alimentaire",
    "parents d'élèves": r"parents d eleves?|ape",
    "cultures du Pacifique": r"kanak|wallis|futuna|wallisien(ne)?s?|futunien(ne)?s?|tahiti|tahitien(ne)?s?|polynesi(e|en|enne)s?|oceanien(ne)?s?|vanuatu|fidji|fiji|samoa|tonga|melanesien(ne)?s?",
    "religion": r"eglises?|paroisses?|cultes?|chretien(ne)?s?|evangeliques?|adventistes?|temples?|bible|priere|spirituel(le)?s?",
}  # fmt: skip
_ACTIVITES_RE = {k: re.compile(rf"\b(?:{v})\b") for k, v in ACTIVITES.items()}

PUBLICS = {
    "enfants": r"enfants?|enfance|bebes?|bambins?|eveil|baby|kids?|poussins?|benjamins?|ecoliers?|periscolaire"
    r"|ecole (?:de |d )?(?:foot|football|rugby|tennis|danse|musique|cirque|natation|judo|voile|va a)",
    "jeunes": r"jeunes?|jeunesse|adolescents?|ados?|collegiens?|lyceens?|etudiants?|juniors?|cadets?",
    "adultes": r"adultes?",
    "seniors": r"seniors?|personnes agees|aines|retraites?|troisieme age|inter ?ages?",
}
_PUBLICS_RE = {k: re.compile(rf"\b(?:{v})\b") for k, v in PUBLICS.items()}

_AGE_RANGE = re.compile(r"\b(\d{1,2}) (?:a |et )?(\d{1,2}) ans\b")
_AGE_MIN = re.compile(r"\b(?:a partir de|des|plus de|au dela de) (\d{1,2}) ans\b")
_AGE_MAX = re.compile(r"\b(?:moins de|jusqu a) (\d{1,2}) ans\b")


def genre(categorie_mairie: str | None, rubrique: str | None, codes: list[str]) -> str:
    for cle in (rubrique, categorie_mairie):
        if cle in MAIRIE_GENRE:
            return MAIRIE_GENRE[cle]
    for code in codes:
        if g := WALDEC_GENRE.get(code[:3]):
            return g
    return "autres"


def activites(texte_norm: str) -> list[str]:
    return [k for k, rx in _ACTIVITES_RE.items() if rx.search(texte_norm)]


def publics(texte_norm: str) -> list[str]:
    return [k for k, rx in _PUBLICS_RE.items() if rx.search(texte_norm)]


def ages(texte_norm: str) -> tuple[int | None, int | None]:
    """Tranche d'âge explicite (min, max) trouvée dans le texte, sinon (None, None)."""
    if m := _AGE_RANGE.search(texte_norm):
        a, b = int(m.group(1)), int(m.group(2))
        if a < b:
            return a, b
    lo = int(m.group(1)) if (m := _AGE_MIN.search(texte_norm)) else None
    hi = int(m.group(1)) if (m := _AGE_MAX.search(texte_norm)) else None
    return lo, hi
