// Recherche : texte libre (MiniSearch) + âge / public extraits de la requête.
// « danse pour enfant de 5 ans » -> termes ["danse"], âge 5, public "enfants".
import MiniSearch from 'minisearch'

export function normalize(s) {
  return (s || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

const PUBLIC_WORDS = {
  enfants: /\b(enfants?|petits?|bebes?|gamins?|kids?|fillettes?|garcons?)\b/g,
  jeunes: /\b(ados?|adolescents?|jeunes?|collegiens?|lyceens?)\b/g,
  adultes: /\badultes?\b/g,
  seniors: /\b(seniors?|retraites?|aines|personnes agees)\b/g,
}

// Mots vides de la requête (pas des critères d'activité).
const STOP = new Set(
  ('association associations asso club clubs de du des d la le les l un une pour qui que quel quels quelle ' +
    'quelles donne donnent donner propose proposent proposant cours lecon lecons a au aux en et ou dans sur ' +
    'avec mon ma mes son sa ses ans an age ages fait faire pratiquer cherche chercher je veux trouver dumbea ' +
    'activite activites ville pres moi enfant')
    .split(' '),
)

// Raccourcis courants -> vocabulaire des fiches.
const SYNONYMS = {
  foot: 'football',
  basket: 'basket',
  hand: 'handball',
  muscu: 'musculation',
  tahitienne: 'tahiti',
  tahitien: 'tahiti',
  polynesienne: 'polynesien',
  piscine: 'natation',
  nager: 'natation',
  peindre: 'peinture',
  dessiner: 'dessin',
  chanter: 'chant',
  danser: 'danse',
  pirogue: 'va a',
  vaa: 'va a',
  velo: 'cyclisme',
  karate: 'karate',
}

export function publicForAge(age) {
  if (age <= 11) return 'enfants'
  if (age <= 17) return 'jeunes'
  if (age <= 59) return 'adultes'
  return 'seniors'
}

export function parseQuery(q) {
  let n = normalize(q)
  let age = null
  const m = n.match(/\b(\d{1,2}) ?ans?\b/)
  if (m) {
    age = Number(m[1])
    n = n.replace(m[0], ' ')
  }
  const publics = []
  for (const [pub, rx] of Object.entries(PUBLIC_WORDS)) {
    if (n.match(rx)) {
      publics.push(pub)
      n = n.replace(rx, ' ')
    }
  }
  if (age !== null && !publics.includes(publicForAge(age))) publics.push(publicForAge(age))
  const terms = n
    .split(' ')
    .filter((t) => t.length > 1 && !STOP.has(t) && !/^\d+$/.test(t))
    .map((t) => SYNONYMS[t] || t)
  return { terms, age, publics }
}

const FIELDS = ['nom', 'activites', 'rubriques', 'activites_objet', 'objet']

// Mots grammaticaux exclus de l'index : sinon la recherche floue rapproche « danse » de « dans ».
const INDEX_STOP = new Set(
  ('dans de des du la le les et en un une pour par sur au aux avec ce ces cet cette son sa ses leur leurs ' +
    'qui que quoi dont ou est sont ne pas plus tout tous toute toutes etre avoir faire entre afin ainsi ' +
    'notre nos votre vos elle elles il ils nous vous on se si mais donc car l d s n c j qu')
    .split(' '),
)

export function buildIndex(associations) {
  const index = new MiniSearch({
    fields: FIELDS,
    storeFields: [],
    extractField: (doc, field) => {
      const v = doc[field]
      return Array.isArray(v) ? v.join(' ') : v || ''
    },
    processTerm: (t) => {
      const n = normalize(t)
      return n && !INDEX_STOP.has(n) ? n : null
    },
  })
  index.addAll(associations)
  return index
}

const SEARCH_OPTIONS = {
  boost: { activites: 4, rubriques: 3, nom: 3, activites_objet: 1.5, objet: 1 },
  prefix: (term) => term.length >= 4,
  fuzzy: (term) => (term.length >= 5 ? 0.2 : false),
}

// 'oui' : correspond explicitement ; 'non' : tranche d'âge explicite qui exclut ;
// 'inconnu' : aucune information sur le public.
export function publicMatch(asso, { age, publics }) {
  if (age !== null && (asso.age_min != null || asso.age_max != null)) {
    return (asso.age_min ?? 0) <= age && age <= (asso.age_max ?? 120) ? 'oui' : 'non'
  }
  if (!publics.length) return 'oui'
  return (asso.publics || []).some((p) => publics.includes(p)) ? 'oui' : 'inconnu'
}

/**
 * @param associations liste complète
 * @param index MiniSearch construit par buildIndex
 * @param query texte saisi
 * @param filters { genres: Set<string>, statuts: Set<string>, localisees: boolean }
 * @returns { parsed, correspond: asso[], aVerifier: asso[] }
 */
export function search(associations, index, query, filters) {
  const parsed = parseQuery(query)
  const keep = (a) =>
    (!filters.genres.size || filters.genres.has(a.genre)) &&
    filters.statuts.has(a.statut) &&
    (!filters.localisees || a.lat != null)

  let ranked
  if (parsed.terms.length) {
    const q = parsed.terms.join(' ')
    let hits = index.search(q, { ...SEARCH_OPTIONS, combineWith: 'AND' })
    if (!hits.length) hits = index.search(q, { ...SEARCH_OPTIONS, combineWith: 'OR' })
    const byId = new Map(associations.map((a) => [a.id, a]))
    ranked = hits.map((h) => byId.get(h.id))
  } else {
    ranked = associations // déjà triées : confirmées, récentes, anciennes
  }

  const correspond = []
  const aVerifier = []
  for (const a of ranked) {
    if (!keep(a)) continue
    const m = publicMatch(a, parsed)
    if (m === 'oui') correspond.push(a)
    else if (m === 'inconnu') aVerifier.push(a)
  }
  return { parsed, correspond, aVerifier }
}

/**
 * Lieux de pratique correspondant aux termes de la recherche (aucun terme -> aucun lieu).
 * Un terme correspond s'il commence un mot du nom ou des activités du lieu.
 */
export function matchLieux(lieux, { terms }) {
  if (!terms.length) return []
  const rxs = terms.map((t) => new RegExp(`\\b${t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`))
  return lieux.filter((l) => {
    const hay = normalize(
      [l.nom, l.complexe, ...(l.activites || []), ...(l.activites_mairie || []), ...(l.pratiques || [])].join(' '),
    )
    return rxs.some((rx) => rx.test(hay))
  })
}
