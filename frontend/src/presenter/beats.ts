import type { MessageKey } from '../i18n/en'

export interface Beat {
  start_s: number
  end_s: number
  time: string
  action: string
  intent: string
}

const beat = (start_s: number, end_s: number, action: string, intent: string): Beat => ({
  start_s,
  end_s,
  time: `${formatDuration(start_s)}–${formatDuration(end_s)}`,
  action,
  intent,
})

/** Verbatim from the Timeline table in `specs/009-submission/demo-script.md` (a unit test keeps them equal). */
export const BEATS: readonly Beat[] = [
  beat(
    0,
    8,
    'Show the shot, then the Why card',
    '"The shot is obvious. The run that opened the space is easier to miss."',
  ),
  beat(
    8,
    30,
    'Rewind in 3D; highlight runner, defender and channel',
    'Explain the invisible contribution using visible evidence',
  ),
  beat(30, 43, 'Expand the evidence drawer', 'Show factual measurements and the interpretation distinction'),
  beat(
    43,
    58,
    'Change Fan to Analyst; switch to Hindi; pin the runner',
    'Same facts, different useful experiences',
  ),
  beat(
    58,
    73,
    'Load an unseen seed or alternate sequence',
    'Show the running system handles a second example',
  ),
  beat(
    73,
    88,
    'Trigger a labeled missing-data or timeout fixture',
    'Show a blocked claim and a useful fallback',
  ),
  beat(
    88,
    105,
    'Generate recap and inspect timed overlay output',
    'Connect the experience to a studio workflow',
  ),
  beat(
    105,
    115,
    'Show measured results and the live project link',
    'State the product value and actual deployed stack',
  ),
]

export const REHEARSAL_S = 115

/** The beat being performed at `elapsed_s`; the last beat stays current once time runs over. */
export function beatIndexAt(elapsed_s: number): number {
  const index = BEATS.findIndex((b) => elapsed_s < b.end_s)
  return index < 0 ? BEATS.length - 1 : index
}

export const CHECKLIST_STORAGE_KEY = 'tactistream.presenter.checklist'

export const CHECKLIST: readonly { id: string; label: MessageKey }[] = [
  { id: 'h264', label: 'checkH264' },
  { id: 'resolution', label: 'checkResolution' },
  { id: 'duration', label: 'checkDuration' },
  { id: 'backup', label: 'checkBackup' },
  { id: 'captions', label: 'checkCaptions' },
]

export interface VideoMeta {
  duration_s: number
  width: number
  height: number
}

export type SpecIssue = 'duration' | 'resolution'

const MIN_S = 110
const MAX_S = 119

export function videoSpecIssues(meta: VideoMeta): SpecIssue[] {
  const issues: SpecIssue[] = []
  if (!(meta.duration_s >= MIN_S && meta.duration_s <= MAX_S)) issues.push('duration')
  if (meta.width !== 1920 || meta.height !== 1080) issues.push('resolution')
  return issues
}

/** `m:ss`, truncated to whole seconds. */
export function formatDuration(seconds: number): string {
  const whole = Math.max(Math.floor(seconds), 0)
  return `${String(Math.floor(whole / 60))}:${String(whole % 60).padStart(2, '0')}`
}

/** The browser's own reading of the file; `null` when it cannot decode the header. */
export function readVideoMeta(file: File): Promise<VideoMeta | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const video = document.createElement('video')
    const done = (meta: VideoMeta | null) => {
      URL.revokeObjectURL(url)
      resolve(meta)
    }
    video.preload = 'metadata'
    video.onloadedmetadata = () => {
      const ok = Number.isFinite(video.duration) && video.videoWidth > 0
      done(ok ? { duration_s: video.duration, width: video.videoWidth, height: video.videoHeight } : null)
    }
    video.onerror = () => {
      done(null)
    }
    video.src = url
  })
}
