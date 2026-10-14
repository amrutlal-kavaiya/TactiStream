import { makeStyles, mergeClasses, Text, ToggleButton, tokens, Tooltip } from '@fluentui/react-components'
import { DataTrending24Regular, WeatherMoon20Regular, WeatherSunny20Regular } from '@fluentui/react-icons'

import type { MessageKey } from '../i18n/en'
import { useT } from '../i18n/useT'
import { useMatchStore } from '../store/matchStore'
import type { ThemeName } from '../theme/brand'
import { SourceBadge } from './SourceBadge'

export type ConnectionStatus = 'live' | 'paused' | 'offline'

const STATUS_LABEL: Record<ConnectionStatus, MessageKey> = {
  live: 'statusLive',
  paused: 'statusPaused',
  offline: 'statusOffline',
}

const useStyles = makeStyles({
  bar: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    columnGap: tokens.spacingHorizontalL,
    rowGap: tokens.spacingVerticalS,
    padding: `${tokens.spacingVerticalM} ${tokens.spacingHorizontalXXL}`,
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    color: tokens.colorBrandForeground1,
  },
  title: { margin: 0, color: tokens.colorNeutralForeground1 },
  matchTitle: { color: tokens.colorNeutralForeground2 },
  status: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalXS,
    color: tokens.colorNeutralForeground2,
  },
  dot: {
    width: '10px',
    height: '10px',
    borderRadius: tokens.borderRadiusCircular,
    border: `${tokens.strokeWidthThin} solid ${tokens.colorNeutralStrokeAccessible}`,
  },
  live: { backgroundColor: tokens.colorPaletteGreenBackground3 },
  paused: { backgroundColor: tokens.colorPaletteMarigoldBackground3 },
  offline: { backgroundColor: tokens.colorNeutralBackground5 },
  spacer: { flexGrow: 1 },
})

export interface TopBarProps {
  status: ConnectionStatus
  themeName: ThemeName
  onToggleTheme: () => void
}

export function TopBar({ status, themeName, onToggleTheme }: TopBarProps) {
  const t = useT()
  const styles = useStyles()
  const sourceKind = useMatchStore((s) => s.metadata?.source.kind)
  const teams = useMatchStore((s) => s.metadata?.teams)
  const language = useMatchStore((s) => s.prefs.language)
  const matchTitle = teams?.map((team) => team.display_name[language]).join(` ${t('versus')} `)

  return (
    <div className={styles.bar}>
      <div className={styles.brand}>
        <DataTrending24Regular aria-hidden />
        <Text as="h1" size={500} weight="semibold" className={styles.title}>
          {t('appTitle')}
        </Text>
      </div>
      {matchTitle && (
        <Text size={400} className={styles.matchTitle} data-testid="match-title">
          {matchTitle}
        </Text>
      )}
      <SourceBadge kind={sourceKind ?? 'synthetic'} testId="source-badge" />
      <span className={styles.status} role="status" title={t('connection')} data-testid="connection-status">
        <span className={mergeClasses(styles.dot, styles[status])} aria-hidden />
        <Text>{t(STATUS_LABEL[status])}</Text>
      </span>
      <span className={styles.spacer} />
      <Tooltip content={t('lightTheme')} relationship="label">
        <ToggleButton
          appearance="subtle"
          checked={themeName === 'light'}
          icon={themeName === 'light' ? <WeatherSunny20Regular /> : <WeatherMoon20Regular />}
          onClick={onToggleTheme}
        />
      </Tooltip>
    </div>
  )
}
