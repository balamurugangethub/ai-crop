import { Link } from 'react-router-dom'
import { useAuth } from '../App'
import { useI18n } from '../i18n'
import { FieldsArt } from '../components'

export default function Dashboard() {
  const { t } = useI18n()
  const { user } = useAuth()
  const tiles = [
    { to: '/scan', icon: '📷', title: 'scanCrop', hint: 'scanCropHint', primary: true },
    { to: '/reports', icon: '📋', title: 'previousReports', hint: 'previousReportsHint' },
    { to: '/shops', icon: '🏪', title: 'findShops', hint: 'findShopsHint' },
    { to: '/tips', icon: '🌾', title: 'farmingTips', hint: 'farmingTipsHint' },
    { to: '/settings', icon: '🗣️', title: 'languageSettings', hint: 'languageHint' },
  ]
  return (
    <div className="dashboard">
      <section className="hero">
        <FieldsArt />
        <div className="hero-text">
          <p className="hero-greet">{t('welcomeBack')},</p>
          <h1>{user?.name}</h1>
          <p>{t('dashboardIntro')}</p>
        </div>
      </section>
      <div className="tiles">
        {tiles.map((x) => (
          <Link key={x.to} to={x.to} className={`tile ${x.primary ? 'tile-primary' : ''}`}>
            <span className="tile-icon" aria-hidden>{x.icon}</span>
            <span className="tile-title">{t(x.title)}</span>
            <span className="tile-hint">{t(x.hint)}</span>
          </Link>
        ))}
      </div>
      <p className="note">{t('supportedCrops')} {t('notSupportedYet')}</p>
    </div>
  )
}
