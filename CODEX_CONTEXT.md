## Purpose
Build a local-news publishing system that ingests municipal and other local content sources, extracts structured information, drafts news-style articles and calendar items, and publishes them to a newspaper-style website.

## Current scope and decisions
- Project has moved from planning into initial scaffold/build.
- Initial geography is Wareham, Massachusetts.
- Primary v1 source is `https://www.wareham.gov`, especially `https://www.wareham.gov/AgendaCenter`.
- Expected source formats for v1 are HTML and PDFs.
- User wants coverage of local government and community sources such as municipal websites, meeting agendas, and minutes.
- User wants article drafting, local calendar generation, and a newspaper-style web presentation.
- Initial content types in scope: briefs, explainers, and official event listings.
- Out of scope for now: investigations, election guides, email ingestion.
- Publishing preference is auto-publish rather than editor approval.
- Articles should include footnotes or sidenotes with source links where appropriate.
- Initial refresh cadence target is daily.
- Calendar should begin with official meetings only.
- User prefers MySQL over Postgres due to planned hosting on Freehostia Wildhoney.
- Deployment database target provided by user: host `localhost`, database `bricoo10_newsroom`.
- GitHub repository created by user: `https://github.com/brianjcook/newsroom`.
- Visual direction appears to be print/editorial rather than generic modern blog styling, based on reference images in `examples/`.
- Initial implementation direction is a PHP 8 publishing app plus a Python worker, with MySQL as the shared system of record.

## Implemented work summary
- Confirmed `C:\codex\newsroom` exists.
- Confirmed `examples/` contains editorial layout references.
- Created initial project handoff context file.
- Captured initial product constraints for Wareham-focused v1.
- Verified Freehostia Wildhoney publicly advertises MySQL, Python, PHP, and cron-job support, making MySQL feasible for deployment-oriented planning.
- Added `V1_BLUEPRINT.md` with product scope, architecture, data model, publishing model, and safety rules.
- Added `IMPLEMENTATION_ROADMAP.md` with phased build order and immediate next tasks.
- Initialized local git repository in `C:\codex\newsroom`.
- Added `origin` remote pointing to the GitHub repository and set the local branch to `main`.
- Recorded Freehostia MySQL deployment target details supplied by user.
- Added the initial repository scaffold:
- `web/` PHP publishing app
- `worker/` Python pipeline package
- `db/` MySQL migrations and seeds
- `storage/` runtime artifact directories
- Added initial MySQL schema and seed files for Wareham `AgendaCenter`.
- Added a first-pass newspaper-style public site scaffold with homepage, story page, and calendar page.
- Added a first-pass Python daily pipeline command that seeds run history and performs Wareham `AgendaCenter` source discovery into `source_items`.
- Validated the scaffold with `python -m compileall worker` and PHP linting on public entrypoint files.

## Key files/entry points
- `C:\codex\newsroom\CODEX_CONTEXT.md`
- `C:\codex\newsroom\V1_BLUEPRINT.md`
- `C:\codex\newsroom\IMPLEMENTATION_ROADMAP.md`
- `C:\codex\newsroom\README.md`
- `C:\codex\newsroom\db\migrations\001_initial_schema.sql`
- `C:\codex\newsroom\db\seeds\001_sources.sql`
- `C:\codex\newsroom\web\public\index.php`
- `C:\codex\newsroom\web\public\story.php`
- `C:\codex\newsroom\web\public\calendar.php`
- `C:\codex\newsroom\worker\scripts\run_daily.py`
- `C:\codex\newsroom\worker\newsroom\pipeline.py`
- `C:\codex\newsroom\worker\newsroom\sources.py`
- `C:\codex\newsroom\examples\`

## Deployment/runtime status
- Initial application scaffold exists.
- Initial ingestion/source-discovery pipeline exists but is not yet fully wired for document download, extraction, generation, or publishing.
- Tentative hosting target is Freehostia Wildhoney.
- Shared-hosting constraints likely require simple scheduled jobs and a deployment shape that does not depend on persistent background workers.
- Preferred architectural direction is a PHP/MySQL publishing app plus a Python ingestion/generation worker.
- Production database target named by user: MySQL database `bricoo10_newsroom` on host `localhost`.

## Recent commits
- `655a78b` - `Initial newsroom scaffold`

## Next priority tasks
- Push the initial scaffold to GitHub.
- Add configuration guidance for deployment credentials and local development.
- Extend the worker from source discovery to document fetch, storage, and extraction.
- Add a minimal admin/status page for generation runs and failed items.
- Continue refining the site typography and layout against the editorial references.

## Resume prompt for a brand-new Codex session
Read `C:\codex\newsroom\CODEX_CONTEXT.md` first, then `C:\codex\newsroom\V1_BLUEPRINT.md`, then `C:\codex\newsroom\IMPLEMENTATION_ROADMAP.md`. The project is a Wareham, Massachusetts local-news platform with an initial scaffold already created: PHP public site, Python worker, MySQL schema, and Wareham `AgendaCenter` source seeding/discovery. Hosting target is Freehostia Wildhoney with MySQL database `bricoo10_newsroom` on `localhost`. Continue by extending the worker into document fetching/extraction and wiring published content into the web app.
