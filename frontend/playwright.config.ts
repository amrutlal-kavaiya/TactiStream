import { resolve } from 'node:path'

import { defineConfig, devices } from '@playwright/test'

const baseURL = 'http://localhost:8000'

export default defineConfig({
  testDir: 'tests/e2e',
  // Every run drives the same skeleton match session on one server, so tests must not overlap.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  reporter: process.env.CI ? 'github' : 'list',
  use: { baseURL, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run build && cd ../backend && uv run tactistream-api',
    env: { TACTISTREAM_STATIC_DIR: resolve(import.meta.dirname, 'dist') },
    url: `${baseURL}/healthz`,
    // Never reuse a server on :8000: it may be serving a stale dist or a dev backend without one.
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
