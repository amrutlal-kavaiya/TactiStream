import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../src/api/client'
import { uploadMedia } from '../../src/presenter/api'
import { MockXHR } from './http'

const file = new File([new Uint8Array(4)], 'demo.mp4', { type: 'video/mp4' })

function start(signal?: AbortSignal) {
  const promise = uploadMedia('main', file, null, 'k1', () => undefined, signal)
  const xhr = MockXHR.instances[0]
  if (!xhr) throw new Error('no XHR sent')
  return { promise, xhr }
}

beforeEach(() => {
  MockXHR.instances = []
  vi.stubGlobal('XMLHttpRequest', MockXHR)
})

describe('uploadMedia', () => {
  it('aborts the XHR when the signal fires and rejects with AbortError', async () => {
    const controller = new AbortController()
    const { promise, xhr } = start(controller.signal)
    controller.abort()
    expect(xhr.aborted).toBe(true)
    await expect(promise).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('does not send when the signal has already fired', async () => {
    const controller = new AbortController()
    controller.abort()
    await expect(
      uploadMedia('main', file, null, 'k1', () => undefined, controller.signal),
    ).rejects.toMatchObject({ name: 'AbortError' })
    expect(MockXHR.instances).toHaveLength(0)
  })

  it.each(['onerror', 'ontimeout'] as const)('rejects with a network error on %s', async (handler) => {
    const { promise, xhr } = start()
    xhr[handler]?.()
    await expect(promise).rejects.toBeInstanceOf(ApiError)
    await expect(promise).rejects.toMatchObject({ code: 'network_error' })
  })

  it('rejects on a bare onabort', async () => {
    const { promise, xhr } = start()
    xhr.abort()
    await expect(promise).rejects.toMatchObject({ name: 'AbortError' })
  })
})
