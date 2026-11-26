import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { api, getToken, setToken } from './api'
import { LANGUAGES, LangContext, useI18n } from './i18n'
import { FieldsArt, Spinner } from './components'
import AuthPage from './pages/AuthPage'
import Dashboard from './pages/Dashboard'
import ScanPage from './pages/ScanPage'
import ReportPage from './pages/ReportPage'
import HistoryPage from './pages/HistoryPage'
import ShopsPage from './pages/ShopsPage'
import TipsPage from './pages/TipsPage'
import SettingsPage from './pages/SettingsPage'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

const LANG_KEY = 'cropdoctor.lang'
function initialLang() {
  try { return localStorage.getItem(LANG_KEY) || 'en' } catch { return 'en' }
}

export function LanguageSwitch({ compact = false }) {
  const { lang, setLang } = useI18n()
  return (
    <div className={`lang-switch ${compact ? 'compact' : ''}`} role="group" aria-label="Language">
      {LANGUAGES.map((l) => (
        <button key={l.code} type="button" className={lang === l.code ? 'on' : ''}
          aria-pressed={lang === l.code} onClick={() => setLang(l.code)}>{l.label}</button>
      ))}
    </div>
  )
}

function Shell({ children }) {
  const { t } = useI18n()
  const nav = [
    ['/', '🏠', 'home'], ['/scan', '📷', 'scan'], ['/reports', '📋', 'reports'],
    ['/shops', '🏪', 'shops'], ['/settings', '⚙️', 'settings'],
  ]
  return (
    <div className="shell">
      <header className="topbar">
        <NavLink to="/" className="brand">
          <span className="brand-mark" aria-hidden>🌱</span>
          <span>{t('appName')}</span>
        </NavLink>
        <nav className="topnav" aria-label="Main">
          {nav.map(([to, , key]) => (
            <NavLink key={to} to={to} end={to === '/'}>{t(key)}</NavLink>
          ))}
        </nav>
        <LanguageSwitch compact />
      </header>
      <main className="content">{children}</main>
      <nav className="bottomnav" aria-label="Main">
        {nav.map(([to, icon, key]) => (
          <NavLink key={to} to={to} end={to === '/'}>
            <span className="bn-icon" aria-hidden>{icon}</span><span>{t(key)}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

function Protected({ children }) {
  const { user } = useAuth()
  return user ? <Shell>{children}</Shell> : <Navigate to="/welcome" replace />
}

function Routed() {
  const { user } = useAuth()
  return (
    <Routes>
      <Route path="/welcome" element={user ? <Navigate to="/" replace /> : <AuthPage />} />
      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/scan" element={<Protected><ScanPage /></Protected>} />
      <Route path="/reports" element={<Protected><HistoryPage /></Protected>} />
      <Route path="/reports/:id" element={<Protected><ReportPage /></Protected>} />
      <Route path="/shops" element={<Protected><ShopsPage /></Protected>} />
      <Route path="/tips" element={<Protected><TipsPage /></Protected>} />
      <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  const [lang, setLangState] = useState(initialLang)
  const [user, setUser] = useState(null)
  const [booting, setBooting] = useState(!!getToken())

  const setLang = (code) => {
    setLangState(code)
    try { localStorage.setItem(LANG_KEY, code) } catch { /* ignore */ }
    if (getToken()) api('/api/me', { method: 'PATCH', body: { language: code } }).then(setUser).catch(() => {})
  }
  useEffect(() => { document.documentElement.lang = lang }, [lang])

  useEffect(() => {
    if (!getToken()) return
    api('/api/me').then((u) => {
      setUser(u)
      if (u.language) setLangState(u.language)
    }).catch(() => setToken(null)).finally(() => setBooting(false))
  }, [])

  const auth = useMemo(() => ({
    user,
    setUser,
    signIn: ({ token, user: u }) => { setToken(token); setUser(u); if (u.language) setLangState(u.language) },
    signOut: async () => { try { await api('/api/auth/logout', { method: 'POST' }) } catch { /* ignore */ } setToken(null); setUser(null) },
  }), [user])

  return (
    <LangContext.Provider value={{ lang, setLang }}>
      <AuthContext.Provider value={auth}>
        {booting ? (
          <div className="boot"><FieldsArt /><Spinner /></div>
        ) : (
          <BrowserRouter><Routed /></BrowserRouter>
        )}
      </AuthContext.Provider>
    </LangContext.Provider>
  )
}

