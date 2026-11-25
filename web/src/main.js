import '@fontsource/atkinson-hyperlegible/latin-400.css'
import '@fontsource/atkinson-hyperlegible/latin-700.css'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'
import L from './leaflet.js'
import 'leaflet.markercluster'
import './style.css'
import { buildIndex, matchLieux, normalize, search } from './search.js'

// Couleurs de genre : contraste ≥ 4,5:1 sur blanc (utilisées aussi pour du texte).
const COLORS = {
  sport: '#2e6b30',
  culture: '#7b1fa2',
  loisirs: '#b45309',
  education: '#1d4ed8',
  solidarite: '#b91c1c',
  quartier: '#0e7490',
  environnement: '#4d7c0f',
  communautes: '#6d4c41',
  autres: '#475569',
}
const STATUTS = {
  actives: new Set(['confirmee', 'recente']),
  mairie: new Set(['confirmee']),
  toutes: new Set(['confirmee', 'recente', 'ancienne']),
}
const STATUT_BADGE = {
  confirmee: ['i-check', 'Annuaire de la mairie'],
  recente: ['i-clock', 'Déclarée il y a moins de 5 ans'],
  ancienne: ['i-alert', 'Sans nouvelle depuis 5 ans'],
}
const EXAMPLES = ['danse pour enfant de 5 ans', 'football', 'aide aux devoirs', "va'a", 'musique', 'seniors']
const PAGE = 40

const $ = (id) => document.getElementById(id)
const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
const safeUrl = (u) => (/^https?:\/\//i.test(u || '') ? u : null)
const formatTel = (t) => t.replace(/(\d{2})(?=\d)/g, '$1 ')
const icon = (id, cls = 'icon') => `<svg class="${cls}" aria-hidden="true"><use href="#${id}"/></svg>`
const isMobile = window.matchMedia('(max-width: 1023px)')
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
const scrollBehavior = () => (reducedMotion.matches ? 'auto' : 'smooth')

// --- état (synchronisé avec l'URL pour partager une recherche) ---
const params = new URLSearchParams(location.search)
const state = {
  query: params.get('q') || '',
  genres: new Set((params.get('genre') || '').split(',').filter(Boolean)),
  statut: STATUTS[params.get('statut')] ? params.get('statut') : 'actives',
  localisees: params.get('carte') === '1',
  limit: PAGE,
}
let data, index, genres
const markers = new Map()

function saveUrl() {
  const p = new URLSearchParams()
  if (state.query) p.set('q', state.query)
  if (state.genres.size) p.set('genre', [...state.genres].join(','))
  if (state.statut !== 'actives') p.set('statut', state.statut)
  if (state.localisees) p.set('carte', '1')
  history.replaceState(null, '', p.size ? `?${p}` : location.pathname)
}

// --- carte ---
// maxZoom 16 : la plupart des positions sont approximatives (quartier).
const map = L.map('map', { maxZoom: 16 }).setView([-22.18, 166.45], 12)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 16,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map)
const cluster = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 40 })
map.addLayer(cluster)
// Lieux de pratique : couche à part, non regroupée (peu nombreux, repères fixes).
const lieuxLayer = L.layerGroup().addTo(map)
const lieuMarkers = new Map()
const legend = L.control({ position: 'bottomleft' })
legend.onAdd = () => {
  const div = L.DomUtil.create('div', 'legend')
  div.innerHTML = '<span><i class="legend__dot"></i>Association</span><span><i class="legend__lieu"></i>Lieu de pratique</span>'
  return div
}
legend.addTo(map)

const lieuActivites = (l) => (l.activites_mairie?.length ? l.activites_mairie : l.pratiques || [])

function lieuMarker(l) {
  const acts = lieuActivites(l)
  return L.marker([l.lat, l.lon], {
    icon: L.divIcon({ className: 'lieu-pin', html: '<span></span>', iconSize: [28, 28] }),
    title: l.complexe || l.nom,
    alt: l.complexe || l.nom,
    zIndexOffset: -100,
  }).bindPopup(
    `<p class="popup__title">${esc(l.complexe || l.nom)}</p>` +
      (l.complexe && l.complexe !== l.nom ? `<p class="popup__genre">${esc(l.nom)}</p>` : '') +
      `<p class="popup__genre">Lieu de pratique${l.acces_libre ? ' · accès libre' : ''}</p>` +
      `<p>${esc(acts.slice(0, 12).join(', '))}${acts.length > 12 ? '…' : ''}</p>`,
  )
}

function markerFor(a, faded) {
  const html = `<span style="background:${COLORS[a.genre]}"></span>`
  const marker = L.marker([a.lat, a.lon], {
    icon: L.divIcon({ className: `dot${faded ? ' dot--faded' : ''}`, html, iconSize: [28, 28] }),
    title: a.nom,
    alt: a.nom,
  })
  const approx = a.precision === 'quartier' ? `<p class="popup__note">Position approximative : ${esc(a.quartier)}</p>` : ''
  return marker.bindPopup(
    `<p class="popup__title">${esc(a.nom)}</p><p class="popup__genre">${esc(genres[a.genre])}</p>${approx}` +
      `<button type="button" class="btn btn--small" data-focus="${esc(a.id)}">Voir la fiche</button>`,
  )
}

// --- rendu ---
const mapButton = (id) =>
  `<button type="button" class="btn btn--map" data-map="${esc(id)}">${icon('i-pin')}<span>Voir sur la carte</span></button>`

function card(a, faded) {
  const c = a.contact || {}
  const ages = a.age_min != null || a.age_max != null ? `${a.age_min ?? '?'} à ${a.age_max ?? '…'} ans` : null
  const pub = [...(a.publics || []), ages].filter(Boolean)
  const lieu =
    a.precision === 'quartier'
      ? `${esc(a.quartier)} <span class="muted">(position approximative)</span>`
      : a.adresse
        ? esc(a.adresse)
        : a.hors_dumbea
          ? 'Siège déclaré hors Dumbéa'
          : 'Adresse non communiquée'
  const objet = a.objet
    ? a.objet.length > 180
      ? `<details class="objet"><summary><span>${esc(a.objet.slice(0, 180))}…</span> <span class="more-link"></span></summary><p>${esc(a.objet)}</p></details>`
      : `<p class="objet">${esc(a.objet)}</p>`
    : ''
  const actions = [
    ...(c.tels || []).slice(0, 2).map((t) => `<a class="btn btn--action" href="tel:${esc(t)}">${icon('i-phone')}${esc(formatTel(t))}</a>`),
    ...(c.emails || []).slice(0, 1).map((m) => `<a class="btn btn--action" href="mailto:${esc(m)}" aria-label="Écrire à ${esc(m)}">${icon('i-mail')}E-mail</a>`),
    safeUrl(c.facebook) && `<a class="btn btn--action" href="${esc(c.facebook)}" target="_blank" rel="noopener">${icon('i-facebook')}Facebook</a>`,
    safeUrl(c.site) && `<a class="btn btn--action" href="${esc(c.site)}" target="_blank" rel="noopener">${icon('i-globe')}Site web</a>`,
  ].filter(Boolean)
  const [statutIcon, statutLabel] = STATUT_BADGE[a.statut]

  const locatable = a.lat != null
  return `<article class="card${faded ? ' card--faded' : ''}${locatable ? ' is-locatable' : ''}" id="asso-${esc(a.id)}" data-id="${esc(a.id)}" tabindex="-1">
    <div class="card__head">
      <p class="genre" style="--c:${COLORS[a.genre]}"><span class="genre__dot"></span>${esc(genres[a.genre])}</p>
      ${locatable ? mapButton(a.id) : ''}
    </div>
    <h3>${esc(a.nom)}</h3>
    <p class="statut statut--${a.statut}">${icon(statutIcon, 'icon icon--sm')}${esc(statutLabel)}</p>
    ${a.activites?.length ? `<ul class="tags" aria-label="Activités">${a.activites.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
    ${pub.length ? `<p class="line"><strong>Public :</strong> ${esc(pub.join(' · '))}</p>` : ''}
    ${a.rubriques?.length ? `<p class="line muted">Annuaire : ${esc(a.rubriques.join(' · '))}</p>` : ''}
    ${objet}
    <p class="line lieu">${icon('i-pin', 'icon icon--sm')}<span>${lieu}</span></p>
    ${a.ridet ? `<p class="line muted">Registre RIDET n° ${esc(a.ridet)}${a.ridet_radiee ? ' — <strong>radiée</strong>' : ''} ·
      <a href="https://annuaire-entreprises.gouv.nc/entreprise/${encodeURIComponent(a.ridet)}" target="_blank" rel="noopener">fiche officielle</a></p>` : ''}
    ${actions.length ? `<div class="actions">${actions.join('')}</div>` : ''}
  </article>`
}

function renderGenres(counts) {
  $('genres').innerHTML = Object.entries(genres)
    .map(([k, label]) => {
      const on = state.genres.has(k)
      return `<button type="button" class="chip${on ? ' is-on' : ''}" style="--c:${COLORS[k]}" data-genre="${k}" aria-pressed="${on}">
        <span class="chip__dot"></span>${esc(label)}<span class="chip__count">${counts[k] || 0}</span></button>`
    })
    .join('')
  const n = state.genres.size + (state.statut !== 'actives') + state.localisees
  $('filters-count').hidden = !n
  $('filters-count').textContent = n
  $('filters-open').setAttribute('aria-label', n ? `Filtres (${n} actif${n > 1 ? 's' : ''})` : 'Filtres')
}

function renderSummary(parsed, total) {
  const crit = [
    ...parsed.terms.map((t) => `activité : ${t}`),
    parsed.age !== null ? `${parsed.age} ans` : null,
    ...parsed.publics.map((p) => `public : ${p}`),
  ].filter(Boolean)
  $('summary').innerHTML =
    `<p class="summary__count"><strong>${total}</strong> association${total > 1 ? 's' : ''}</p>` +
    (crit.length ? `<ul class="criteria" aria-label="Critères compris">${crit.map((c) => `<li>${esc(c)}</li>`).join('')}</ul>` : '')
  $('examples').hidden = Boolean(state.query)
  $('filters-apply').textContent = `Voir ${total} résultat${total > 1 ? 's' : ''}`
}

function renderEmpty() {
  const widen = state.statut !== 'toutes' || state.genres.size || state.localisees
  return `<div class="empty">
    <p><strong>Aucune association trouvée.</strong></p>
    <p>Essayez un mot plus simple (« danse » plutôt que « danseuse classique ») ou un exemple ci-dessous.</p>
    ${widen ? '<button type="button" class="btn btn--primary" data-widen>Chercher dans toutes les associations</button>' : ''}
  </div>`
}

function renderLieux(lieux, terms) {
  if (!lieux.length) return ''
  const rxs = terms.map((t) => new RegExp(`\\b${t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`))
  const hit = (a) => rxs.some((rx) => rx.test(normalize(a)))
  const items = lieux
    .map((l) => {
      const acts = lieuActivites(l)
      // Activités correspondant à la recherche d'abord, en gras ; puis quelques autres.
      const oui = acts.filter(hit)
      const autres = acts.filter((a) => !hit(a))
      const liste = [...oui.map((a) => `<strong>${esc(a)}</strong>`), ...autres.slice(0, 5).map(esc)]
      return `<li class="lieu-item is-locatable" data-id="${esc(l.id)}">
        <div class="card__head">
          <p class="lieu-item__nom">${esc(l.complexe || l.nom)}</p>
          ${mapButton(l.id)}
        </div>
        ${l.complexe && l.complexe !== l.nom ? `<p class="line muted">${esc(l.nom)}</p>` : ''}
        <p class="line">${liste.join(', ')}${autres.length > 5 ? '…' : ''}</p>
        <p class="line muted">${l.acces_libre ? '<strong class="libre">Accès libre</strong> · ' : ''}${esc(l.adresse || '')}</p>
      </li>`
    })
    .join('')
  const open = !isMobile.matches || lieux.length <= 2 ? ' open' : ''
  return `<details class="lieux"${open}>
    <summary class="group">${icon('i-pin')}Où pratiquer à Dumbéa <span class="group__n">${lieux.length}</span></summary>
    <p class="hint">Équipements où cette activité est proposée. La source n'indique pas quels clubs les utilisent.</p>
    <ul class="lieux__list">${items}</ul>
  </details>`
}

function render() {
  const filters = { genres: state.genres, statuts: STATUTS[state.statut], localisees: state.localisees }
  const { parsed, correspond, aVerifier } = search(data.associations, index, state.query, filters)
  const all = search(data.associations, index, state.query, { ...filters, genres: new Set() })
  const counts = {}
  for (const a of [...all.correspond, ...all.aVerifier]) counts[a.genre] = (counts[a.genre] || 0) + 1

  renderGenres(counts)
  renderSummary(parsed, correspond.length + aVerifier.length)
  saveUrl()

  let budget = state.limit
  const take = (list) => {
    const shown = list.slice(0, Math.max(0, budget))
    budget -= shown.length
    return shown
  }
  const shownOk = take(correspond)
  const shownMaybe = take(aVerifier)
  const lieux = matchLieux(data.equipements || [], parsed)
  let html = renderLieux(lieux, parsed.terms)
  if (!correspond.length && !aVerifier.length) {
    html += renderEmpty()
  } else {
    if (parsed.publics.length) {
      html += `<h2 class="group">${icon('i-check')}Correspondent au public recherché <span class="group__n">${correspond.length}</span></h2>`
      if (!correspond.length) html += '<p class="hint">Aucune fiche ne mentionne explicitement ce public.</p>'
    }
    html += shownOk.map((a) => card(a, false)).join('')
    if (aVerifier.length) {
      html += `<h2 class="group">${icon('i-help')}À vérifier <span class="group__n">${aVerifier.length}</span></h2>
        <p class="hint">Activité trouvée, mais le public ou l'âge n'est pas précisé. Contactez l'association.</p>`
      html += shownMaybe.map((a) => card(a, true)).join('')
    }
    const rest = correspond.length + aVerifier.length - state.limit
    if (rest > 0) html += `<button type="button" id="more" class="btn btn--ghost btn--block">Afficher ${Math.min(rest, PAGE)} de plus</button>`
  }
  $('results').innerHTML = html

  cluster.clearLayers()
  markers.clear()
  const layers = []
  for (const [list, faded] of [[correspond, false], [aVerifier, true]]) {
    for (const a of list) {
      if (a.lat == null) continue
      const m = markerFor(a, faded)
      markers.set(a.id, m)
      layers.push(m)
    }
  }
  cluster.addLayers(layers)

  // Lieux : ceux de la recherche, ou tous si aucune activité n'est cherchée.
  lieuxLayer.clearLayers()
  lieuMarkers.clear()
  for (const l of parsed.terms.length ? lieux : data.equipements || []) {
    const m = lieuMarker(l).addTo(lieuxLayer)
    lieuMarkers.set(l.id, m)
  }
}

// --- vues mobile (liste / carte) ---
function setView(view) {
  document.body.dataset.view = view
  const toMap = view === 'carte'
  $('view-toggle').innerHTML = toMap ? `${icon('i-list')}<span>Liste</span>` : `${icon('i-map')}<span>Carte</span>`
  $('view-toggle').setAttribute('aria-pressed', String(toMap))
  if (toMap) map.invalidateSize()
}

function select(id) {
  document.querySelectorAll('.is-selected').forEach((el) => el.classList.remove('is-selected'))
  if (id) document.querySelector(`[data-id="${CSS.escape(id)}"]`)?.classList.add('is-selected')
}

function showOnMap(id) {
  const lieu = lieuMarkers.get(id)
  const m = markers.get(id)
  if (!lieu && !m) return
  select(id)
  if (isMobile.matches) setView('carte')
  if (lieu) {
    map.setView(lieu.getLatLng(), 15)
    lieu.openPopup()
  } else {
    cluster.zoomToShowLayer(m, () => m.openPopup())
  }
}

function focusCard(id) {
  if (isMobile.matches) setView('liste')
  let el = $(`asso-${id}`)
  while (!el && state.limit < data.associations.length) {
    state.limit += PAGE
    render()
    el = $(`asso-${id}`)
  }
  if (!el) return
  el.scrollIntoView({ behavior: scrollBehavior(), block: 'center' })
  el.focus({ preventScroll: true })
  el.classList.add('card--flash')
  setTimeout(() => el.classList.remove('card--flash'), 1600)
}

// --- panneau de filtres (bottom sheet sur mobile, colonne sur ordinateur) ---
function openFilters() {
  const f = $('filters')
  f.classList.add('is-open')
  f.setAttribute('role', 'dialog')
  f.setAttribute('aria-modal', 'true')
  $('filters-scrim').hidden = false
  $('filters-open').setAttribute('aria-expanded', 'true')
  $('filters-close').focus()
}
function closeFilters() {
  const f = $('filters')
  if (!f.classList.contains('is-open')) return
  f.classList.remove('is-open')
  f.removeAttribute('role')
  f.removeAttribute('aria-modal')
  $('filters-scrim').hidden = true
  $('filters-open').setAttribute('aria-expanded', 'false')
  $('filters-open').focus()
}
isMobile.addEventListener('change', () => {
  closeFilters()
  setView('liste')
  map.invalidateSize()
})

// --- événements ---
const update = (changes) => {
  Object.assign(state, changes, { limit: PAGE })
  render()
}
let timer
$('q').addEventListener('input', (e) => {
  clearTimeout(timer)
  timer = setTimeout(() => update({ query: e.target.value }), 150)
})
$('search-form').addEventListener('submit', (e) => {
  e.preventDefault()
  clearTimeout(timer)
  update({ query: $('q').value })
  $('q').blur() // ferme le clavier mobile
})
$('statut').addEventListener('change', (e) => update({ statut: e.target.value }))
$('localisees').addEventListener('change', (e) => update({ localisees: e.target.checked }))
$('genres').addEventListener('click', (e) => {
  const g = e.target.closest('[data-genre]')?.dataset.genre
  if (!g) return
  state.genres.has(g) ? state.genres.delete(g) : state.genres.add(g)
  update({})
  document.querySelector(`[data-genre="${g}"]`)?.focus()
})
$('filters-open').addEventListener('click', openFilters)
$('filters-close').addEventListener('click', closeFilters)
$('filters-apply').addEventListener('click', closeFilters)
$('filters-scrim').addEventListener('click', closeFilters)
$('filters-reset').addEventListener('click', () => {
  state.genres.clear()
  $('statut').value = 'actives'
  $('localisees').checked = false
  update({ statut: 'actives', localisees: false })
})
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeFilters()
})
$('examples').addEventListener('click', (e) => {
  const q = e.target.closest('[data-example]')?.dataset.example
  if (!q) return
  $('q').value = q
  update({ query: q })
})
$('results').addEventListener('click', (e) => {
  const t = e.target.closest('button')
  if (!t) {
    // Vue large (carte visible) : un clic sur la fiche, hors liens et texte dépliable, la montre.
    if (isMobile.matches || e.target.closest('a, summary, details.objet')) return
    if (window.getSelection()?.toString()) return // l'utilisateur sélectionne du texte
    const card = e.target.closest('.is-locatable')
    if (card) showOnMap(card.dataset.id)
    return
  }
  if (t.id === 'more') {
    state.limit += PAGE
    render()
  } else if (t.dataset.map) {
    showOnMap(t.dataset.map)
  } else if ('widen' in t.dataset) {
    state.genres.clear()
    $('statut').value = 'toutes'
    $('localisees').checked = false
    update({ statut: 'toutes', localisees: false })
  }
})
$('view-toggle').addEventListener('click', () => setView(document.body.dataset.view === 'carte' ? 'liste' : 'carte'))
map.on('popupclose', () => select(null))
map.on('popupopen', (e) => {
  e.popup.getElement()?.querySelector('[data-focus]')?.addEventListener('click', (ev) => {
    focusCard(ev.currentTarget.dataset.focus)
  })
})

// --- démarrage ---
$('examples').innerHTML =
  '<p class="examples__label">Exemples :</p>' +
  EXAMPLES.map((q) => `<button type="button" class="chip chip--example" data-example="${esc(q)}">${esc(q)}</button>`).join('')
$('q').value = state.query
$('statut').value = state.statut
$('localisees').checked = state.localisees

async function load() {
  try {
    const resp = await fetch(`${import.meta.env.BASE_URL}data/associations.json`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    data = await resp.json()
  } catch (err) {
    $('results').innerHTML = `<div class="empty" role="alert"><p><strong>Les données n'ont pas pu être chargées.</strong></p>
      <p>Vérifiez votre connexion puis réessayez.</p><button type="button" class="btn btn--primary" id="retry">Réessayer</button></div>`
    $('retry').addEventListener('click', load, { once: true })
    console.error(err)
    return
  }
  genres = data.genres
  index = buildIndex(data.associations)
  $('generated').textContent = `Données du ${new Date(data.genere_le).toLocaleDateString('fr-FR')}.`
  render()
}
load()
