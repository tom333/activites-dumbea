from asso.equipements import installations

EQUIPS = [
    {
        "inst_numero": "I1", "inst_nom": "Salle omnisports d'Auteuil", "inst_adresse": "29 av. d'Auteuil",
        "inst_hs_bool": "Non", "equip_coordonnees": {"lat": -22.21, "lon": 166.47},
        "aps_name": ["Basket-Ball"], "equip_type_name": "Salle multisports (gymnase)",
        "equip_nom": "Salle omnisports", "equip_acc_libre": "false",
    },
    {
        "inst_numero": "I2", "inst_nom": "Terrain de football Dumbéa Rivière", "inst_adresse": "RT1",
        "inst_hs_bool": "Non", "equip_coordonnees": {"lat": -22.15, "lon": 166.46},
        "aps_name": ["Football / Football en salle (Futsal)"], "equip_type_name": "Terrain de football",
        "equip_nom": "Terrain de football de Dumbéa Rivière", "equip_acc_libre": "true",
    },
    {  # hors service : ignoré
        "inst_numero": "I3", "inst_nom": "Vieux plateau", "inst_hs_bool": "Oui",
        "equip_coordonnees": {"lat": 0, "lon": 0}, "aps_name": ["Tennis"],
    },
]  # fmt: skip
CARTE = [
    {"installation": "es-I1", "lieu_carte_mairie": "Complexe sportif d'Auteuil",
     "activites": "judo, danse polynésienne", "lon": "", "lat": ""},
    {"installation": "mairie-x", "lieu_carte_mairie": "Plateau X",
     "activites": "volley-ball", "lon": "166.4", "lat": "-22.2"},
]  # fmt: skip


def test_installations():
    lieux = {i["id"]: i for i in installations(EQUIPS, CARTE)}
    assert set(lieux) == {"es-I1", "es-I2", "mairie-x"}
    auteuil = lieux["es-I1"]
    assert {"basket", "judo", "danse", "ori tahiti"} <= set(auteuil["activites"])
    assert "cultures du Pacifique" not in auteuil["activites"]
    assert auteuil["complexe"] == "Complexe sportif d'Auteuil"
    assert auteuil["sources"] == ["data-es", "carte-mairie-2022"]
    assert lieux["es-I2"]["activites"] == [
        "football"
    ]  # « Rivière » n'ajoute pas « environnement »
    assert lieux["es-I2"]["acces_libre"] is True
    assert lieux["mairie-x"]["lat"] == -22.2
