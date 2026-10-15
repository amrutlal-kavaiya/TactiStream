import { Link, makeStyles, tokens } from '@fluentui/react-components'
import { Open16Regular } from '@fluentui/react-icons'

import type { DemoMedia } from '../api/config'
import { useT } from '../i18n/useT'

const useStyles = makeStyles({
  root: { display: 'grid', gap: tokens.spacingVerticalM },
  video: {
    display: 'block',
    width: '100%',
    aspectRatio: '16 / 9',
    backgroundColor: tokens.colorNeutralBackgroundInverted,
    borderRadius: tokens.borderRadiusMedium,
  },
  external: { display: 'inline-flex', alignItems: 'center', gap: tokens.spacingHorizontalXS },
})

export interface DemoVideoPlayerProps {
  media: DemoMedia
}

/** File media plays inline with captions; link media (YouTube) opens in a new tab. */
export function DemoVideoPlayer({ media }: DemoVideoPlayerProps) {
  const t = useT()
  const styles = useStyles()
  const { main, backup, captions_url } = media
  return (
    <div className={styles.root}>
      {main.kind === 'file' ? (
        <video className={styles.video} src={main.url} controls preload="metadata" data-testid="demo-video">
          {captions_url && (
            <track kind="captions" src={captions_url} srcLang="en" label={t('captionsEnglish')} default />
          )}
        </video>
      ) : (
        <Link href={main.url} target="_blank" rel="noopener noreferrer" className={styles.external}>
          {t('openExternalVideo')}
          <Open16Regular aria-hidden />
        </Link>
      )}
      {backup && (
        <Link
          href={backup.url}
          target={backup.kind === 'link' ? '_blank' : undefined}
          rel="noopener noreferrer"
        >
          {t('backupRecording')}
        </Link>
      )}
    </div>
  )
}
