import { ApiError, apiError, request } from '../api/client'
import type { VideoMeta } from './beats'

export type MediaSlot = 'main' | 'backup' | 'captions'

export const MEDIA_SLOTS: readonly MediaSlot[] = ['main', 'backup', 'captions']

export interface MediaRecord {
  slot: MediaSlot
  kind: 'file' | 'link'
  url?: string | null
  filename?: string | null
  content_type?: string | null
  bytes?: number | null
  sha256?: string | null
  duration_s?: number | null
  width?: number | null
  height?: number | null
  client_reported?: string[]
  uploaded_at?: string
}

export interface PresenterState {
  slots: Partial<Record<MediaSlot, MediaRecord>>
  published: boolean
}

/** sessionStorage only (FR-026): the key never outlives the tab. */
export const PRESENTER_KEY_STORAGE = 'tactistream.presenter.key'

const keyHeader = (key: string): Record<string, string> => (key ? { 'X-Presenter-Key': key } : {})

const sendJson = <T>(method: string, path: string, key: string, body?: unknown) =>
  request<T>(path, {
    method,
    headers: { ...keyHeader(key), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

export const getPresenterState = (key: string) =>
  request<PresenterState>('/api/presenter/state', { headers: keyHeader(key) })

export const linkMedia = (slot: MediaSlot, url: string, key: string) =>
  sendJson<MediaRecord>('PUT', `/api/presenter/media/${slot}`, key, { url })

export const clearMedia = (slot: MediaSlot, key: string) =>
  sendJson<PresenterState>('DELETE', `/api/presenter/media/${slot}`, key)

export const setPublished = (published: boolean, key: string) =>
  sendJson<PresenterState>('PUT', '/api/presenter/publish', key, { published })

function uploadContentType(slot: MediaSlot, file: File): string {
  if (file.type) return file.type
  if (slot !== 'captions') return 'video/mp4'
  return file.name.toLowerCase().endsWith('.srt') ? 'application/x-subrip' : 'text/vtt'
}

/** Streams the file as the request body; `fetch` cannot report upload progress, so this uses XHR. */
export function uploadMedia(
  slot: MediaSlot,
  file: File,
  meta: VideoMeta | null,
  key: string,
  onProgress: (fraction: number) => void,
): Promise<MediaRecord> {
  const params = new URLSearchParams({ filename: file.name })
  if (meta) {
    params.set('duration_s', String(meta.duration_s))
    params.set('width', String(meta.width))
    params.set('height', String(meta.height))
  }
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', `/api/presenter/media/${slot}?${params.toString()}`)
    xhr.setRequestHeader('X-Presenter-Key', key)
    xhr.setRequestHeader('Content-Type', uploadContentType(slot, file))
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) onProgress(event.loaded / event.total)
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText) as MediaRecord)
      else reject(apiError(xhr.status, xhr.responseText))
    }
    xhr.onerror = () => {
      reject(new ApiError(0, 'network_error', 'upload failed'))
    }
    xhr.send(file)
  })
}
