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

## Deploy on SnapDeploy or Light Cloud

The repository ships a `Dockerfile` that both platforms build as-is: it listens on
`0.0.0.0`, reads `PORT` from the environment and exposes port `8080`.

### SnapDeploy

1. Sign up at <https://snapdeploy.dev> (GitHub login, free tier needs no card).
2. In the dashboard: **New container -> GitHub**, authorize the SnapDeploy GitHub App
   for `saifayyoub/scraptool`, pick branch `main` and root directory `/`.
3. Keep the default build settings. No environment variables are required.
4. Deploy. The app is live at `https://<name>.containers.snapdeploy.app`.
5. Open the container page for live logs - same output as the local backend window.

### Light Cloud

1. Sign in at <https://console.light-cloud.com> with GitHub and install the Light Cloud
   GitHub App for `saifayyoub/scraptool`.
2. **Create -> Deploy from GitHub**, choose the repository and branch `main`.
   The type is detected as **Dockerfile / Backend (runs on a server)**.
3. Leave install/build commands empty and the port at `8080` (read from `EXPOSE`).
   No environment variables are needed.
4. Click **Deploy**. The app is live at
   `https://{branch}-{app}-{workspace}.light-cloud.io`, and every push to `main`
   redeploys it.

### Limits that matter for this app (both platforms)

- Free tiers sleep / scale to zero when idle, so scheduled feed scans do not run then.
  SnapDeploy sleeps after ~15 min; Light Cloud scales to zero and wakes on the next visit.
- **No persistent disk.** The filesystem (including `edufeed.db`) resets on every
  wake, restart and redeploy. The image starts from the database snapshot committed
  to git, so changes made online are lost. For real use, move state to an external
  database or object storage and use an always-on plan.
- `backend/blogger_config.json` is deliberately not in git, so Blogger publishing
  is not configured on the server.
- The app has no authentication: anyone with the URL can read and change the data.


