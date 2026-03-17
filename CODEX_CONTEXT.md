## Purpose
Build a local-news publishing system that ingests municipal and other local content sources, extracts structured information, drafts news-style articles and calendar items, and publishes them to a newspaper-style website.

## Current scope and decisions
- Initial geography is Wareham, Massachusetts.
- Primary v1 source is `https://www.wareham.gov`, especially `https://www.wareham.gov/AgendaCenter`.
- Expected source formats for v1 are HTML and PDFs.
- Initial content types in scope: briefs, explainers, meeting previews, minutes recaps, and official event listings.
- Out of scope for now: investigations, election guides, email ingestion.
- Publishing preference is auto-publish rather than editor approval.
- Articles should include footnotes or sidenotes with source links where appropriate.
- Initial refresh cadence target is daily.
- Calendar should begin with official meetings only.
- User prefers MySQL over Postgres due to planned hosting on Freehostia Wildhoney.
- Canonical host preference is `https://www.warehamtimes.com`.
- User wants the site to prioritize timely/recent content over older discovered records.
- User wants to move toward descriptive, parameter-free, SEO-friendly URL patterns where practical.
- Typography direction is:
- `Manufacturing Consent` for the masthead
- `Merriweather` for body copy and some headlines
- `Fira Code` for eyebrows and metadata
- `Datatype` for data-heavy numerals and chart-like values
- `Roboto Condensed` for sans-serif headlines
- Architectural direction is a PHP 8 publishing app plus a Python worker, with MySQL as the shared system of record.
- The data model direction is now meeting-first:
- `municipalities`
- `governing_bodies`
- canonical `meetings`
- sibling `meeting_artifacts` for agendas/minutes/packets/previous versions
- `stories` and `calendar_events` published downstream from canonical meetings

## Implemented work summary
- Created the planning docs: `V1_BLUEPRINT.md` and `IMPLEMENTATION_ROADMAP.md`.
- Initialized the git repo, connected GitHub, and scaffolded the project under `web/`, `worker/`, `db/`, and `storage/`.
- Added initial MySQL schema and source seed files for Wareham `AgendaCenter`.
- Built the PHP public site with homepage, story page, calendar page, and status page.
- Built the Python worker for source discovery, document fetch/storage, HTML/PDF extraction, meeting normalization, story publication, and calendar generation.
- Added `002_generation_run_metrics.sql` for richer run reporting.
- Added diagnostics for low-confidence or review-needed source items.
- Added `003_meeting_first_model.sql` and applied it on production.
- Added `worker/newsroom/modeling.py` for governing-body normalization, artifact classification, story date derivation, and other shared meeting-first logic.
- Added `worker/newsroom/artifacts.py` to sync sibling artifacts onto canonical meetings.
- Refactored `sources.py` to parse AgendaCenter more structurally, capturing governing body, meeting date, posted timestamp, artifact label, and meeting key from the listing page.
- Refactored `documents.py` so AgendaCenter wrapper URLs are resolved through `?html=true`, harvesting wrapper metadata and linked `ViewFile/Item/...` documents before storing the real source document.
- Refactored `extract.py` so actual agenda PDFs produce structured agenda sections/highlights and preserve wrapper metadata such as remote-access details.
- Refactored `meetings.py` to normalize source items into canonical meetings keyed by governing body/date and to upsert governing bodies.
- Tightened meeting normalization so non-primary artifacts can enrich missing fields but cannot overwrite correct canonical time/location data.
- Refactored `publish.py` so stories and calendar events are driven by primary artifacts, allowing preview and recap stories per meeting and handling slug collisions for same-body same-day meetings.
- Preview stories can now render agenda-highlight lists and source-grounded explainer notes for specific items, with the Select Board wastewater-plan case used as the first working example.
- Refactored `artifacts.py` so meeting artifacts prefer the latest resolved document and latest extraction per source item instead of stale wrapper documents.
- Updated `web/lib/content.php` so the homepage prioritizes imminent upcoming meeting coverage and suppresses stale previews from the main news list.
- Tightened diagnostics filtering to reduce packet/previous-version noise and show one diagnostic row per source item.
- Added a filter so AgendaCenter utility links like `Notify Me` and `RSS` are no longer discovered on future runs.
- Tightened meeting-status derivation to recognize postponed and continued meetings in addition to cancelled/completed states.
- Tightened publication rules so weak/generic low-confidence artifacts do not become public preview stories as easily.
- Tightened calendar suppression so postponed and continued meetings are excluded from public event listings.
- Added stronger status-precedence handling during meeting normalization so high-signal cancelled/postponed artifacts are not overwritten by later weaker artifacts.
- Normalized meeting-location strings more aggressively so public output no longer shows artifacts like `Multi -Service`.
- Refactored `publish.py` so stories and calendar events now sync existing meeting records in place instead of skipping them, allowing amended/revised meetings to update already-published public content on later runs.
- Added story content-signature tracking in `source_basis_json`, so unchanged records can be skipped on later sync runs and amended stories can carry an explicit update note when the rendered public copy materially changes.
- Added shared public styling for `story-update` banners and inline `story-note` explainer text on story pages.
- Deployed the PHP site, worker, and protected directories to Freehostia.
- Installed Python dependencies into a site-local Python user base on Freehostia.
- Added `.htaccess` rules to force HTTPS and the `www` host.
- Uploaded a non-tracked production `config.local.php` on the host.
- Removed temporary production admin and migration helper scripts after the rebuild was complete.

## Key files/entry points
- `C:\codex\newsroom\CODEX_CONTEXT.md`
- `C:\codex\newsroom\V1_BLUEPRINT.md`
- `C:\codex\newsroom\IMPLEMENTATION_ROADMAP.md`
- `C:\codex\newsroom\README.md`
- `C:\codex\newsroom\db\migrations\001_initial_schema.sql`
- `C:\codex\newsroom\db\migrations\002_generation_run_metrics.sql`
- `C:\codex\newsroom\db\migrations\003_meeting_first_model.sql`
- `C:\codex\newsroom\db\seeds\001_sources.sql`
- `C:\codex\newsroom\web\bootstrap.php`
- `C:\codex\newsroom\web\config.local.example.php`
- `C:\codex\newsroom\web\lib\content.php`
- `C:\codex\newsroom\web\public\index.php`
- `C:\codex\newsroom\web\public\story.php`
- `C:\codex\newsroom\web\public\calendar.php`
- `C:\codex\newsroom\web\public\status.php`
- `C:\codex\newsroom\web\public\.htaccess`
- `C:\codex\newsroom\worker\scripts\run_daily.py`
- `C:\codex\newsroom\worker\newsroom\pipeline.py`
- `C:\codex\newsroom\worker\newsroom\sources.py`
- `C:\codex\newsroom\worker\newsroom\documents.py`
- `C:\codex\newsroom\worker\newsroom\extract.py`
- `C:\codex\newsroom\worker\newsroom\meetings.py`
- `C:\codex\newsroom\worker\newsroom\artifacts.py`
- `C:\codex\newsroom\worker\newsroom\modeling.py`
- `C:\codex\newsroom\worker\newsroom\publish.py`
- `C:\codex\newsroom\examples\`

## Deployment/runtime status
- GitHub repo: `https://github.com/brianjcook/newsroom`
- Production site: `https://www.warehamtimes.com`
- Production MySQL database: `bricoo10_newsroom` on host `localhost`
- Freehostia SSH works intermittently; FTPS is the more reliable deployment path.
- Freehostia host runtime confirmed `python3` at `3.6.8`; worker code is compatible.
- PHP web app is deployed and publicly reachable.
- Production schema, seeds, and meeting-first migration are applied.
- Worker dependencies are installed on-host in a site-local Python user base.
- Worker runs successfully on-host using the MySQL Unix socket.
- Story output is still deterministic/template-based and source-grounded rather than model-generated.
- Live ordering now favors imminent upcoming meeting coverage instead of the farthest-future preview.
- Current live quality is materially better than the first run. The Select Board March 17, 2026 preview now resolves to the actual agenda document, uses the correct `7:00 PM` meeting time and `Multi-Service Center, 48 Marion Road, Room 520` location, includes remote-access details, and renders agenda highlights with a source-grounded CWMP explainer. The latest quality pass also suppresses more weak previews and removes postponed/continued meetings from the public calendar. Remaining quality work is still concentrated around amended/cancelled meeting edge cases and low-confidence PDFs.
- Story sync is now diff-aware: later runs compare a content signature for each story, skip unchanged records, and add an explicit update banner when a revised source document materially changes already-published copy.
- Latest successful production run:
- `run_id`: `22`
- `items_discovered`: `368`
- `documents_fetched`: `0`
- `extractions_created`: `0`
- `meetings_normalized`: `0`
- `stories_published`: `100`
- `events_created`: `108`
- `artifacts_synced`: `0`
- `warnings`: `["No pending source items were available for fetch/extract."]`

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
- `ed62a8e` - `Deploy live pipeline to Freehostia`
- `bbd686c` - `Refactor pipeline around canonical meetings`
- `bb6fb54` - `Tune meeting enrichment and artifact ranking`
- `a6ba2d2` - `Resolve agenda wrappers to real source documents`
- `809e569` - `Tighten publication quality rules`
- `544e5c9` - `Sync amended stories and events in place`

## Next priority tasks
- Reduce duplicate/overbroad meeting normalization so canonical meeting counts are cleaner.
- Improve handling of amended, revised, cancelled, and postponed agenda items, especially richer amendment framing so stories can explain what changed instead of only showing a generic update banner.
- Improve low-confidence PDF extraction handling and related publish rules.
- Decide whether low-confidence published items like the January 13, 2025 Special Town Meeting agenda should be suppressed or manually curated.
- Improve agenda-item summarization so lines truncated by PDF extraction are rewritten into clearer plain-language bullets.
- Expand diagnostics into a more useful editorial/ops view instead of raw warnings.
- Decide on and implement a repeatable on-host trigger, preferably cron-based rather than ad hoc admin endpoints.
- Move public URLs from query-parameter patterns toward descriptive path-based routing.
- Improve generated headlines, summaries, and meeting/location normalization against live Wareham examples.
- Add governing-body enrichment from the `Boards and Committees` directory and body detail pages.
- Later, replace or augment deterministic story generation with a constrained model-backed drafting step.

## Resume prompt for a brand-new Codex session
Read `C:\codex\newsroom\CODEX_CONTEXT.md` first, then `C:\codex\newsroom\V1_BLUEPRINT.md`, then `C:\codex\newsroom\IMPLEMENTATION_ROADMAP.md`. This project is a live Wareham, Massachusetts local-news site with a deployed PHP frontend on Freehostia and a deployed Python 3.6-compatible worker. The system is now using a meeting-first model: AgendaCenter discovery captures governing-body/date/posting metadata, wrapper `ViewFile/Agenda/...` URLs are resolved to their real `ViewFile/Item/...` documents, canonical meetings are keyed by governing body/date, sibling agenda/minutes/packet artifacts are synced onto those meetings, and stories/calendar events publish from primary artifacts. Production run `#22` completed successfully after the publisher was made diff-aware: existing stories now store a content signature, unchanged records are skipped on later syncs, and materially changed amended stories can receive an explicit update banner instead of silently rewriting copy. The main remaining work is quality tuning: add richer amendment/change-summary language, improve low-confidence PDF handling, clean up diagnostics, strengthen agenda-item summarization, and then move on to cleaner path-based URL routing.
