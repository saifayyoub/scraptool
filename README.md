# EduFeed

EduFeed is a powerful content reader and analytics dashboard designed for productive content curation. It aggregates RSS feeds and supports importing posts from major social media platforms.

## Features

- **Multi-source Curation**: Support for standard RSS feeds and direct post imports from LinkedIn, Facebook, and Instagram.
- **Full-text extraction**: Automatically fetches the complete article when a feed only provides a title or truncated summary (uses `content:encoded` when available, otherwise extracts the main article from the source page). Retry any article with the "Full text" button.
- **Sleek Interface**: Clean, professional, and data-dense productivity interface with dark mode support.
- **Analytics Dashboard**: Real-time analytics with charts for social and distribution metrics.
- **Markdown Support**: Seamlessly paste and format markdown content in the editor.

## Project Structure

- `backend/`: FastAPI application handling the API, database, and feed synchronization.
- `frontend/`: HTML/JS application using TailwindCSS for a responsive and modern UI.

## Getting Started

1. Navigate to the project directory.
2. Run `run.bat` to start the application.

## Watching what the tool is doing

`run.bat` opens a second window titled **EduFeed Backend - Live Activity Log**.
Every request, feed sync, full-text fetch, publish attempt and error is printed
there in real time, so you can see exactly what EduFeed is working on.

- `backend/server.log` - the same output, saved for later (UTF-8).
- `backend/server.prev.log` - the previous run's log, kept for troubleshooting.
- If the backend window is closed, the server stops (EduFeed becomes unreachable).

## Deploy on SnapDeploy

The repository ships a `Dockerfile`, so SnapDeploy builds and runs it as-is.

1. Sign up at <https://snapdeploy.dev> (GitHub login, free tier needs no card).
2. In the dashboard: **New container -> GitHub**, authorize the SnapDeploy GitHub App
   for `saifayyoub/scraptool`, pick branch `main` and root directory `/`.
3. Keep the default build settings. No environment variables are required: SnapDeploy
   injects `PORT` and `HOST`, and `main.py` / the Dockerfile listen on them.
4. Deploy. The first build takes a few minutes (pip install), then the app is live at
   `https://<name>.containers.snapdeploy.app`.
5. Open the container page for live logs - same output as the local backend window.

Free-tier limits that matter for this app:

- 512 MB RAM / 0.25 vCPU, 100 container-hours a month, 10 deploys a day.
- The container sleeps after ~15 minutes without traffic and wakes in ~1 minute.
  Scheduled feed scans do not run while it sleeps.
- **No persistent disk.** The filesystem (including `edufeed.db`) resets on every
  wake, restart and redeploy. The image starts from the database snapshot committed
  to git, so changes made online are lost. For real use, move state to an external
  database or object storage (and use Always-On for 24/7 operation).
- `backend/blogger_config.json` is deliberately not in git, so Blogger publishing
  is not configured on the server.
- The app has no authentication: anyone with the URL can read and change the data.


