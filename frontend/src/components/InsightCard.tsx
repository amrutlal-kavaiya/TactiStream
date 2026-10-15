import { Badge, Body1, Button, Card, CardHeader, makeStyles, Text, tokens } from '@fluentui/react-components'
import { CheckmarkCircle16Regular, DocumentSearch16Regular } from '@fluentui/react-icons'
import { useEffect, useEffectEvent, useId } from 'react'

import type { InsightPacket } from '../contracts/generated'
import { useT } from '../i18n/useT'
import { SourceBadge } from './SourceBadge'

export interface InsightCardProps {
  packet: InsightPacket
  onOpenEvidence: (evidenceId: string) => void
  onDisplayed?: (packet: InsightPacket) => void
}

const useStyles = makeStyles({
  card: {
    borderLeft: `${tokens.strokeWidthThickest} solid ${tokens.colorBrandStroke1}`,
    boxShadow: tokens.shadow8,
    rowGap: tokens.spacingVerticalM,
  },
  labels: { display: 'flex', flexWrap: 'wrap', gap: tokens.spacingHorizontalS },
  title: { margin: 0 },
  body: { margin: 0 },
  chips: { display: 'flex', flexWrap: 'wrap', gap: tokens.spacingHorizontalS },
  chip: { fontFamily: tokens.fontFamilyMonospace },
})

export function InsightCard({ packet, onOpenEvidence, onDisplayed }: InsightCardProps) {
  const t = useT()
  const styles = useStyles()
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
    <Card
      className={styles.card}
      role="article"
      aria-labelledby={titleId}
      lang={packet.language}
      data-testid="insight-card"
    >
      <CardHeader
        header={
          <Text as="h2" id={titleId} size={400} weight="semibold" className={styles.title}>
            {packet.title}
          </Text>
        }
        description={
          <div className={styles.labels}>
            {packet.labels?.includes('synthetic') && <SourceBadge kind="synthetic" />}
            {packet.claim_status === 'verified_fact' && (
              <Badge appearance="tint" color="success" shape="rounded" icon={<CheckmarkCircle16Regular />}>
                {t('verifiedFact')}
              </Badge>
            )}
          </div>
        }
      />
      <Body1 as="p" className={styles.body}>
        {packet.body}
      </Body1>
      <div className={styles.chips} role="group" aria-label={t('evidence')}>
        {packet.evidence_ids.map((id) => (
          <Button
            key={id}
            size="small"
            appearance="outline"
            shape="circular"
            icon={<DocumentSearch16Regular />}
            className={styles.chip}
            onClick={() => {
              onOpenEvidence(id)
            }}
          >
            {id}
          </Button>
        ))}
      </div>
    </Card>
  )
}
