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
- Freehostia SSH access works intermittently; one successful session confirmed `python3` is `3.6.8`, `python` is unavailable, and the account is effectively rooted at `/home` with a `www` directory present.
- Domain-scoped FTPS access for `warehamtimes.com` works and appears rooted at the site directory itself.
- Canonical host preference is now `https://www.warehamtimes.com`.
- Typography direction is now defined as:
- `Manufacturing Consent` for the masthead
- `Merriweather` for body copy and some headlines
- `Fira Code` for eyebrows and metadata
- `Datatype` for data-heavy numerals and chart-like values
- `Roboto Condensed` for sans-serif headlines
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
- Added `002_generation_run_metrics.sql` to track fetched documents, created extractions, and normalized meetings per pipeline run.
- Extended the worker with document download/storage, HTML/PDF extraction, and first-pass meeting normalization.
- Added a minimal status page that displays recent pipeline runs and ingestion counts.
- Re-ran syntax validation after the pipeline expansion with `python -m compileall worker` and PHP linting on public entrypoints including `status.php`.
- Added deterministic story publication from normalized meetings into `stories` and `story_citations`.
- Added calendar-event generation from normalized meetings into `calendar_events`.
- Updated pipeline run reporting so `generation_runs` now surfaces published story and created event counts in the status page.
- Improved meeting parsing with broader date/time/body/location heuristics aimed at Wareham-style agendas and minutes.
- Added diagnostics to the status page for low-confidence or review-needed source items.
- Added a publish-time quality gate so records missing a governing body or meeting date are withheld from public story output.
- Adjusted the worker codebase for Python 3.6 compatibility after confirming the Freehostia host runtime.
- Added PHP support for a local config-file fallback via `web/config.local.php` for shared-hosting deployments.
- Uploaded the PHP site files to the `warehamtimes.com` FTPS root and replaced the default `index.xhtml` with the newsroom site entrypoint.
- Uploaded a non-tracked production `config.local.php` to the host with the live MySQL connection values.
- Applied the MySQL schema and initial source seed on the Freehostia host using the local `mysql` client.
- Verified the expected tables exist in `bricoo10_newsroom` and that the `wareham-agenda-center` source seed is present.
- Added `.htaccess` rules to force HTTPS and the `www` host for `warehamtimes.com`.
- Updated the site templates and CSS to use the requested font stack.
- Uploaded the Python worker and protected `storage/`/`worker/` directories to the host.
- Installed the worker dependencies into a site-local Python user base under the Freehostia account.
- Ran the first successful live pipeline on production:
- `items_discovered`: `370`
- `documents_fetched`: `370`
- `extractions_created`: `370`
- `meetings_normalized`: `158`
- `stories_published`: `91`
- `events_created`: `176`
- Removed the temporary host probe script after the successful run.

## Key files/entry points
- `C:\codex\newsroom\CODEX_CONTEXT.md`
- `C:\codex\newsroom\V1_BLUEPRINT.md`
- `C:\codex\newsroom\IMPLEMENTATION_ROADMAP.md`
- `C:\codex\newsroom\README.md`
- `C:\codex\newsroom\db\migrations\001_initial_schema.sql`
- `C:\codex\newsroom\db\migrations\002_generation_run_metrics.sql`
- `C:\codex\newsroom\db\seeds\001_sources.sql`
- `C:\codex\newsroom\web\public\index.php`
- `C:\codex\newsroom\web\public\story.php`
- `C:\codex\newsroom\web\public\calendar.php`
- `C:\codex\newsroom\web\public\status.php`
- `C:\codex\newsroom\web\public\.htaccess`
- `C:\codex\newsroom\web\config.local.example.php`
- `C:\codex\newsroom\worker\scripts\run_daily.py`
- `C:\codex\newsroom\worker\newsroom\pipeline.py`
- `C:\codex\newsroom\worker\newsroom\sources.py`
- `C:\codex\newsroom\worker\newsroom\documents.py`
- `C:\codex\newsroom\worker\newsroom\extract.py`
- `C:\codex\newsroom\worker\newsroom\meetings.py`
- `C:\codex\newsroom\worker\newsroom\publish.py`
- `C:\codex\newsroom\examples\`

## Deployment/runtime status
- Initial application scaffold exists.
- Initial ingestion pipeline now supports source discovery, document download/storage, HTML/PDF extraction, first-pass meeting normalization, deterministic story publication, citation creation, and calendar-event generation.
- Story output is currently template-based and source-grounded rather than model-generated.
- Records with weak parsing now remain visible in diagnostics instead of being published automatically.
- Tentative hosting target is Freehostia Wildhoney.
- Shared-hosting constraints likely require simple scheduled jobs and a deployment shape that does not depend on persistent background workers.
- Preferred architectural direction is a PHP/MySQL publishing app plus a Python ingestion/generation worker.
- Production database target named by user: MySQL database `bricoo10_newsroom` on host `localhost`.
- Initial scaffold has been pushed to GitHub `main`.
- The PHP web app has been deployed to the `warehamtimes.com` FTPS root, including a host-local `config.local.php`.
- The MySQL schema and initial source seed have been applied successfully on the production database.
- `.htaccess` has been deployed to force `https://www.warehamtimes.com`.
- Public verification is now confirmed: homepage and status page render live data.
- Worker deployment succeeded and at least one live production run completed successfully.
- SSH remains intermittent, but FTPS plus the now-installed on-host Python environment are sufficient for follow-up worker iterations.

## Recent commits
- `655a78b` - `Initial newsroom scaffold`
- `a0fae08` - `Update project context after scaffold`
- `3b96a0f` - `Record GitHub push status`
- `0fce793` - `Add document processing pipeline`
- `6ae52d9` - `Publish stories and calendar events`
- `12f7ac1` - `Add diagnostics and parsing safeguards`
- `bbd4318` - `Make worker compatible with Freehostia Python`
- `c693bf8` - `Add shared-host config support`
- `bcb2333` - `Deploy canonical redirects and typography`

## Next priority tasks
- Add configuration guidance for deployment credentials and local development.
- Improve meeting parsing quality further using live Wareham examples once the pipeline is run against the real database.
- Add a more detailed diagnostics view with per-item parsing failures and extraction warnings rendered cleanly instead of raw JSON.
- Replace or augment deterministic story generation with a constrained model-backed drafting step when credentials and runtime are available.
- Improve the quality of generated headlines, summaries, event titles, and board-name normalization now that live data is flowing.
- Decide how recurring worker runs will be triggered on-host, likely via cron or a protected trigger endpoint.
- Continue refining the site typography and layout against the editorial references.

## Resume prompt for a brand-new Codex session
Read `C:\codex\newsroom\CODEX_CONTEXT.md` first, then `C:\codex\newsroom\V1_BLUEPRINT.md`, then `C:\codex\newsroom\IMPLEMENTATION_ROADMAP.md`. The project is a Wareham, Massachusetts local-news platform with a live PHP public site, a deployed Python worker, a production MySQL schema, Wareham `AgendaCenter` source seeding/discovery, document download/storage, HTML/PDF extraction, first-pass meeting normalization, deterministic story publication with citations, calendar-event generation, and a status page with diagnostics. Hosting target is Freehostia Wildhoney. The PHP site, `.htaccess`, and a non-tracked production `config.local.php` are deployed to the `warehamtimes.com` FTPS root. The worker is Python 3.6-compatible, its dependencies are installed into a site-local Python user base, and the first live run completed successfully with 370 discovered items, 158 normalized meetings, 91 published stories, and 176 created events. Next priority is improving content quality and setting up a repeatable on-host trigger for future runs.
