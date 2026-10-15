# Presenter page

`/presenter` is where the builder rehearses the jury demo, follows the recording checklist, and uploads (or links) the main
demo video, the backup recording and the captions. One switch publishes them to judges. The page isn't linked from the
judge UI, and the server only enables it when `TACTISTREAM_PRESENTER_KEY` is set. Without the key, the page says
"Presenter mode is disabled on this server" and every `/api/presenter/*` call returns 404.

Judges watch at **`/watch`**. It's the one stable link for the README, judge guide and submission checklist. Once media
is published, the match app header also shows a **Watch demo video** button.

## Set the key

The key is a Container Apps secret. It never goes in git or logs. The browser keeps it in `sessionStorage` only, so
closing the tab forgets it. Use a long random value; the server refuses to start with a key shorter than 16
characters (surrounding whitespace is stripped):

```bash
KEY=$(openssl rand -base64 24)
```

**Persistent (survives `azd provision`).** `infra/main.bicep` takes a `@secure() presenterKey` parameter, which
`main.parameters.json` fills from the azd env. When it's non-empty, the container app gets secret `presenter-key` and
env `TACTISTREAM_PRESENTER_KEY=secretref:presenter-key`. When it's empty (the default), neither is created and presenter
mode is off. Container Apps rejects empty secret values, which is why the secret is conditional.

```bash
azd env set TACTISTREAM_PRESENTER_KEY "$KEY"
azd provision
```

**Quick, without reprovisioning.** This lasts until the next `azd provision` with an empty azd value, which removes it:

```bash
az containerapp secret set -n tactistream -g rg-tactistream-prod --secrets presenter-key="$KEY"
az containerapp update -n tactistream -g rg-tactistream-prod \
  --set-env-vars TACTISTREAM_PRESENTER_KEY=secretref:presenter-key
```

Secret changes don't restart a running revision. After rotating a key whose env var already exists, run
`az containerapp revision restart -n tactistream -g rg-tactistream-prod --revision <active-revision>`.

To disable presenter mode, run `azd env set TACTISTREAM_PRESENTER_KEY ""` and then `azd provision`. Already-published
media stays visible at `/watch` until you unpublish it, so turn **Publish** off first if it should disappear.

Locally, put `TACTISTREAM_PRESENTER_KEY=local-presenter-key` (at least 16 characters) in `.env`, run `make dev`, and open http://localhost:5173/presenter.

## Use the page

1. **Rehearse.** The eight beats come from the Timeline in `specs/009-submission/demo-script.md`, and a unit test keeps
   them equal. Start the 1:55 timer and the current beat is highlighted. Past 1:55 the page says to cut from
   0:58–1:13 first. **Open live app** opens `/demo?seed=42` in a new tab.
2. **Record checklist.** H.264 MP4, exactly 1920×1080, 110–119 s, a backup take labelled "Backup recording —
   TactiStream deployed app, recorded 25 Oct 2026" (title and first frame), and synced English captions. Ticks are
   saved in `localStorage["tactistream.presenter.checklist"]`.
3. **Media.** Each slot (main demo video, backup recording, captions) takes a file or an https link, such as an
   unlisted YouTube URL.
   - When you pick a video, the page shows its duration and resolution before uploading. It shows a green "Meets video
     spec" badge, or a warning badge naming the failed rule. Warnings don't block the upload.
   - Uploads stream to the server with a progress bar. The limits are 500 MB for video and 1 MB for captions. `.srt`
     captions are converted to `.vtt` on save.
   - Duration and resolution are what the browser reported (`client_reported`). Confirm the real values with
     `ffprobe` before recording day.
4. **Publish.** This switch makes the media visible to judges. It stays disabled until the main slot has a file or
   link. Turning it off hides the header button and makes `/watch` say "The demo video is not published yet".

Files and `media/state.json` live in the media store: blob container `artifacts` under `media/` when
`TACTISTREAM_ARTIFACT_STORE=blob` (deployed), or `data/media/` locally (gitignored). They survive restarts and
redeploys. File slots are served at `/media/{slot}` with HTTP Range support, so the player can seek. Before publishing,
`/media/*` returns 404 to anyone without the key.

## Checks

- `cd frontend && npx playwright test presenter.spec.ts` covers the whole flow: wrong key refused, upload, publish,
  the judge dialog plays with captions, `/watch`, unpublish, and axe scans in both themes. The sample video is
  regenerated with `npm run sample-video`, which needs an ffmpeg with libx264.
- On the deployed app, publish the real videos. Then open `/watch` in a logged-out browser and confirm playback with
  captions. Record the result in `specs/009-submission/submission-checklist.md` (SC-009).
