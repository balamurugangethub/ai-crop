import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { api } from '../api'
import { useAuth } from '../App'
import { useI18n } from '../i18n'
import { Alert, Spinner } from '../components'

function FitBounds({ center, shops }) {
  const map = useMap()
  useEffect(() => {
    const pts = [[center.lat, center.lon], ...shops.map((s) => [s.lat, s.lon])]
    if (pts.length === 1) map.setView(pts[0], 13)
    else map.fitBounds(pts, { padding: [30, 30], maxZoom: 15 })
  }, [center, shops, map])
  return null
}

function ShopCard({ s, t, onFocus, active }) {
  const reason = s.match_reason === 'agrarian_tag' ? t('agrarianTag')
    : s.match_reason === 'government_office' ? t('govtOffice') : t('matchedByName')
  return (
    <li className={`card shop ${active ? 'active' : ''}`}>
      <button className="shop-head" onClick={onFocus}>
        <strong>{s.name || t('noName')}</strong>
        <span className="shop-dist">{(s.distance_m / 1000).toFixed(1)} {t('kmAway')}</span>
      </button>
      {s.name_ta && s.name_ta !== s.name && <div className="small">{s.name_ta}</div>}
      <div className="chips">
        <span className="chip">{reason}</span>
        {s.categories.map((c) => <span key={c} className="chip chip-soft">{c}</span>)}
      </div>
      <div className="small">{s.address || <span className="muted">{t('addressMissing')}</span>}</div>
      {s.opening_hours && <div className="small muted">🕒 {s.opening_hours}</div>}
      <div className="small stock">⚠️ {t('stockUnconfirmed')}</div>
      <div className="btn-row">
        {s.phone
          ? <a className="btn btn-secondary" href={`tel:${s.phone.split(';')[0].replace(/\s/g, '')}`}>📞 {t('call')}</a>
          : <span className="muted small">{t('phoneMissing')}</span>}
        <a className="btn btn-primary" href={s.directions.google} target="_blank" rel="noreferrer">🧭 {t('directions')}</a>
        <a className="btn btn-ghost btn-sm" href={s.osm_url} target="_blank" rel="noreferrer">{t('viewOnMap')}</a>
      </div>
    </li>
  )
}

export default function ShopsPage() {
  const { t, tErr } = useI18n()
  const { user } = useAuth()
  const [query, setQuery] = useState(user?.village || '')
  const [radius, setRadius] = useState(15000)
  const [places, setPlaces] = useState(null)
  const [center, setCenter] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  const [focus, setFocus] = useState(null)

  const fail = (ex) => setErr(ex.code === 'network' ? t('networkError') : tErr(ex.code))

  const search = async (c, r = radius) => {
    setCenter(c); setPlaces(null); setResult(null); setErr(''); setFocus(null)
    setBusy('shops')
    try { setResult(await api(`/api/shops?lat=${c.lat}&lon=${c.lon}&radius=${r}`)) } catch (ex) { fail(ex) } finally { setBusy('') }
  }

  const useLocation = () => {
    setErr('')
    if (!navigator.geolocation) { setErr(t('locationUnavailable')); return }
    setBusy('locate')
    navigator.geolocation.getCurrentPosition(
      (pos) => search({ lat: pos.coords.latitude, lon: pos.coords.longitude, label: t('you') }),
      (e) => { setBusy(''); setErr(e.code === 1 ? t('locationDenied') : t('locationUnavailable')) },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 })
  }

  const geocode = async (e) => {
    e.preventDefault()
    if (query.trim().length < 2) { setErr(tErr('invalid_location_query')); return }
    setErr(''); setBusy('geo'); setPlaces(null)
    try {
      const { results } = await api(`/api/geocode?q=${encodeURIComponent(query)}`)
      if (!results.length) setErr(t('locationUnavailable'))
      else if (results.length === 1) search({ ...results[0], label: results[0].name })
      else setPlaces(results)
    } catch (ex) { fail(ex) } finally { setBusy((b) => (b === 'geo' ? '' : b)) }
  }

  return (
    <div className="page shops-page">
      <h1>{t('findShops')}</h1>
      <div className="card">
        <button className="btn btn-primary btn-lg btn-block" onClick={useLocation} disabled={!!busy}>📍 {t('useMyLocation')}</button>
        <form className="search-row" onSubmit={geocode}>
          <label className="sr-only" htmlFor="village">{t('orEnterVillage')}</label>
          <input id="village" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('orEnterVillage')} />
          <button className="btn btn-secondary" disabled={!!busy}>{t('search')}</button>
        </form>
        <label className="radius">{t('radius')}:
          <select value={radius} onChange={(e) => { const r = Number(e.target.value); setRadius(r); if (center) search(center, r) }}>
            {[5000, 10000, 15000, 25000, 50000].map((r) => <option key={r} value={r}>{r / 1000} km</option>)}
          </select>
        </label>
      </div>

      {busy && <Spinner label={t('searching')} />}
      {err && <Alert kind="error">{err}</Alert>}

      {places && (
        <div className="card">
          <h3>{t('pickPlace')}</h3>
          <ul className="places">
            {places.map((p) => <li key={`${p.lat},${p.lon}`}><button className="linkish" onClick={() => search({ ...p, label: p.name })}>{p.name}</button></li>)}
          </ul>
        </div>
      )}

      {result && (
        <>
          <p className="note"><strong>{result.count}</strong> {t('shopsFound')} · {center.label}</p>
          <div className="map-wrap card">
            <MapContainer center={[center.lat, center.lon]} zoom={13} scrollWheelZoom={false} className="map">
              <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <FitBounds center={center} shops={result.shops} />
              <CircleMarker center={[center.lat, center.lon]} radius={9} pathOptions={{ color: '#1d4ed8', fillColor: '#3b82f6', fillOpacity: 0.9 }}>
                <Popup>{t('you')}</Popup>
              </CircleMarker>
              {result.shops.map((s) => (
                <CircleMarker key={s.id} center={[s.lat, s.lon]} radius={focus === s.id ? 11 : 8}
                  pathOptions={{ color: '#5b3a1e', fillColor: focus === s.id ? '#e0a526' : '#3f8f3a', fillOpacity: 0.95 }}>
                  <Popup>
                    <strong>{s.name || t('noName')}</strong><br />
                    {(s.distance_m / 1000).toFixed(1)} {t('kmAway')}<br />
                    <a href={s.directions.google} target="_blank" rel="noreferrer">{t('directions')}</a>
                  </Popup>
                </CircleMarker>
              ))}
            </MapContainer>
          </div>
          {result.count === 0 && <Alert kind="warn">{t('noShops')}</Alert>}
          <ul className="shop-list">
            {result.shops.map((s) => <ShopCard key={s.id} s={s} t={t} active={focus === s.id} onFocus={() => setFocus(s.id)} />)}
          </ul>
          <p className="small muted">{t('shopDataNote')} © <a href={result.attribution_url} target="_blank" rel="noreferrer">OpenStreetMap</a></p>
        </>
      )}
    </div>
  )
}
