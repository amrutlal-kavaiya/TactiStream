import { resolve } from 'node:path'

import { defineConfig, devices } from '@playwright/test'

// Other worktrees may hold :8000; `E2E_PORT=8100 npx playwright test` runs on a free port.
const port = Number(process.env.E2E_PORT ?? 8000)
const baseURL = `http://localhost:${String(port)}`

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
    // `tactistream-api` always binds :8000, so the app factory is served directly to honour the port.
    command: `npm run build && cd ../backend && uv run uvicorn tactistream.api.app:create_app --factory --host 127.0.0.1 --port ${String(port)}`,
    env: { TACTISTREAM_STATIC_DIR: resolve(import.meta.dirname, 'dist') },
    url: `${baseURL}/healthz`,
    // Never reuse a server on the port: it may be serving a stale dist or a dev backend without one.
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
