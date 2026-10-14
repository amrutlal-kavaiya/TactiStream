import { Body1, Caption1, Card, makeStyles, tokens } from '@fluentui/react-components'

import { useT } from '../i18n/useT'

const useStyles = makeStyles({
  card: { boxShadow: tokens.shadow4 },
  pitch: {
    position: 'relative',
    aspectRatio: '105 / 68',
    maxHeight: '60vh',
    backgroundColor: 'var(--ts-pitch-grass)',
    border: '2px solid var(--ts-pitch-line)',
    borderRadius: tokens.borderRadiusMedium,
    overflow: 'hidden',
    '::before': {
      content: '""',
      position: 'absolute',
      insetBlock: 0,
      left: '50%',
      borderLeft: '2px solid var(--ts-pitch-line)',
    },
    '::after': {
      content: '""',
      position: 'absolute',
      top: '50%',
      left: '50%',
      width: '17.4%',
      aspectRatio: '1',
      transform: 'translate(-50%, -50%)',
      border: '2px solid var(--ts-pitch-line)',
      borderRadius: '50%',
    },
  },
  text: { display: 'grid', gap: tokens.spacingVerticalXS },
  hint: { color: tokens.colorNeutralForeground2 },
})

export function PitchPlaceholder({ hint }: { hint: string }) {
  const t = useT()
  const styles = useStyles()
  return (
    <Card className={styles.card}>
      <div className={styles.pitch} aria-hidden />
      <div className={styles.text}>
        <Body1>{t('pitchPlaceholder')}</Body1>
        <Caption1 className={styles.hint}>{hint}</Caption1>
      </div>
    </Card>
  )
}
