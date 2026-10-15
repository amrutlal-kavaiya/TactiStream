// Regenerates the e2e fixture `tests/e2e/fixtures/sample.mp4` (2 s H.264, ~45 KB): `npm run sample-video`.
// Needs an ffmpeg with libx264: `ffmpeg` on PATH, or FFMPEG=/path/to/ffmpeg (e.g. the static binary from `pip install imageio-ffmpeg`).
// The committed file is what the e2e uses, so this only runs when the fixture should change.
import { execFileSync } from 'node:child_process'
import { statSync } from 'node:fs'

const ffmpeg = process.env.FFMPEG ?? 'ffmpeg'
const out = new URL('../tests/e2e/fixtures/sample.mp4', import.meta.url).pathname

execFileSync(
  ffmpeg,
  [
    ...['-hide_banner', '-loglevel', 'error', '-y'],
    ...['-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=15:duration=2'],
    ...['-c:v', 'libx264', '-profile:v', 'baseline', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an'],
    out,
  ],
  { stdio: 'inherit' },
)
console.log(`${out}: ${String(statSync(out).size)} bytes`)
