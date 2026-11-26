import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, imageUrl } from '../api'
import { useI18n } from '../i18n'
import { Alert, Spinner } from '../components'

export default function HistoryPage() {
  const { t, tErr, lang } = useI18n()
  const [items, setItems] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api(`/api/reports?lang=${lang}`).then(setItems)
      .catch((ex) => setErr(ex.code === 'network' ? t('networkError') : tErr(ex.code)))
  }, [lang]) // eslint-disable-line react-hooks/exhaustive-deps

  const remove = async (id) => {
    if (!window.confirm(t('confirmDelete'))) return
    try {
      await api(`/api/reports/${id}`, { method: 'DELETE' })
      setItems((xs) => xs.filter((x) => x.id !== id))
    } catch (ex) { setErr(tErr(ex.code)) }
  }

  return (
    <div className="page">
      <h1>{t('previousReports')}</h1>
      {err && <Alert kind="error">{err}</Alert>}
      {!items && !err && <Spinner />}
      {items?.length === 0 && (
        <div className="card empty"><p>{t('noReports')}</p><Link to="/scan" className="btn btn-primary">{t('scanCrop')}</Link></div>
      )}
      <ul className="history">
        {items?.map((r) => (
          <li key={r.id} className="card history-item">
            <Link to={`/reports/${r.id}`} className="history-link">
              {r.image_url ? <img src={imageUrl(r.image_url)} alt="" loading="lazy" /> : <span className="thumb-empty" />}
              <div>
                <strong>{r.status === 'ok' ? `${r.crop_name} — ${r.name}` : t(`status_${r.status}`)}</strong>
                <div className="small muted">
                  {new Date(r.created_at.replace(' ', 'T') + 'Z').toLocaleString()}
                  {r.status === 'ok' && ` · ${Math.round(r.confidence * 100)}%`}
                </div>
              </div>
            </Link>
            <button className="btn btn-ghost btn-sm" onClick={() => remove(r.id)}>{t('deleteReport')}</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
