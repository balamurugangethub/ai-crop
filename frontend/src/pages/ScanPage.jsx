import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useI18n } from '../i18n'
import { Alert, Spinner } from '../components'

const MAX_BYTES = 10 * 1024 * 1024

export default function ScanPage() {
  const { t, tErr, lang } = useI18n()
  const nav = useNavigate()
  const camRef = useRef()
  const fileRef = useRef()
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview])

  const pick = (e) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    setErr('')
    if (!/^image\/(jpeg|png|webp)$/.test(f.type)) { setErr(tErr('unsupported_format')); return }
    if (f.size > MAX_BYTES) { setErr(tErr('file_too_large')); return }
    setFile(f)
    setPreview(URL.createObjectURL(f))
  }

  const analyse = async () => {
    if (!file) return
    setBusy(true)
    setErr('')
    const form = new FormData()
    form.append('image', file)
    form.append('lang', lang)
    try {
      const res = await api('/api/diagnose', { method: 'POST', form })
      if (res.status === 'rejected') { setErr(tErr(res.message)); return }
      nav(`/reports/${res.report_id}`, { state: { result: res } })
    } catch (ex) {
      setErr(ex.code === 'network' ? t('networkError') : tErr(ex.code))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page scan">
      <h1>{t('scanCrop')}</h1>
      <p className="note">{t('supportedCrops')} {t('notSupportedYet')}</p>
      <div className="card">
        {preview ? (
          <img className="preview" src={preview} alt="" />
        ) : (
          <div className="drop">
            <span className="drop-icon" aria-hidden>🍃</span>
            <p>{t('photoTips')}</p>
          </div>
        )}
        <input ref={camRef} type="file" accept="image/*" capture="environment" hidden onChange={pick} data-testid="camera-input" />
        <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={pick} data-testid="file-input" />
        <div className="btn-row">
          <button className="btn btn-secondary btn-lg" onClick={() => camRef.current.click()} disabled={busy}>📷 {t('takePhoto')}</button>
          <button className="btn btn-secondary btn-lg" onClick={() => fileRef.current.click()} disabled={busy}>🖼️ {preview ? t('changePhoto') : t('uploadPhoto')}</button>
        </div>
        {err && <Alert kind="error" title={t('status_rejected')}>{err}</Alert>}
        {file && (
          busy ? <Spinner label={t('analysing')} />
            : <button className="btn btn-primary btn-lg btn-block" onClick={analyse}>{t('analyse')}</button>
        )}
      </div>
      {preview && <p className="muted small">{t('photoTips')}</p>}
    </div>
  )
}
