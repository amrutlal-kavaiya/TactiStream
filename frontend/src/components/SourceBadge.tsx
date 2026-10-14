import type { SourceKind } from '../contracts/generated'
import { useT } from '../i18n/useT'

/** Persistent provenance badge; the MVP only ever emits synthetic data. */
export function SourceBadge({ kind }: { kind: SourceKind }) {
  const t = useT()
  return (
    <span className="badge" data-testid="source-badge" title={t('dataSource')}>
      {kind === 'synthetic' ? t('synthetic') : kind}
    </span>
  )
}
