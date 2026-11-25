from asso import classify
from asso.annuaire import parse_page
from asso.build import joli_nom
from asso.clean import fix_text, norm
from asso.match import tokens

PAGE = """
<div class="field--name-field-item-body">
  <table><tr><td><a href="#a">A</a></td></tr></table>
  <h1 id="a_no_init_scroll">A</h1>
  <ul><li><strong><u>AÏKIDO</u></strong></li></ul>
  <p><strong>Aïkido Club de Dumbéa (ACD)</strong><br>Tél. : 78 65 28 / 82 04 40<br>
     Mail : <a href="mailto:aikido@example.nc">aikido@example.nc</a><br>
     <a href="https://www.facebook.com/aikido">Page Facebook</a></p>
  <h1 id="arts_divers_no_init_scroll">Arts divers</h1>
  <p><br><strong>Association </strong><span><strong>Mathiila </strong></span><em>(arts vivants)</em>
     <br>Tél. : 72 40 33</p>
  <p><strong>A</strong><span><strong>ssociation Valentin-Haüy</strong></span><br>Tél. : 24 11 15</p>
  <p>Paragraphe sans fiche.</p>
</div>
"""


def test_parse_page():
    e = parse_page(PAGE, "Sport")
    assert [x["nom"] for x in e] == [
        "Aïkido Club de Dumbéa (ACD)",
        "Association Mathiila",
        "Association Valentin-Haüy",
    ]
    assert e[0]["rubrique"] == "AÏKIDO"
    assert e[0]["tels"] == ["786528", "820440"]
    assert e[0]["emails"] == ["aikido@example.nc"]
    assert e[0]["facebook"] == "https://www.facebook.com/aikido"
    assert e[1]["rubrique"] == "Arts divers"
    assert e[1]["description"] == "arts vivants"


def test_fix_text_mojibake():
    assert fix_text("parents d'élÚves  nà°2") == "parents d'élèves n°2"


def test_norm():
    assert norm("Va'a — Ori Tahiti !") == "va a ori tahiti"


def test_activites():
    assert classify.activites(norm("Club de tennis de table")) == ["tennis de table"]
    assert classify.activites(norm("Tennis Club d'Auteuil")) == ["tennis"]
    assert "football" not in classify.activites(norm("footing et marche"))
    assert {"danse", "ori tahiti"} <= set(
        classify.activites(norm("cours de Ori Tahiti"))
    )
    assert "arts martiaux" in classify.activites(norm("Judo club"))


def test_publics_et_ages():
    t = norm("Cours de danse pour les enfants de 4 à 12 ans et les adultes")
    assert classify.publics(t) == ["enfants", "adultes"]
    assert classify.ages(t) == (4, 12)
    assert classify.ages(norm("ouvert dès 5 ans")) == (5, None)
    assert classify.ages(norm("réservé aux moins de 18 ans")) == (None, 18)
    assert classify.ages(norm("créée il y a 20 ans")) == (None, None)


def test_genre_priorite_mairie():
    assert classify.genre("Autres", "Animalier", ["011000"]) == "environnement"
    assert classify.genre(None, None, ["011075"]) == "sport"
    assert classify.genre(None, None, []) == "autres"


def test_tokens_ape():
    assert tokens("APE de l'école L'OASIS") == {"parents", "eleves", "ecole", "oasis"}


def test_joli_nom():
    assert joli_nom('" DUMBEA CLUB D\'ECHECS "') == "Dumbea Club d'Echecs"
    assert joli_nom("Déjà Bien Écrit") == "Déjà Bien Écrit"
