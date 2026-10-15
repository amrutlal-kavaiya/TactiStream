import {
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  DialogTrigger,
  makeStyles,
} from '@fluentui/react-components'
import { Video20Regular } from '@fluentui/react-icons'

import { useDemoMedia } from '../api/config'
import { useT } from '../i18n/useT'
import { DemoVideoPlayer } from './DemoVideoPlayer'

const useStyles = makeStyles({
  surface: { maxWidth: 'min(960px, calc(100vw - 32px))', width: '100%' },
})

/** Header entry point for judges; renders nothing until the presenter publishes. */
export function WatchDemoButton() {
  const t = useT()
  const styles = useStyles()
  const { media } = useDemoMedia()
  if (!media) return null
  return (
    <Dialog>
      <DialogTrigger disableButtonEnhancement>
        <Button appearance="primary" icon={<Video20Regular />}>
          {t('watchDemo')}
        </Button>
      </DialogTrigger>
      <DialogSurface className={styles.surface}>
        <DialogBody>
          <DialogTitle>{t('demoVideo')}</DialogTitle>
          <DialogContent>
            <DemoVideoPlayer media={media} />
          </DialogContent>
          <DialogActions>
            <DialogTrigger disableButtonEnhancement>
              <Button appearance="secondary">{t('close')}</Button>
            </DialogTrigger>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  )
}
