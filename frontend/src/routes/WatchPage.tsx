import { makeStyles, MessageBar, MessageBarBody, Spinner, Text } from '@fluentui/react-components'

import { useDemoMedia } from '../api/config'
import { DemoVideoPlayer } from '../components/DemoVideoPlayer'
import { TopBar } from '../components/TopBar'
import { useT } from '../i18n/useT'
import { PageShell } from '../theme/PageShell'
import { useThemePreference } from '../theme/useThemePreference'

const useStyles = makeStyles({
  title: { margin: 0 },
})

/** The one stable link for README, judge guide and submission checklist (FR-030). */
export function WatchPage() {
  const t = useT()
  const styles = useStyles()
  const { themeName, toggleTheme } = useThemePreference()
  const { media, loaded } = useDemoMedia()
  return (
    <PageShell themeName={themeName} header={<TopBar themeName={themeName} onToggleTheme={toggleTheme} />}>
      <Text as="h2" size={600} weight="semibold" className={styles.title}>
        {t('demoVideo')}
      </Text>
      {!loaded ? (
        <Spinner size="small" label={t('watchLoading')} />
      ) : media ? (
        <DemoVideoPlayer media={media} />
      ) : (
        <MessageBar intent="info">
          <MessageBarBody>{t('watchNotPublished')}</MessageBarBody>
        </MessageBar>
      )}
    </PageShell>
  )
}
