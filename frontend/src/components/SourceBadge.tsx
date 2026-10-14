import { Badge } from '@fluentui/react-components'
import { DataUsage16Regular } from '@fluentui/react-icons'

import type { SourceKind } from '../contracts/generated'
import { useT } from '../i18n/useT'

/** Persistent provenance badge; the MVP only ever emits synthetic data. */
export function SourceBadge({ kind, testId }: { kind: SourceKind; testId?: string }) {
  const t = useT()
  return (
    <Badge
      appearance="filled"
      color="informative"
      shape="rounded"
      size="medium"
      icon={<DataUsage16Regular />}
      data-testid={testId}
      title={t('dataSource')}
    >
      {kind === 'synthetic' ? t('synthetic') : kind}
    </Badge>
  )
}
