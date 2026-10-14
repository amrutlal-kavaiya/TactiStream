import type { Language } from '../contracts/generated'
import { useMatchStore } from '../store/matchStore'
import { en, type MessageKey } from './en'
import { hi } from './hi'

const catalogs: Record<Language, Record<MessageKey, string>> = { en, hi }

export type Translate = (key: MessageKey) => string

/** Chrome strings in the viewer's language preference. */
export function useT(): Translate {
  const language = useMatchStore((s) => s.prefs.language)
  const catalog = catalogs[language]
  return (key) => catalog[key]
}

/** `mm:ss` or `mm:ss.t` for a millisecond clock. */
export function formatClock(ms: number, tenths = false): string {
  const unit = tenths ? 100 : 1000
  const truncated = Math.floor(Math.max(ms, 0) / unit) * unit
  const minutes = Math.floor(truncated / 60_000)
  const seconds = (truncated - minutes * 60_000) / 1000
  const ss = tenths ? seconds.toFixed(1).padStart(4, '0') : String(seconds).padStart(2, '0')
  return `${String(minutes).padStart(2, '0')}:${ss}`
}
