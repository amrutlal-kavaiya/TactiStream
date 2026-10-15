import {
  Button,
  Card,
  CardHeader,
  Checkbox,
  Field,
  Input,
  Link,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Spinner,
  Switch,
  Text,
  tokens,
} from '@fluentui/react-components'
import { LockOpen20Regular, Open20Regular } from '@fluentui/react-icons'
import { type SubmitEvent, useCallback, useEffect, useState } from 'react'

import { ApiError } from '../api/client'
import { MediaSlotCard } from '../components/MediaSlotCard'
import { RehearsalTimer } from '../components/RehearsalTimer'
import { TopBar } from '../components/TopBar'
import type { MessageKey } from '../i18n/en'
import { useT } from '../i18n/useT'
import {
  getPresenterState,
  MEDIA_SLOTS,
  type MediaRecord,
  type MediaSlot,
  PRESENTER_KEY_STORAGE,
  type PresenterState,
  setPublished,
} from '../presenter/api'
import { CHECKLIST, CHECKLIST_STORAGE_KEY } from '../presenter/beats'
import { PageShell } from '../theme/PageShell'
import { useThemePreference } from '../theme/useThemePreference'

const SLOT_TITLE: Record<MediaSlot, MessageKey> = {
  main: 'slotMain',
  backup: 'backupRecording',
  captions: 'slotCaptions',
}

const LIVE_APP_URL = '/demo?seed=42'

type Access =
  | { kind: 'loading' }
  | { kind: 'disabled' }
  | { kind: 'locked'; refused: boolean }
  | { kind: 'error' }
  | { kind: 'ready'; key: string; state: PresenterState }

const useStyles = makeStyles({
  title: { margin: 0 },
  card: { display: 'grid', gap: tokens.spacingVerticalM },
  keyForm: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'end',
    gap: tokens.spacingHorizontalS,
    maxWidth: '520px',
  },
  grow: { flexGrow: 1 },
  checklist: { display: 'grid', gap: tokens.spacingVerticalXS },
  slots: {
    display: 'grid',
    gap: tokens.spacingHorizontalL,
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
  },
  hint: { color: tokens.colorNeutralForeground2 },
})

function readStoredKey(): string {
  try {
    return sessionStorage.getItem(PRESENTER_KEY_STORAGE) ?? ''
  } catch {
    return ''
  }
}

function storeKey(key: string | null) {
  try {
    if (key) sessionStorage.setItem(PRESENTER_KEY_STORAGE, key)
    else sessionStorage.removeItem(PRESENTER_KEY_STORAGE)
  } catch {
    // Without sessionStorage the key lives in memory for this page view only.
  }
}

/** An empty key still asks the server, which is how a disabled server (404) is told apart from a locked one (401). */
async function resolveAccess(key: string): Promise<Access> {
  try {
    const state = await getPresenterState(key)
    storeKey(key)
    return { kind: 'ready', key, state }
  } catch (error) {
    if (error instanceof ApiError && error.code === 'presenter_disabled') return { kind: 'disabled' }
    if (error instanceof ApiError && error.code === 'presenter_key_invalid') {
      storeKey(null)
      return { kind: 'locked', refused: key !== '' }
    }
    return { kind: 'error' }
  }
}

function readChecklist(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(CHECKLIST_STORAGE_KEY) ?? '[]')
    return Array.isArray(value) ? value.filter((id): id is string => typeof id === 'string') : []
  } catch {
    return []
  }
}

function StepHeading({ text }: { text: MessageKey }) {
  const t = useT()
  return (
    <Text as="h3" size={500} weight="semibold">
      {t(text)}
    </Text>
  )
}

function RecordChecklist() {
  const t = useT()
  const styles = useStyles()
  const [ticked, setTicked] = useState(readChecklist)

  function toggle(id: string, checked: boolean) {
    const next = CHECKLIST.map((item) => item.id).filter((itemId) =>
      itemId === id ? checked : ticked.includes(itemId),
    )
    setTicked(next)
    try {
      localStorage.setItem(CHECKLIST_STORAGE_KEY, JSON.stringify(next))
    } catch {
      // Ticks still apply for this visit.
    }
  }

  return (
    <div className={styles.checklist}>
      {CHECKLIST.map((item) => (
        <Checkbox
          key={item.id}
          label={t(item.label)}
          checked={ticked.includes(item.id)}
          onChange={(_, data) => {
            toggle(item.id, data.checked === true)
          }}
        />
      ))}
    </div>
  )
}

function KeyForm({ refused, onSubmit }: { refused: boolean; onSubmit: (key: string) => Promise<void> }) {
  const t = useT()
  const styles = useStyles()
  const [key, setKey] = useState('')
  const [checking, setChecking] = useState(false)

  function submit(event: SubmitEvent) {
    event.preventDefault()
    if (!key || checking) return
    setChecking(true)
    void onSubmit(key).finally(() => {
      setChecking(false)
    })
  }

  return (
    <Card className={styles.card}>
      <form className={styles.keyForm} onSubmit={submit}>
        <Field
          label={t('presenterKey')}
          hint={t('presenterKeyHint')}
          className={styles.grow}
          validationState={refused ? 'error' : 'none'}
          validationMessage={refused ? t('presenterKeyRefused') : undefined}
        >
          <Input
            type="password"
            autoComplete="current-password"
            value={key}
            onChange={(_, data) => {
              setKey(data.value)
            }}
          />
        </Field>
        <Button type="submit" appearance="primary" icon={<LockOpen20Regular />} disabled={!key || checking}>
          {t('unlock')}
        </Button>
      </form>
    </Card>
  )
}

/** Key-protected (FR-025, FR-026); intentionally not linked from the judge UI. */
export function PresenterPage() {
  const t = useT()
  const styles = useStyles()
  const { themeName, toggleTheme } = useThemePreference()
  const [access, setAccess] = useState<Access>({ kind: 'loading' })
  const [publishError, setPublishError] = useState<MessageKey | null>(null)
  const [publishing, setPublishing] = useState(false)

  useEffect(() => {
    let active = true
    void resolveAccess(readStoredKey()).then((next) => {
      if (active) setAccess(next)
    })
    return () => {
      active = false
    }
  }, [])

  async function unlock(key: string) {
    setAccess(await resolveAccess(key))
  }

  const lock = useCallback(() => {
    storeKey(null)
    setAccess({ kind: 'locked', refused: true })
  }, [])

  function updateSlot(slot: MediaSlot, record: MediaRecord | undefined) {
    setAccess((current) =>
      current.kind === 'ready'
        ? { ...current, state: { ...current.state, slots: { ...current.state.slots, [slot]: record } } }
        : current,
    )
  }

  async function publish(key: string, published: boolean) {
    setPublishError(null)
    setPublishing(true)
    try {
      const state = await setPublished(published, key)
      setAccess({ kind: 'ready', key, state })
    } catch (error) {
      if (error instanceof ApiError && error.code === 'presenter_key_invalid') lock()
      else
        setPublishError(
          error instanceof ApiError && error.code === 'main_missing' ? 'publishNeedsMain' : 'errorPresenter',
        )
    } finally {
      setPublishing(false)
    }
  }

  return (
    <PageShell themeName={themeName} header={<TopBar themeName={themeName} onToggleTheme={toggleTheme} />}>
      <Text as="h2" size={600} weight="semibold" className={styles.title}>
        {t('presenterTitle')}
      </Text>

      {access.kind === 'loading' && <Spinner size="small" />}
      {access.kind === 'disabled' && (
        <MessageBar intent="info">
          <MessageBarBody>{t('presenterDisabled')}</MessageBarBody>
        </MessageBar>
      )}
      {access.kind === 'error' && (
        <MessageBar intent="error" role="alert">
          <MessageBarBody>{t('errorPresenter')}</MessageBarBody>
        </MessageBar>
      )}
      {access.kind === 'locked' && <KeyForm refused={access.refused} onSubmit={unlock} />}

      {access.kind === 'ready' && (
        <>
          <Card className={styles.card}>
            <CardHeader
              header={<StepHeading text="stepRehearse" />}
              action={
                <Button as="a" href={LIVE_APP_URL} target="_blank" rel="noopener" icon={<Open20Regular />}>
                  {t('openLiveApp')}
                </Button>
              }
            />
            <RehearsalTimer />
          </Card>

          <Card className={styles.card}>
            <CardHeader header={<StepHeading text="stepRecord" />} />
            <RecordChecklist />
          </Card>

          <Card className={styles.card}>
            <CardHeader header={<StepHeading text="stepMedia" />} />
            <div className={styles.slots}>
              {MEDIA_SLOTS.map((slot) => (
                <MediaSlotCard
                  key={slot}
                  slot={slot}
                  title={SLOT_TITLE[slot]}
                  record={access.state.slots[slot]}
                  presenterKey={access.key}
                  onChange={updateSlot}
                  onUnauthorized={lock}
                />
              ))}
            </div>
          </Card>

          <Card className={styles.card}>
            <CardHeader header={<StepHeading text="stepPublish" />} />
            <Switch
              label={t('publishSwitch')}
              checked={access.state.published && Boolean(access.state.slots.main)}
              disabled={publishing || !access.state.slots.main}
              onChange={(_, data) => void publish(access.key, data.checked)}
            />
            <Text className={styles.hint}>
              {access.state.slots.main ? t('publishHint') : t('publishNeedsMain')}
            </Text>
            {publishError && (
              <MessageBar intent="error" role="alert">
                <MessageBarBody>{t(publishError)}</MessageBarBody>
              </MessageBar>
            )}
            <Link href="/watch" target="_blank" rel="noopener">
              {t('openWatchPage')}
            </Link>
          </Card>
        </>
      )}
    </PageShell>
  )
}
