import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api, imageUrl } from '../api'
import { useI18n } from '../i18n'
import { Alert, ConfidenceBar, DiseaseInfo, SpeakButton, Spinner } from '../components'

export default function ReportPage() {
  const { id } = useParams()
  const { state } = useLocation()
  const { t, tErr, lang } = useI18n()
  const [r, setR] = useState(state?.result?.report_id === Number(id) && state.result.disease?.language === lang ? state.result : null)
  const [err, setErr] = useState('')

  useEffect(() => {
    let live = true
    api(`/api/reports/${id}?lang=${lang}`).then((x) => live && setR(x))
      .catch((ex) => live && setErr(ex.code === 'network' ? t('networkError') : tErr(ex.code)))
    return () => { live = false }
  }, [id, lang]) // eslint-disable-line react-hooks/exhaustive-deps

  if (err) return <div className="page"><Alert kind="error">{err}</Alert></div>
  if (!r) return <div className="page"><Spinner /></div>
  const d = r.disease
  const summary = d ? `${d.crop_name}. ${d.name}. ${t('confidence')} ${Math.round(r.confidence * 100)}%. ${d.severity_note}` : ''

  return (
    <div className="page report">
      <h1>{t('result')}</h1>
      <div className="report-top card">
        {r.image_url && <img className="report-img" src={imageUrl(r.image_url)} alt="" />}
        <div className="report-main">
          <p className={`status status-${r.status}`} data-testid="status">{t(`status_${r.status}`)}</p>
          {r.status === 'ok' && d && (
            <>
              <p className="muted">{d.crop_name}</p>
              <h2 className="disease-name">{d.healthy ? `✅ ${d.name}` : d.name}</h2>
              {d.pathogen && <p className="muted small">{d.pathogen}</p>}
              <div className="conf-label">{t('confidence')}</div>
              <ConfidenceBar value={r.confidence} />
              <SpeakButton text={summary} />
            </>
          )}
          {r.status === 'uncertain' && <p>{t('status_uncertain_body')}</p>}
          {r.status === 'unsupported' && <p>{t('status_unsupported_body')}</p>}
          <p className="small muted">{new Date(r.created_at.replace(' ', 'T') + 'Z').toLocaleString()}</p>
        </div>
      </div>

      <Alert kind="warn">{t('notGuaranteed')}</Alert>

      {r.status === 'uncertain' && r.candidates.length > 0 && (
        <div className="card">
          <h3>{t('closestMatches')}</h3>
          <ul className="cands">
            {r.candidates.map((c) => (
              <li key={c.class_id}><span>{c.crop_name} — {c.name}</span><ConfidenceBar value={c.confidence} /></li>
            ))}
          </ul>
          <Link to="/scan" className="btn btn-primary">{t('changePhoto')}</Link>
        </div>
      )}
      {r.status === 'unsupported' && <Link to="/scan" className="btn btn-primary btn-lg">{t('changePhoto')}</Link>}

      {r.status === 'ok' && d && (
        <>
          <div className="card"><DiseaseInfo d={d} /></div>
          {!d.healthy && (
            <Link to="/shops" className="btn btn-primary btn-lg btn-block">🏪 {t('findShopsForThis')}</Link>
          )}
        </>
      )}
    </div>
  )
}
