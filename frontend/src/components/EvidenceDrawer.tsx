import {
  Button,
  DrawerBody,
  DrawerHeader,
  DrawerHeaderTitle,
  makeStyles,
  MessageBar,
  MessageBarBody,
  OverlayDrawer,
  Spinner,
  tokens,
} from '@fluentui/react-components'
import { Dismiss24Regular } from '@fluentui/react-icons'
import { useEffect, useEffectEvent, useId, useRef, useState } from 'react'

import type { EvidenceResponse } from '../api/client'
import { formatClock, type Translate, useT } from '../i18n/useT'

export interface EvidenceDrawerProps {
  evidenceId: string
  load: (evidenceId: string) => Promise<EvidenceResponse>
  onClose: () => void
}

type LoadState =
  { status: 'loading' } | { status: 'ready'; evidence: EvidenceResponse } | { status: 'unavailable' }

const point = (p: [number, number]) => `${p[0].toFixed(1)}, ${p[1].toFixed(1)}`

function fieldsOf(evidence: EvidenceResponse, t: Translate): [string, string][] {
  switch (evidence.kind) {
    case 'event': {
      const r = evidence.record
      return [
        [t('fieldType'), r.event_type],
        [t('fieldPlayer'), r.player_id],
        ...(r.recipient_id ? [[t('fieldRecipient'), r.recipient_id] as [string, string]] : []),
        [t('fieldStart'), point(r.start_m)],
        ...(r.end_m ? [[t('fieldEnd'), point(r.end_m)] as [string, string]] : []),
        ...(r.outcome ? [[t('fieldOutcome'), r.outcome] as [string, string]] : []),
        [t('fieldPeriodClock'), `P${String(r.period)} ${formatClock(r.period_clock_ms, true)}`],
        [t('fieldSessionClock'), formatClock(r.session_clock_ms, true)],
        [t('fieldSource'), r.source.kind],
      ]
    }
    case 'metric': {
      const r = evidence.record
      const value =
        r.value === undefined ? t('valueUnavailable') : `${String(r.value)}${r.unit ? ` ${r.unit}` : ''}`
      return [
        [t('fieldMetric'), r.kind],
        [t('fieldValue'), value],
        [t('fieldWindow'), `${formatClock(r.window.start_ms, true)} – ${formatClock(r.window.end_ms, true)}`],
        [t('fieldInputEvents'), r.inputs.event_ids.join(', ')],
      ]
    }
    case 'frame': {
      const r = evidence.record
      return [
        [t('fieldFrame'), String(r.frame_index)],
        [t('fieldSessionClock'), formatClock(r.session_clock_ms, true)],
        [t('fieldVisiblePlayers'), String(r.players.filter((p) => p.visible).length)],
        [t('fieldSource'), r.source.kind],
      ]
    }
  }
}

const useStyles = makeStyles({
  id: { fontFamily: tokens.fontFamilyMonospace },
  fields: { margin: `0 0 ${tokens.spacingVerticalL}` },
  row: {
    display: 'grid',
    gridTemplateColumns: '9rem 1fr',
    gap: tokens.spacingHorizontalS,
    padding: `${tokens.spacingVerticalXS} 0`,
    borderBottom: `${tokens.strokeWidthThin} solid ${tokens.colorNeutralStroke2}`,
  },
  term: { color: tokens.colorNeutralForeground2 },
  value: {
    margin: 0,
    fontFamily: tokens.fontFamilyMonospace,
    fontVariantNumeric: 'tabular-nums',
    overflowWrap: 'anywhere',
  },
  raw: {
    overflowX: 'auto',
    fontFamily: tokens.fontFamilyMonospace,
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground2,
  },
})

/** Resolves one evidence id through REST. Remount (key) per id; focus returns to the opener on unmount. */
export function EvidenceDrawer({ evidenceId, load, onClose }: EvidenceDrawerProps) {
  const t = useT()
  const styles = useStyles()
  const headingId = useId()
  const closeRef = useRef<HTMLButtonElement>(null)
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  // Captured on first render: StrictMode re-runs effects after focus has already moved into the drawer.
  const [opener] = useState(() =>
    document.activeElement instanceof HTMLElement ? document.activeElement : null,
  )
  const loadEvidence = useEffectEvent((id: string) => load(id))

  useEffect(() => {
    let cancelled = false
    loadEvidence(evidenceId).then(
      (evidence) => {
        if (!cancelled) setState({ status: 'ready', evidence })
      },
      () => {
        if (!cancelled) setState({ status: 'unavailable' })
      },
    )
    return () => {
      cancelled = true
    }
  }, [evidenceId])

  // The opener stays inert until the commit that closes the drawer; this passive cleanup runs after that commit.
  useEffect(() => {
    closeRef.current?.focus()
    return () => {
      opener?.focus()
    }
  }, [opener])

  return (
    <OverlayDrawer
      open
      position="end"
      size="medium"
      aria-labelledby={headingId}
      onOpenChange={(_, data) => {
        if (!data.open) onClose()
      }}
    >
      <DrawerHeader>
        <DrawerHeaderTitle
          heading={{ id: headingId }}
          action={
            <Button
              ref={closeRef}
              appearance="subtle"
              aria-label={t('close')}
              icon={<Dismiss24Regular />}
              onClick={onClose}
            />
          }
        >
          {t('evidence')} <span className={styles.id}>{evidenceId}</span>
        </DrawerHeaderTitle>
      </DrawerHeader>
      <DrawerBody>
        {state.status === 'loading' && (
          <Spinner size="small" labelPosition="after" label={t('loadingEvidence')} />
        )}
        {state.status === 'unavailable' && (
          <MessageBar intent="warning" role="alert">
            <MessageBarBody>{t('evidenceUnavailable')}</MessageBarBody>
          </MessageBar>
        )}
        {state.status === 'ready' && (
          <>
            <dl className={styles.fields}>
              {fieldsOf(state.evidence, t).map(([term, value]) => (
                <div key={term} className={styles.row}>
                  <dt className={styles.term}>{term}</dt>
                  <dd className={styles.value}>{value}</dd>
                </div>
              ))}
            </dl>
            <details>
              <summary>{t('rawRecord')}</summary>
              <pre className={styles.raw}>{JSON.stringify(state.evidence.record, null, 2)}</pre>
            </details>
          </>
        )}
      </DrawerBody>
    </OverlayDrawer>
  )
}
