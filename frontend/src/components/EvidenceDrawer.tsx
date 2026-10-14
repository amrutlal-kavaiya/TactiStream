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

/** Resolves one evidence id through REST. Remount (key) per id; focus returns to the opener on unmount. */
export function EvidenceDrawer({ evidenceId, load, onClose }: EvidenceDrawerProps) {
  const t = useT()
  const headingId = useId()
  const closeRef = useRef<HTMLButtonElement>(null)
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  // Captured on first render: StrictMode re-runs effects after focus has already moved into the drawer.
  const [opener] = useState(() =>
    document.activeElement instanceof HTMLElement ? document.activeElement : null,
  )
  const loadEvidence = useEffectEvent((id: string) => load(id))
  const close = useEffectEvent(() => {
    onClose()
  })

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

  useEffect(() => {
    closeRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        close()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      opener?.focus()
    }
  }, [opener])

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <section
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        onClick={(event) => {
          event.stopPropagation()
        }}
      >
        <header className="drawer__header">
          <h2 id={headingId}>
            {t('evidence')} {evidenceId}
          </h2>
          <button ref={closeRef} type="button" className="button" onClick={onClose}>
            {t('close')}
          </button>
        </header>
        {state.status === 'loading' && <p role="status">{t('loadingEvidence')}</p>}
        {state.status === 'unavailable' && <p role="alert">{t('evidenceUnavailable')}</p>}
        {state.status === 'ready' && (
          <>
            <dl className="fields">
              {fieldsOf(state.evidence, t).map(([term, value]) => (
                <div key={term} className="fields__row">
                  <dt>{term}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <details>
              <summary>{t('rawRecord')}</summary>
              <pre>{JSON.stringify(state.evidence.record, null, 2)}</pre>
            </details>
          </>
        )}
      </section>
    </div>
  )
}
