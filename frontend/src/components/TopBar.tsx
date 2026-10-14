import type { Language, ViewerMode } from '../contracts/generated'
import { formatClock, useT } from '../i18n/useT'
import { useMatchStore } from '../store/matchStore'
import { SourceBadge } from './SourceBadge'

const LANGUAGE_NAMES: Record<Language, string> = { en: 'English', hi: 'हिन्दी' }

export function TopBar() {
  const t = useT()
  const sessionClockMs = useMatchStore((s) => s.sessionClockMs)
  const sourceKind = useMatchStore((s) => s.metadata?.source.kind)
  const prefs = useMatchStore((s) => s.prefs)
  const setPrefs = useMatchStore((s) => s.setPrefs)

  return (
    <header className="top-bar">
      <h1>{t('appTitle')}</h1>
      {sourceKind && <SourceBadge kind={sourceKind} />}
      <span>
        <span className="muted">{t('sessionClock')}</span>{' '}
        <time className="clock" data-testid="session-clock">
          {formatClock(sessionClockMs)}
        </time>
      </span>
      <label>
        {t('mode')}
        <select
          value={prefs.mode}
          onChange={(e) => {
            setPrefs({ ...prefs, mode: e.target.value as ViewerMode })
          }}
        >
          <option value="fan">{t('modeFan')}</option>
          <option value="analyst">{t('modeAnalyst')}</option>
        </select>
      </label>
      <label>
        {t('language')}
        <select
          value={prefs.language}
          onChange={(e) => {
            setPrefs({ ...prefs, language: e.target.value as Language })
          }}
        >
          {Object.entries(LANGUAGE_NAMES).map(([code, name]) => (
            <option key={code} value={code} lang={code}>
              {name}
            </option>
          ))}
        </select>
      </label>
    </header>
  )
}
