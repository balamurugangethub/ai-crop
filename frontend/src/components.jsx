import { useEffect, useState } from 'react'
import { useI18n } from './i18n'

/* ---------- Text to speech (browser Web Speech API) ---------- */
function useVoices() {
  const [voices, setVoices] = useState(() =>
    typeof window !== 'undefined' && window.speechSynthesis ? window.speechSynthesis.getVoices() : [])
  useEffect(() => {
    if (!window.speechSynthesis) return
    const update = () => setVoices(window.speechSynthesis.getVoices())
    window.speechSynthesis.addEventListener?.('voiceschanged', update)
    update()
    return () => window.speechSynthesis.removeEventListener?.('voiceschanged', update)
  }, [])
  return voices
}

export function SpeakButton({ text }) {
  const { t, speechLang } = useI18n()
  const voices = useVoices()
  const [speaking, setSpeaking] = useState(false)
  const [msg, setMsg] = useState('')
  const prefix = speechLang.split('-')[0]
  const voice = voices.find((v) => v.lang === speechLang) || voices.find((v) => v.lang?.startsWith(prefix))
  useEffect(() => () => window.speechSynthesis?.cancel(), [])

  const onClick = () => {
    if (!window.speechSynthesis || !voice) { setMsg(t('speechUnavailable')); return }
    if (speaking) { window.speechSynthesis.cancel(); setSpeaking(false); return }
    const u = new SpeechSynthesisUtterance(text)
    u.voice = voice
    u.lang = voice.lang
    u.rate = 0.9
    u.onend = u.onerror = () => setSpeaking(false)
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(u)
    setSpeaking(true)
  }
  return (
    <span className="speak">
      <button type="button" className="btn btn-ghost btn-sm" onClick={onClick} aria-pressed={speaking}>
        <span aria-hidden>{speaking ? '■' : '🔊'}</span> {speaking ? t('stop') : t('listen')}
      </button>
      {msg && <small className="muted">{msg}</small>}
    </span>
  )
}

/* ---------- Village & fields illustration (inline SVG, theme-aware) ---------- */
export function FieldsArt({ className = '' }) {
  return (
    <svg className={`fields-art ${className}`} viewBox="0 0 800 260" preserveAspectRatio="xMidYMax slice" aria-hidden>
      <defs>
        <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="var(--sky-top)" /><stop offset="1" stopColor="var(--sky-bottom)" />
        </linearGradient>
      </defs>
      <rect width="800" height="260" fill="url(#sky)" />
      <circle cx="660" cy="70" r="34" fill="var(--sun)" />
      {/* distant hills */}
      <path d="M0 150 Q120 95 250 140 T520 130 T800 120 V260 H0Z" fill="var(--hill)" />
      {/* palm trees */}
      <g fill="var(--tree)">
        <rect x="96" y="92" width="5" height="62" rx="2" />
        <path d="M98 92 q-30 -4 -44 14 q22 -10 44 -8 q-18 -18 -6 -32 q8 18 8 26 q10 -22 30 -22 q-14 12 -26 28 q26 -6 40 6 q-24 -6 -46 -12z" />
        <rect x="716" y="100" width="5" height="52" rx="2" />
        <path d="M718 100 q-26 -4 -38 12 q20 -8 38 -6 q-14 -16 -4 -28 q6 16 6 22 q8 -18 26 -18 q-12 10 -22 24 q22 -4 34 6 q-20 -6 -40 -12z" />
      </g>
      {/* village huts */}
      <g>
        <rect x="560" y="122" width="56" height="34" fill="var(--wall)" />
        <path d="M552 126 L588 98 L624 126Z" fill="var(--roof)" />
        <rect x="582" y="136" width="12" height="20" fill="var(--door)" />
        <rect x="628" y="130" width="40" height="26" fill="var(--wall)" />
        <path d="M622 133 L648 112 L674 133Z" fill="var(--roof)" />
      </g>
      {/* field rows */}
      <path d="M0 170 Q400 140 800 165 V260 H0Z" fill="var(--field-1)" />
      <path d="M0 200 Q400 172 800 196 V260 H0Z" fill="var(--field-2)" />
      <g stroke="var(--row)" strokeWidth="3" strokeLinecap="round" opacity=".55">
        {Array.from({ length: 14 }).map((_, i) => (
          <path key={i} d={`M${i * 60 - 20} 260 Q${i * 60 + 20} 215 ${i * 58 + 30} 185`} fill="none" />
        ))}
      </g>
      <path d="M0 232 Q400 212 800 228 V260 H0Z" fill="var(--field-3)" />
    </svg>
  )
}

export function Spinner({ label }) {
  return <div className="spinner-wrap" role="status"><span className="spinner" aria-hidden />{label && <span>{label}</span>}</div>
}

export function Alert({ kind = 'info', title, children }) {
  return (
    <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {title && <strong>{title}</strong>}
      {children && <div>{children}</div>}
    </div>
  )
}

export function ConfidenceBar({ value }) {
  // Never display 100%: a model estimate is never certain.
  const pct = Math.min(99, Math.round(value * 100))
  const level = value >= 0.9 ? 'high' : value >= 0.7 ? 'mid' : 'low'
  return (
    <div className="conf">
      <div className="conf-track"><div className={`conf-fill conf-${level}`} style={{ width: `${pct}%` }} /></div>
      <span className="conf-val">{pct}%</span>
    </div>
  )
}

function Section({ title, items, speak }) {
  if (!items?.length) return null
  return (
    <section className="info-sec">
      <div className="info-head">
        <h3>{title}</h3>
        {speak && <SpeakButton text={`${title}. ${items.join('. ')}`} />}
      </div>
      <ul>{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </section>
  )
}

export function DiseaseInfo({ d }) {
  const { t } = useI18n()
  return (
    <div className="disease-info">
      {!d.healthy && (
        <div className={`severity sev-${d.severity}`}>
          <div className="sev-row">
            <span>{t('severity')}:</span>
            <strong className="sev-badge">{t(`severity_${d.severity}`)}</strong>
          </div>
          <p>{d.severity_note}</p>
          <small className="muted">{t('severityNote')}</small>
        </div>
      )}
      {d.healthy && <p className="lead">{d.severity_note}</p>}
      {d.limited_source && <Alert kind="warn">{t('limitedSource')}</Alert>}
      <Section title={t('symptoms')} items={d.symptoms} speak />
      <Section title={t('causes')} items={d.causes} />
      <Section title={t('doNow')} items={d.do_now} speak />
      <Section title={t('prevention')} items={d.prevention} speak />
      <Section title={t('natural')} items={d.natural} />
      {!d.healthy && <Alert kind="warn">{t('chemicalNote')}</Alert>}
      <Alert kind="info">{t('expertNote')}</Alert>
      <section className="info-sec">
        <h3>{t('sources')}</h3>
        <ul className="sources">
          {d.sources.map((s) => <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.title}</a></li>)}
        </ul>
      </section>
    </div>
  )
}
