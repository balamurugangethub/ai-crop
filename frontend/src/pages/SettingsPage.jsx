import { useEffect, useState } from 'react'
import { api } from '../api'
import { LanguageSwitch, useAuth } from '../App'
import { useI18n } from '../i18n'
import { Alert } from '../components'

const pretty = (c) => c.replace('___', ' — ').replace(/_/g, ' ')

export default function SettingsPage() {
  const { t, tErr } = useI18n()
  const { user, setUser, signOut } = useAuth()
  const [village, setVillage] = useState(user?.village || '')
  const [saved, setSaved] = useState(false)
  const [model, setModel] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => { api('/api/model').then(setModel).catch(() => {}) }, [])

  const save = async (e) => {
    e.preventDefault()
    try { setUser(await api('/api/me', { method: 'PATCH', body: { village } })); setSaved(true) } catch (ex) { setErr(tErr(ex.code)) }
  }

  return (
    <div className="page">
      <h1>{t('settings')}</h1>
      <div className="card">
        <h3>{t('languageSettings')}</h3>
        <LanguageSwitch />
      </div>
      <form className="card form" onSubmit={save}>
        <p><strong>{user?.name}</strong> · {user?.phone}</p>
        <label>{t('village')}<input value={village} onChange={(e) => { setVillage(e.target.value); setSaved(false) }} /></label>
        <button className="btn btn-secondary">{saved ? '✓' : 'OK'}</button>
        {err && <Alert kind="error">{err}</Alert>}
      </form>
      {model && (
        <div className="card model-info">
          <h3>{t('modelInfo')}</h3>
          <p className="small">{model.architecture}</p>
          <p><strong>{t('modelAccuracy')}:</strong> {(model.test_accuracy_supported_classes * 100).toFixed(1)}%</p>
          <p className="small"><strong>{t('modelDataset')}:</strong> {model.dataset}</p>
          <details><summary>{t('modelClasses')} ({model.classes.length})</summary>
            <ul className="small">{model.classes.map((c) => <li key={c}>{pretty(c)}</li>)}</ul>
          </details>
          <Alert kind="warn">{t('modelLimit')}</Alert>
        </div>
      )}
      <button className="btn btn-ghost btn-lg btn-block" onClick={signOut}>{t('logout')}</button>
    </div>
  )
}
