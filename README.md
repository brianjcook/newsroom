# Newsroom

Automated local-news publishing system for Wareham, Massachusetts.

## Architecture
- `web/`: PHP 8 publishing app for Freehostia-style shared hosting
- `worker/`: Python ingestion and generation pipeline
- `db/`: MySQL schema and seed files
- `storage/`: fetched documents, extraction artifacts, and logs

## Initial Scope
- Source discovery from `https://www.wareham.gov/AgendaCenter`
- HTML and PDF ingestion
- MySQL-backed stories, citations, meetings, and calendar events
- Newspaper-style public site

## Quick Start

### 1. Database
Create a MySQL database and apply:

```sql
source db/migrations/001_initial_schema.sql;
source db/migrations/002_generation_run_metrics.sql;
source db/seeds/001_sources.sql;
```

### 2. Web config
Set these environment variables for PHP:

- `NEWSROOM_DB_HOST`
- `NEWSROOM_DB_PORT`
- `NEWSROOM_DB_NAME`
- `NEWSROOM_DB_USER`
- `NEWSROOM_DB_PASSWORD`
- `NEWSROOM_SITE_NAME`
- `NEWSROOM_SITE_URL`

On shared hosting, you can instead copy `web/config.local.example.php` to
`web/config.local.php` and fill in the real values. Do not commit that file.

### 3. Worker config
Create a Python virtual environment and install:

```bash
pip install -r worker/requirements.txt
```

Then set the same database environment variables plus:

- `NEWSROOM_SOURCE_DISCOVERY_ENABLED=1`
- `NEWSROOM_FETCH_USER_AGENT`
- `NEWSROOM_SITE_STORAGE_ROOT`

### 4. Run the worker

```bash
python worker/scripts/run_daily.py
```

## Deployment Notes
- Production target database: `bricoo10_newsroom` on host `localhost`
- Intended public hosting target: Freehostia Wildhoney
