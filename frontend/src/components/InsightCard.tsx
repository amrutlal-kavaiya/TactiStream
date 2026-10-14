import { useEffect, useEffectEvent, useId } from 'react'

import type { InsightPacket } from '../contracts/generated'
import { useT } from '../i18n/useT'

export interface InsightCardProps {
  packet: InsightPacket
  onOpenEvidence: (evidenceId: string) => void
  onDisplayed?: (packet: InsightPacket) => void
}

export function InsightCard({ packet, onOpenEvidence, onDisplayed }: InsightCardProps) {
  const t = useT()
  const titleId = useId()
  const reportDisplayed = useEffectEvent(() => onDisplayed?.(packet))

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      reportDisplayed()
    })
    return () => {
      cancelAnimationFrame(frame)
    }
  }, [packet.insight_id, packet.insight_version])

  return (
    <article
      className="insight-card"
      aria-labelledby={titleId}
      lang={packet.language}
      data-testid="insight-card"
    >
      <div className="insight-card__labels">
        {packet.labels?.includes('synthetic') && (
          <span className="label label--synthetic">{t('synthetic')}</span>
        )}
        {packet.claim_status === 'verified_fact' && (
          <span className="label label--verified">{t('verifiedFact')}</span>
        )}
      </div>
      <h2 id={titleId} className="insight-card__title">
        {packet.title}
      </h2>
      <p className="insight-card__body">{packet.body}</p>
      <div className="chips" role="group" aria-label={t('evidence')}>
        {packet.evidence_ids.map((id) => (
          <button
            key={id}
            type="button"
            className="chip"
            onClick={() => {
              onOpenEvidence(id)
            }}
          >
            {id}
          </button>
        ))}
      </div>
    </article>
  )
}
