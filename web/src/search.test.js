import { describe, expect, it } from 'vitest'
import { buildIndex, matchLieux, parseQuery, publicMatch, search } from './search.js'

describe('parseQuery', () => {
  it('extrait activité, âge et public', () => {
    expect(parseQuery('association de danse qui donnent des cours pour les enfants de 5 ans')).toEqual({
      terms: ['danse'],
      age: 5,
      publics: ['enfants'],
    })
  })
  it("déduit le public de l'âge", () => {
    expect(parseQuery('judo 14 ans')).toEqual({ terms: ['judo'], age: 14, publics: ['jeunes'] })
  })
  it('applique les synonymes', () => {
    expect(parseQuery('foot pour ados').terms).toEqual(['football'])
  })
  it('requête vide', () => {
    expect(parseQuery('')).toEqual({ terms: [], age: null, publics: [] })
  })
})

describe('publicMatch', () => {
  const q = { age: 5, publics: ['enfants'] }
  it('tranche explicite incluse / exclue', () => {
    expect(publicMatch({ age_min: 4, age_max: 12 }, q)).toBe('oui')
    expect(publicMatch({ age_min: 16 }, q)).toBe('non')
  })
  it('public déclaré', () => {
    expect(publicMatch({ publics: ['enfants', 'adultes'] }, q)).toBe('oui')
  })
  it('sans information', () => {
    expect(publicMatch({}, q)).toBe('inconnu')
  })
  it('sans critère de public', () => {
    expect(publicMatch({}, { age: null, publics: [] })).toBe('oui')
  })
})

describe('search', () => {
  const data = [
    { id: '1', nom: 'Te Mana Ori', genre: 'culture', statut: 'confirmee', activites: ['danse', 'ori tahiti'], publics: ['enfants'], lat: 1 },
    { id: '2', nom: 'Dumbéa Danse Country', genre: 'culture', statut: 'confirmee', activites: ['danse'] },
    { id: '3', nom: 'Judo Club', genre: 'sport', statut: 'confirmee', activites: ['judo'], publics: ['enfants'] },
    { id: '4', nom: 'Vieille danse', genre: 'culture', statut: 'ancienne', activites: ['danse'] },
    { id: '5', nom: 'Danse adultes', genre: 'culture', statut: 'recente', activites: ['danse'], age_min: 18 },
  ]
  const index = buildIndex(data)
  const filters = { genres: new Set(), statuts: new Set(['confirmee', 'recente']), localisees: false }
  const ids = (l) => l.map((a) => a.id)

  it('danse pour enfant de 5 ans', () => {
    const r = search(data, index, 'danse pour enfant de 5 ans', filters)
    expect(ids(r.correspond)).toEqual(['1'])
    expect(ids(r.aVerifier)).toEqual(['2']) // public inconnu ; 4 ancienne ; 5 exclue (18+)
  })
  it('filtre genre et localisation', () => {
    const r = search(data, index, '', { ...filters, genres: new Set(['culture']), localisees: true })
    expect(ids(r.correspond)).toEqual(['1'])
  })
  it('tolère les fautes', () => {
    expect(ids(search(data, index, 'dense', filters).correspond)).toContain('2')
  })
})

describe('matchLieux', () => {
  const lieux = [
    { id: 'a', nom: "Salle omnisports d'Auteuil", activites: ['danse', 'judo'], activites_mairie: ['danse polynésienne'] },
    { id: 'b', nom: 'Parc des sports', activites: ['football'] },
  ]
  it('par activité', () => {
    expect(matchLieux(lieux, parseQuery('danse pour enfant de 5 ans')).map((l) => l.id)).toEqual(['a'])
    expect(matchLieux(lieux, parseQuery('foot')).map((l) => l.id)).toEqual(['b'])
  })
  it('sans terme', () => {
    expect(matchLieux(lieux, parseQuery('5 ans'))).toEqual([])
  })
})
