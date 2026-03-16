# Wareham Newsroom Implementation Roadmap

## Phase 0: Foundation
- Create project structure for `web`, `worker`, `docs`, and `storage`.
- Add local environment config strategy.
- Define MySQL schema and migration workflow.
- Decide how the worker writes into the shared database.

## Phase 1: Source Discovery
- Build a Wareham source registry with `AgendaCenter` as the first source.
- Fetch listing pages and persist discovered source items.
- Add hashing and duplicate detection.
- Store raw HTML snapshots for debugging.

## Phase 2: Document Fetching And Extraction
- Download linked agenda and minutes PDFs.
- Normalize HTML and PDF text extraction.
- Capture extraction confidence and warnings.
- Build a canonical `meetings` model.

## Phase 3: Story And Calendar Generation
- Define prompts and templates for:
- `meeting_preview`
- `minutes_recap`
- `civic_brief`
- `explainer`
- `official_meeting_listing`
- Store generated drafts, citations, and source-basis metadata.
- Add validation rules before auto-publish.

## Phase 4: Publishing Site
- Build masthead-driven homepage.
- Build article pages with footnotes/sidenotes.
- Build calendar and archive pages.
- Build minimal admin/status pages for run history and failed items.

## Phase 5: Automation And Operations
- Add one-command daily pipeline run.
- Add cron scheduling.
- Add logging, error reports, and rerun support.
- Add manual reprocess tools for bad extractions.

## Phase 6: Quality Pass
- Tune story structure and tone for civic reporting.
- Improve PDF handling for poor-quality files.
- Reduce duplicate or low-value stories.
- Refine typography and layout from examples.

## Decision Log

### Decided
- Geography: Wareham, Massachusetts
- Primary source: `wareham.gov`
- Priority source page: `AgendaCenter`
- Formats: HTML and PDF
- Cadence: daily
- Publish mode: auto-publish
- Storage: MySQL
- Hosting target: Freehostia Wildhoney

### Not decided yet
- Final web framework inside the PHP/MySQL publishing tier
- Whether worker runs on Freehostia cron alone or from an external machine that writes to MySQL
- Final editorial naming and brand identity
- Exact visual system and typography choices

## Immediate Next Build Task
Implement the skeleton repository structure and define the MySQL schema for:

- `sources`
- `source_items`
- `documents`
- `document_extractions`
- `meetings`
- `stories`
- `story_citations`
- `calendar_events`
- `generation_runs`
