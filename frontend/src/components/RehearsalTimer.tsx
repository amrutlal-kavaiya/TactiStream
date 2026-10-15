import {
  Button,
  makeStyles,
  mergeClasses,
  ProgressBar,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
  tokens,
} from '@fluentui/react-components'
import { ArrowReset20Regular, Pause20Regular, Play20Regular } from '@fluentui/react-icons'
import { useEffect, useState } from 'react'

import { useT } from '../i18n/useT'
import { BEATS, beatIndexAt, formatDuration, REHEARSAL_S } from '../presenter/beats'

const TICK_MS = 250

const useStyles = makeStyles({
  root: { display: 'grid', gap: tokens.spacingVerticalM },
  controls: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: tokens.spacingHorizontalS },
  clock: {
    fontFamily: tokens.fontFamilyMonospace,
    fontVariantNumeric: 'tabular-nums',
    color: tokens.colorNeutralForeground1,
  },
  total: { color: tokens.colorNeutralForeground2 },
  over: { color: tokens.colorPaletteRedForeground1, fontWeight: tokens.fontWeightSemibold },
  time: { fontFamily: tokens.fontFamilyMonospace, whiteSpace: 'nowrap', width: '110px' },
  current: {
    backgroundColor: tokens.colorBrandBackground2,
    boxShadow: `inset 4px 0 0 ${tokens.colorBrandStroke1}`,
  },
})

/** Wall-clock based, so a throttled background tab still shows the true elapsed time. */
export function RehearsalTimer() {
  const t = useT()
  const styles = useStyles()
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [bankedMs, setBankedMs] = useState(0)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (startedAt === null) return
    const id = setInterval(() => {
      setNow(Date.now())
    }, TICK_MS)
    return () => {
      clearInterval(id)
    }
  }, [startedAt])

  const elapsedMs = bankedMs + (startedAt === null ? 0 : now - startedAt)
  const elapsedS = elapsedMs / 1000
  const current = beatIndexAt(elapsedS)

  function start() {
    const at = Date.now()
    setNow(at)
    setStartedAt(at)
  }

  function pause() {
    if (startedAt !== null) setBankedMs(bankedMs + Date.now() - startedAt)
    setStartedAt(null)
  }

  function reset() {
    setStartedAt(null)
    setBankedMs(0)
  }

  return (
    <div className={styles.root}>
      <div className={styles.controls} role="group" aria-label={t('rehearsalTimer')}>
        {startedAt === null ? (
          <Button appearance="primary" icon={<Play20Regular />} onClick={start}>
            {t('timerStart')}
          </Button>
        ) : (
          <Button icon={<Pause20Regular />} onClick={pause}>
            {t('timerPause')}
          </Button>
        )}
        <Button icon={<ArrowReset20Regular />} onClick={reset}>
          {t('timerReset')}
        </Button>
        <Text size={600} className={styles.clock}>
          <time>{formatDuration(elapsedS)}</time>
        </Text>
        <Text className={styles.total}>/ {formatDuration(REHEARSAL_S)}</Text>
        {elapsedS > REHEARSAL_S && (
          <Text className={styles.over} role="status">
            {t('timerOver')}
          </Text>
        )}
      </div>
      <ProgressBar
        value={Math.min(elapsedS / REHEARSAL_S, 1)}
        color={elapsedS > REHEARSAL_S ? 'error' : 'brand'}
        aria-label={t('rehearsalTimer')}
      />
      <Table size="small" aria-label={t('demoBeats')}>
        <TableHeader>
          <TableRow>
            <TableHeaderCell className={styles.time}>{t('colBeatTime')}</TableHeaderCell>
            <TableHeaderCell>{t('colBeatAction')}</TableHeaderCell>
            <TableHeaderCell>{t('colBeatIntent')}</TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {BEATS.map((beat, index) => (
            <TableRow
              key={beat.time}
              aria-current={index === current ? 'step' : undefined}
              className={mergeClasses(index === current && styles.current)}
            >
              <TableCell className={styles.time}>{beat.time}</TableCell>
              <TableCell>{beat.action}</TableCell>
              <TableCell>{beat.intent}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
