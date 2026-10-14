import {
  Caption1,
  makeStyles,
  Subtitle2,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  tokens,
} from '@fluentui/react-components'
import { useId, useLayoutEffect, useRef } from 'react'

import { formatClock, useT } from '../i18n/useT'
import { useMatchStore } from '../store/matchStore'

/** Pixels from the bottom that still count as "following" the newest event. */
const FOLLOW_SLACK_PX = 8

const useStyles = makeStyles({
  section: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS, minHeight: 0 },
  heading: { margin: 0 },
  scroller: { maxHeight: '320px', overflowY: 'auto' },
  mono: { fontFamily: tokens.fontFamilyMonospace, fontVariantNumeric: 'tabular-nums' },
  player: { display: 'inline-flex', alignItems: 'center', gap: tokens.spacingHorizontalXS },
  swatch: {
    flexShrink: 0,
    width: '8px',
    height: '8px',
    borderRadius: tokens.borderRadiusCircular,
  },
  muted: { color: tokens.colorNeutralForeground2 },
})

export function EventList() {
  const t = useT()
  const styles = useStyles()
  const headingId = useId()
  const events = useMatchStore((s) => s.events)
  const scrollerRef = useRef<HTMLDivElement>(null)
  const followRef = useRef(true)

  useLayoutEffect(() => {
    const scroller = scrollerRef.current
    if (scroller && followRef.current) scroller.scrollTop = scroller.scrollHeight
  }, [events.length])

  return (
    <section className={styles.section}>
      <Subtitle2 as="h2" id={headingId} className={styles.heading}>
        {t('events')}
      </Subtitle2>
      {events.length === 0 ? (
        <Caption1 className={styles.muted}>{t('noEvents')}</Caption1>
      ) : (
        <div
          ref={scrollerRef}
          className={styles.scroller}
          onScroll={(e) => {
            const el = e.currentTarget
            followRef.current = el.scrollHeight - el.scrollTop - el.clientHeight <= FOLLOW_SLACK_PX
          }}
        >
          <Table size="extra-small" aria-labelledby={headingId}>
            <TableHeader>
              <TableRow>
                <TableHeaderCell>{t('colTime')}</TableHeaderCell>
                <TableHeaderCell>{t('fieldType')}</TableHeaderCell>
                <TableHeaderCell>{t('fieldPlayer')}</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((e) => (
                <TableRow key={e.event_id}>
                  <TableCell className={styles.mono}>{formatClock(e.session_clock_ms)}</TableCell>
                  <TableCell>{e.event_type}</TableCell>
                  <TableCell className={styles.mono}>
                    <span className={styles.player}>
                      <span
                        className={styles.swatch}
                        style={{ backgroundColor: `var(--ts-team-${e.team_id})` }}
                        aria-hidden
                      />
                      {e.player_id}
                      {e.recipient_id ? ` → ${e.recipient_id}` : ''}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  )
}
