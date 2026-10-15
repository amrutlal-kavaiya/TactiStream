import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Input,
  Link,
  makeStyles,
  MessageBar,
  MessageBarBody,
  ProgressBar,
  Text,
  tokens,
  useId,
} from '@fluentui/react-components'
import { ArrowUpload20Regular, Delete20Regular, Dismiss20Regular, Link20Regular } from '@fluentui/react-icons'
import { type SubmitEvent, useEffect, useRef, useState } from 'react'

import { ApiError } from '../api/client'
import type { MessageKey } from '../i18n/en'
import { useT } from '../i18n/useT'
import { clearMedia, linkMedia, type MediaRecord, type MediaSlot, uploadMedia } from '../presenter/api'
import {
  formatDuration,
  readVideoMeta,
  type SpecIssue,
  type VideoMeta,
  videoSpecIssues,
} from '../presenter/beats'

const SPEC_LABEL: Record<SpecIssue, MessageKey> = {
  duration: 'specDuration',
  resolution: 'specResolution',
}

const useStyles = makeStyles({
  card: { display: 'grid', gap: tokens.spacingVerticalM, alignContent: 'start' },
  facts: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: tokens.spacingHorizontalS },
  filename: { wordBreak: 'break-all' },
  muted: { color: tokens.colorNeutralForeground2 },
  row: { display: 'flex', flexWrap: 'wrap', alignItems: 'end', gap: tokens.spacingHorizontalS },
  grow: { flexGrow: 1, minWidth: '180px' },
  file: { color: tokens.colorNeutralForeground1, maxWidth: '100%' },
})

function errorKey(error: unknown): MessageKey {
  if (!(error instanceof ApiError)) return 'errorPresenter'
  switch (error.code) {
    case 'presenter_key_invalid':
      return 'presenterKeyRefused'
    case 'media_too_large':
      return 'errorMediaTooLarge'
    case 'unsupported_media':
      return 'errorUnsupportedMedia'
    case 'invalid_url':
      return 'errorInvalidUrl'
    default:
      return 'errorPresenter'
  }
}

const formatBytes = (bytes: number) =>
  bytes < 1024 * 1024 ? `${String(Math.ceil(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`

function recordMeta(record: MediaRecord): VideoMeta | null {
  const { duration_s, width, height } = record
  return duration_s != null && width != null && height != null ? { duration_s, width, height } : null
}

function SpecBadges({ meta }: { meta: VideoMeta | null }) {
  const t = useT()
  if (!meta) {
    return (
      <Badge appearance="tint" color="warning">
        {t('specUnknown')}
      </Badge>
    )
  }
  const issues = videoSpecIssues(meta)
  if (issues.length === 0) {
    return (
      <Badge appearance="tint" color="success">
        {t('meetsSpec')}
      </Badge>
    )
  }
  return issues.map((issue) => (
    <Badge key={issue} appearance="tint" color="warning">
      {t(SPEC_LABEL[issue])}
    </Badge>
  ))
}

function VideoFacts({ meta }: { meta: VideoMeta | null }) {
  return (
    <>
      {meta && <Text>{formatDuration(meta.duration_s)}</Text>}
      {meta && <Text>{`${String(meta.width)}×${String(meta.height)}`}</Text>}
      <SpecBadges meta={meta} />
    </>
  )
}

export interface MediaSlotCardProps {
  slot: MediaSlot
  title: MessageKey
  record: MediaRecord | undefined
  presenterKey: string
  onChange: (slot: MediaSlot, record: MediaRecord | undefined) => void
  onUnauthorized: () => void
}

/** One media slot: pick a file (metadata shown before upload), or save an https link, or clear. */
export function MediaSlotCard({
  slot,
  title,
  record,
  presenterKey,
  onChange,
  onUnauthorized,
}: MediaSlotCardProps) {
  const t = useT()
  const styles = useStyles()
  const headingId = useId('slot-title')
  const isVideo = slot !== 'captions'
  const [pending, setPending] = useState<{ file: File; meta: VideoMeta | null } | null>(null)
  const [progress, setProgress] = useState<number | null>(null)
  const [link, setLink] = useState('')
  const [error, setError] = useState<MessageKey | null>(null)
  const busy = progress !== null
  const uploadRef = useRef<AbortController | null>(null)

  useEffect(
    () => () => {
      uploadRef.current?.abort()
    },
    [],
  )

  function fail(caught: unknown) {
    if (caught instanceof ApiError && caught.code === 'presenter_key_invalid') onUnauthorized()
    setError(errorKey(caught))
  }

  async function select(file: File | undefined) {
    setError(null)
    if (!file) {
      setPending(null)
      return
    }
    setPending({ file, meta: isVideo ? await readVideoMeta(file) : null })
  }

  async function upload() {
    if (!pending) return
    setError(null)
    setProgress(0)
    const controller = new AbortController()
    uploadRef.current = controller
    try {
      onChange(
        slot,
        await uploadMedia(slot, pending.file, pending.meta, presenterKey, setProgress, controller.signal),
      )
      setPending(null)
    } catch (caught) {
      if (!controller.signal.aborted) fail(caught)
    } finally {
      uploadRef.current = null
      setProgress(null)
    }
  }

  async function saveLink(event: SubmitEvent) {
    event.preventDefault()
    setError(null)
    try {
      onChange(slot, await linkMedia(slot, link.trim(), presenterKey))
      setLink('')
    } catch (caught) {
      fail(caught)
    }
  }

  async function clear() {
    setError(null)
    try {
      onChange(slot, (await clearMedia(slot, presenterKey)).slots[slot])
    } catch (caught) {
      fail(caught)
    }
  }

  return (
    <Card className={styles.card} role="region" aria-labelledby={headingId}>
      <CardHeader
        header={
          <Text as="h4" id={headingId} weight="semibold">
            {t(title)}
          </Text>
        }
        action={
          record && (
            <Button
              appearance="subtle"
              icon={<Delete20Regular />}
              disabled={busy}
              onClick={() => void clear()}
            >
              {t('clearSlot')}
            </Button>
          )
        }
      />

      {!record ? (
        <Text className={styles.muted}>{t('slotEmpty')}</Text>
      ) : record.kind === 'link' ? (
        <div className={styles.facts}>
          <Link20Regular aria-hidden />
          <Link href={record.url ?? ''} target="_blank" rel="noopener noreferrer" className={styles.filename}>
            {record.url}
          </Link>
        </div>
      ) : (
        <div className={styles.facts}>
          <Text weight="semibold" className={styles.filename}>
            {record.filename}
          </Text>
          {record.bytes != null && <Text>{formatBytes(record.bytes)}</Text>}
          {isVideo && <VideoFacts meta={recordMeta(record)} />}
        </div>
      )}

      <Field label={t('chooseFile')}>
        {(fieldProps) => (
          <input
            {...fieldProps}
            className={styles.file}
            type="file"
            accept={isVideo ? 'video/mp4,.mp4' : '.vtt,.srt,text/vtt'}
            disabled={busy}
            onChange={(event) => void select(event.target.files?.[0])}
          />
        )}
      </Field>

      {pending && (
        <div className={styles.facts} data-testid={`pending-${slot}`}>
          <Text className={styles.muted}>{t('selectedNotUploaded')}</Text>
          <Text weight="semibold" className={styles.filename}>
            {pending.file.name}
          </Text>
          <Text>{formatBytes(pending.file.size)}</Text>
          {isVideo && <VideoFacts meta={pending.meta} />}
          <Button
            appearance="primary"
            icon={<ArrowUpload20Regular />}
            disabled={busy}
            onClick={() => void upload()}
          >
            {busy ? t('uploading') : t('upload')}
          </Button>
        </div>
      )}
      {progress !== null && (
        <Field label={t('uploadProgress')} validationState="none">
          <ProgressBar value={progress} />
        </Field>
      )}
      {progress !== null && (
        <Button
          icon={<Dismiss20Regular />}
          onClick={() => {
            uploadRef.current?.abort()
          }}
        >
          {t('cancelUpload')}
        </Button>
      )}

      {isVideo && (
        <form className={styles.row} onSubmit={(event) => void saveLink(event)}>
          <Field label={t('mediaLink')} className={styles.grow}>
            <Input
              type="url"
              value={link}
              placeholder="https://youtu.be/…"
              disabled={busy}
              onChange={(_, data) => {
                setLink(data.value)
              }}
            />
          </Field>
          <Button type="submit" disabled={busy || link.trim() === ''}>
            {t('saveLink')}
          </Button>
        </form>
      )}

      {error && (
        <MessageBar intent="error" role="alert">
          <MessageBarBody>{t(error)}</MessageBarBody>
        </MessageBar>
      )}
    </Card>
  )
}
