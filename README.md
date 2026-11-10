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

