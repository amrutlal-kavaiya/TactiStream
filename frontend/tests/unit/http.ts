import { vi } from 'vitest'

export type Route = (init?: RequestInit) => Response

export interface FetchCall {
  key: string
  headers: Headers
  body: unknown
}

export const json =
  (status: number, body: unknown): Route =>
  () =>
    new Response(JSON.stringify(body), { status })

/** Routes `fetch` by `"METHOD path"`; `routes` stays live so tests can swap responses mid-test. */
export function stubFetch(routes: Record<string, Route>): FetchCall[] {
  const calls: FetchCall[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string, init?: RequestInit) => {
      const key = `${init?.method ?? 'GET'} ${path}`
      calls.push({
        key,
        headers: new Headers(init?.headers),
        body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined,
      })
      const route = routes[key]
      return Promise.resolve(route ? route(init) : new Response('not routed', { status: 500 }))
    }),
  )
  return calls
}

export class MockXHR {
  static instances: MockXHR[] = []
  method = ''
  url = ''
  headers: Record<string, string> = {}
  body: unknown = null
  status = 0
  responseText = ''
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null

  open(method: string, url: string) {
    this.method = method
    this.url = url
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name.toLowerCase()] = value
  }

  send(body: unknown) {
    this.body = body
    MockXHR.instances.push(this)
  }

  respond(status: number, body: unknown) {
    this.upload.onprogress?.({ lengthComputable: true, loaded: 1, total: 1 } as ProgressEvent)
    this.status = status
    this.responseText = JSON.stringify(body)
    this.onload?.()
  }
}

export interface VideoMetadata {
  duration: number
  width: number
  height: number
}

/** jsdom never loads media: setting `src` fires `loadedmetadata` with the given values. */
export function mockVideoMetadata(meta: VideoMetadata) {
  vi.stubGlobal(
    'URL',
    Object.assign(URL, { createObjectURL: () => 'blob:mock', revokeObjectURL: () => undefined }),
  )
  Object.defineProperty(HTMLMediaElement.prototype, 'src', {
    configurable: true,
    get: () => '',
    set(this: HTMLMediaElement) {
      queueMicrotask(() => this.dispatchEvent(new Event('loadedmetadata')))
    },
  })
  Object.defineProperty(HTMLMediaElement.prototype, 'duration', {
    configurable: true,
    get: () => meta.duration,
  })
  Object.defineProperty(HTMLVideoElement.prototype, 'videoWidth', {
    configurable: true,
    get: () => meta.width,
  })
  Object.defineProperty(HTMLVideoElement.prototype, 'videoHeight', {
    configurable: true,
    get: () => meta.height,
  })
}
