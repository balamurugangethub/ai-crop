import { TIPS, useI18n } from '../i18n'
import { Alert, SpeakButton } from '../components'

export default function TipsPage() {
  const { t, lang } = useI18n()
  const tips = TIPS[lang] || TIPS.en
  return (
    <div className="page">
      <h1>{t('farmingTips')}</h1>
      <p>{t('tipsIntro')}</p>
      <SpeakButton text={tips.map((x) => x.text).join('. ')} />
      <ol className="tips">
        {tips.map((x, i) => (
          <li key={i} className="card tip"><span className="tip-n">{i + 1}</span><div><p>{x.text}</p><small className="muted">{x.src}</small></div></li>
        ))}
      </ol>
      <Alert kind="info">{t('expertNote')}</Alert>
    </div>
  )
}
