# Activités à Dumbéa

Trouver une activité à Dumbéa (Nouvelle-Calédonie) : associations, clubs et lieux de pratique,
sur une carte, par domaine, activité et âge — par exemple « danse pour enfant de 5 ans ».

**Site : https://tom333.github.io/activites-dumbea/**

Projet libre et non officiel, sans lien avec la Ville de Dumbéa. Les informations viennent de
données publiques et peuvent être incomplètes ou datées : vérifiez auprès de l'association.

## Comment ça marche

Un pipeline Python croise plusieurs sources publiques et produit `web/public/data/associations.json`.
Le site (Vite + Leaflet, sans serveur) charge ce fichier et fait la recherche dans le navigateur.

- **Associations actives** : listées dans l'annuaire de la mairie (« confirmée ») ou ayant fait une
  déclaration au RNA depuis moins de 5 ans (« récente »). Les autres sont masquées par défaut.
- **Recherche** : « danse pour enfant de 5 ans » est compris comme activité *danse*, âge *5 ans*,
  public *enfants*. Les associations dont les textes ne précisent pas le public sont listées à part,
  « à vérifier ».
- **Où pratiquer** : installations sportives où l'activité est proposée. Aucune source ne dit quel
  club utilise quelle salle.
- **Vie privée** : l'adresse du siège n'est affichée que si l'association a autorisé sa publication
  au RNA (`ispublic = oui`) ; sinon la position est arrondie au quartier. Les noms des dirigeants
  ne sont pas repris.

## Sources

| Source | Licence | Usage |
|---|---|---|
| [Répertoire des associations de Nouvelle-Calédonie (RNA)](https://data.gouv.nc/explore/dataset/rna-nc/) | Licence Ouverte 2.0 | base : objet, codes WALDEC, déclarations, siège |
| [Annuaire des associations de la Ville de Dumbéa](https://www.ville-dumbea.nc/annuaire-des-associations) | site de la Ville | associations actives, rubrique d'activité, contacts |
| [Carte des infrastructures sportives de la Ville (2022)](https://www.ville-dumbea.nc/sites/default/files/datocms/1685579402-carte-infras-sportives-2022.jpg) | site de la Ville | activités proposées par complexe |
| [Data ES – équipements sportifs](https://www.data.gouv.fr/datasets/recensement-des-equipements-sportifs-espaces-et-sites-de-pratiques) | Licence Ouverte 2.0 | lieux de pratique : position, activités, accès libre |
| [Annuaire des entreprises NC (RIDET)](https://annuaire-entreprises.gouv.nc) | API publique | n° RIDET, lien officiel, radiation, activité déclarée ; adresse d'établissement utilisée seulement pour situer le quartier |
| [API Localisation NC](https://localisation.gouv.nc/api/openapi) | API publique | géocodage des adresses |
| [Nomenclature WALDEC](https://data.orleans-metropole.fr/explore/dataset/rna-associations-nomenclature-waldec/) | Licence Ouverte | libellés des codes d'objet social |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | ODbL | fond de carte |

Fichiers de référence maintenus à la main (`data/ref/`) :

- `rapprochements.csv` : corrections du rapprochement annuaire mairie ↔ RNA (`rna_id` vide = aucune correspondance) ;
- `quartiers.csv` : coordonnées des quartiers de Dumbéa ;
- `lieux_activites_mairie.csv` : transcription de la carte 2022 de la Ville, reliée aux installations Data ES.

## Développement

```bash
# Données (Python ≥ 3.12, uv)
cd pipeline
uv run python -m asso.build            # utilise le cache data/raw/
uv run python -m asso.build --refresh  # retélécharge RNA, annuaire, RIDET, Data ES
uv run pytest

# Site (Node ≥ 20)
cd web
npm install
npm run dev      # http://localhost:5173
npm test
npm run build    # -> web/dist/
```

**Mettre à jour les données** (le RNA est republié chaque mois, le 3) : lancer
`uv run python -m asso.build --refresh`, vérifier la sortie (rapprochements, nombre de fiches),
puis committer `web/public/data/associations.json`. Le site est redéployé automatiquement à chaque
push sur `main` (GitHub Actions → GitHub Pages).

## Contribuer

Une association manque, une information est fausse ? Ouvrez une
[issue](https://github.com/tom333/activites-dumbea/issues).

## Licence

Code sous licence [MIT](LICENSE). Les données restent sous la licence de leurs producteurs (voir Sources).
