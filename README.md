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
3. Keep the default build settings. Add `DATABASE_URL` (see *Keep your data on a
   deployed server*) so your changes are saved, or leave it empty to run on the
   reset-on-restart SQLite file.
4. Deploy. The app is live at `https://<name>.containers.snapdeploy.app`.
5. Open the container page for live logs - same output as the local backend window.

### Light Cloud

1. Sign in at <https://console.light-cloud.com> with GitHub and install the Light Cloud
   GitHub App for `saifayyoub/scraptool`.
2. **Create -> Deploy from GitHub**, choose the repository and branch `main`.
   The type is detected as **Dockerfile / Backend (runs on a server)**.
3. Leave install/build commands empty and the port at `8080` (read from `EXPOSE`).
   Add `DATABASE_URL` (see *Keep your data on a deployed server*) so your changes
   are saved.
4. Click **Deploy**. The app is live at
   `https://{branch}-{app}-{workspace}.light-cloud.io`, and every push to `main`
   redeploys it.

## Keep your data on a deployed server (PostgreSQL)

A container has no permanent disk: every restart, wake from sleep or redeploy
resets its files back to the image. That is why an article you marked as done
came back after a while. Both platforms allow outbound connections to a hosted
database, so EduFeed can store its data outside the container:

- Local use (`run.bat`) keeps using the bundled SQLite file - nothing to set up.
- On a server, set the `DATABASE_URL` environment variable and the same backend
  stores everything in PostgreSQL instead.

### 1. The database for this project

This repository is linked to the Neon project `my-first-project`
(`cool-scene-62264594`, organisation `org-summer-cake-13224688`, branch
`production`, region `aws-eu-central-1`). The Neon CLI wrote the connection
string to `.env.local` in the project root; that file is gitignored on purpose,
so the secret never reaches GitHub or the Docker image.

To use a different database, run `neon init` again (or create a project at
<https://neon.com>) and put its connection string in `.env.local`.

### 2. Point the deployments at it

Add one environment variable named `DATABASE_URL` with the value from
`.env.local` (the line that starts with `DATABASE_URL=`):

- **SnapDeploy**: open the container -> **Environment variables** -> add
  `DATABASE_URL` -> save (it restarts the container with the new value).
- **Light Cloud**: open the app -> **Environment variables** -> add `DATABASE_URL`
  -> save, then **Deploy** (or push to `main`) to restart it.

With the Light Cloud CLI the same step is:

```sh
lc env vars set DATABASE_URL="postgresql://..." --redeploy
```

The tables are created automatically on the first start.

### 3. Copy your current local data (one time)

From the `backend` folder on your PC:

```bat
venv\Scripts\python.exe migrate_to_postgres.py
```

The script reads the connection string from `.env.local` automatically. To point
it somewhere else, set it yourself first:

```bat
set DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
venv\Scripts\python.exe migrate_to_postgres.py
```

It copies feeds, folders and articles (keeping their ids and statuses). Re-running
is safe and quick: rows that already exist are skipped, so it only adds what is
missing and never overwrites changes you made online. Afterwards the deployed app
shows the same data as your local copy, and every change you make online is saved
in PostgreSQL, so it survives refreshes, sleeps and redeploys.

Without `DATABASE_URL` the app works exactly as before, with `backend/edufeed.db`.

### Limits that matter for this app (both platforms)

- Free tiers sleep / scale to zero when idle, so scheduled feed scans do not run then.
  SnapDeploy sleeps after ~15 min; Light Cloud scales to zero and wakes on the next visit.
- `backend/blogger_config.json` is deliberately not in git, so Blogger publishing
  is not configured on the server.
- The app has no authentication: anyone with the URL can read and change the data.



