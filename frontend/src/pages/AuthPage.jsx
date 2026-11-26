import { useState } from 'react'
import { api } from '../api'
import { useAuth, LanguageSwitch } from '../App'
import { useI18n } from '../i18n'
import { Alert, FieldsArt } from '../components'

export default function AuthPage() {
  const { t, tErr, lang } = useI18n()
  const { signIn } = useAuth()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ name: '', phone: '', pin: '', village: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      const res = mode === 'login'
        ? await api('/api/auth/login', { method: 'POST', body: { phone: form.phone, pin: form.pin } })
        : await api('/api/auth/register', { method: 'POST', body: { ...form, language: lang } })
      signIn(res)
    } catch (ex) {
      setErr(ex.code === 'network' ? t('networkError') : tErr(ex.code))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <div className="auth-hero">
        <FieldsArt />
        <div className="auth-hero-text">
          <h1><span aria-hidden>🌱</span> {t('appName')}</h1>
          <p>{t('tagline')}</p>
        </div>
      </div>
      <div className="auth-card card">
        <LanguageSwitch />
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={mode === 'login'} className={mode === 'login' ? 'on' : ''} onClick={() => { setMode('login'); setErr('') }}>{t('login')}</button>
          <button role="tab" aria-selected={mode === 'register'} className={mode === 'register' ? 'on' : ''} onClick={() => { setMode('register'); setErr('') }}>{t('register')}</button>
        </div>
        <form onSubmit={submit} className="form">
          {mode === 'register' && (
            <label>{t('name')}<input value={form.name} onChange={set('name')} autoComplete="name" required maxLength={80} /></label>
          )}
          <label>{t('phone')}
            <input value={form.phone} onChange={set('phone')} inputMode="tel" autoComplete="tel" placeholder="98xxxxxxxx" required />
          </label>
          <label>{t('pin')}
            <input value={form.pin} onChange={set('pin')} type="password" inputMode="numeric" pattern="\d{4,6}" maxLength={6} required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
          </label>
          {mode === 'register' && (
            <label>{t('village')}<input value={form.village} onChange={set('village')} maxLength={120} /></label>
          )}
          {err && <Alert kind="error">{err}</Alert>}
          <button className="btn btn-primary btn-lg" disabled={busy}>
            {busy ? '…' : mode === 'login' ? t('login') : t('register')}
          </button>
        </form>
        <p className="muted small center">{t('supportedCrops')} {t('notSupportedYet')}</p>
      </div>
    </div>
  )
}
