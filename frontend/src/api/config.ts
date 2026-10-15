import { useEffect, useState } from 'react'

import { request } from './client'

export interface DemoMediaItem {
  url: string
  kind: 'file' | 'link'
}

/** Published demo media from `GET /api/config`; `null` until the presenter publishes. */
export interface DemoMedia {
  main: DemoMediaItem
  backup: DemoMediaItem | null
  captions_url: string | null
}

export const getConfig = () => request<{ demo_media: DemoMedia | null }>('/api/config')

export interface DemoMediaState {
  media: DemoMedia | null
  loaded: boolean
}

/** Any failure reads as unpublished: judges simply see no video button. */
export function useDemoMedia(): DemoMediaState {
  const [state, setState] = useState<DemoMediaState>({ media: null, loaded: false })
  useEffect(() => {
    let active = true
    void getConfig()
      .then((config) => config.demo_media)
      .catch(() => null)
      .then((media) => {
        if (active) setState({ media, loaded: true })
      })
    return () => {
      active = false
    }
  }, [])
  return state
}
