# Wareham Newsroom V1 Blueprint

## Goal
Build an automated local-news publishing system focused on Wareham, Massachusetts that:

- reads official municipal content from `wareham.gov`
- extracts agendas, minutes, and meeting metadata from HTML and PDF sources
- generates straight civic reporting, explainers, and official meeting listings
- auto-publishes a newspaper-style website
- stores source traceability and citation links for every published story

## V1 Product Boundaries

### In scope
- Wareham, Massachusetts only
- Primary source: `https://www.wareham.gov`
- Priority entry point: `https://www.wareham.gov/AgendaCenter`
- Source formats: HTML and PDF
- Daily ingestion
- Auto-published content
- Content types:
  - meeting preview
  - minutes recap
  - civic brief
  - explainer
  - official meeting listing
- Citation footnotes or sidenotes with source links
- Print/editorial visual direction

### Out of scope
- Email ingestion
- Investigations
- Election guides
- Reader accounts or subscriptions
- Monetization features
- Broad community event ingestion beyond official meetings
- Human approval workflow in v1

## Product Principles

1. Source-grounded reporting only.
Every article must be tied to stored source documents and explicit source links.

2. No invisible synthesis.
The system should never publish claims that cannot be traced back to a specific source item or clearly labeled inference.

3. Utility over volume.
Publishing fewer accurate, consistent civic stories is better than generating many weak ones.

4. Shared-hosting compatibility.
The deployed system must fit a MySQL-based Freehostia environment without requiring persistent workers on the web host.

5. Editorial newspaper feel.
The site should feel like a small digital paper, not a generic blog or startup content feed.

## Editorial Posture Recommendation
For v1, use a restrained civic-news posture:

- factual, neutral, and concise
- emphasize who met, what was discussed, what decisions were made, and what happens next
- avoid opinionated framing
- avoid inflated prose
- allow one "why it matters" paragraph when the source clearly supports it

This gives you a stable base for automation. More voice can be added later, but auto-publishing works best when tone is disciplined.

## Recommended System Shape

### Split architecture
Use two cooperating parts:

1. Publishing app
- hosted on Freehostia
- serves article pages, section pages, calendar pages, archives, and admin utilities
- stores content in MySQL

2. Ingestion and generation worker
- runs as a scheduled process once per day
- fetches new source items
- extracts structured text and metadata
- generates stories and calendar entries
- writes results into MySQL

### Why this split
- scraping and PDF processing are operationally different from web serving
- shared hosting is not ideal for long-running or compute-heavy jobs
- generation logic can evolve without destabilizing the public site
- the web app remains simple and deployable

## Stack Recommendation

### Web publishing
- PHP 8
- MySQL with InnoDB
- server-rendered templates
- modest JavaScript only where needed

### Ingestion and generation
- Python 3
- HTTP fetching and HTML parsing
- PDF extraction and OCR-ready pipeline design
- LLM integration for drafting and structured extraction

### Scheduling
- daily cron job
- one command to run the entire pipeline

### Why not a JS-heavy full-stack app
Next.js-style stacks are possible in general but are a poor fit for low-friction deployment on this hosting target. PHP plus Python worker is the more pragmatic v1.

## Source Model

### V1 source registry
Start with a source registry table and support these source categories:

- `agenda_center_listing`
- `agenda_html`
- `agenda_pdf`
- `minutes_pdf`
- `meeting_page`

### Initial Wareham targets
- `AgendaCenter` list pages
- individual agenda entries
- linked PDF agendas
- linked PDF minutes

### Future-safe source abstraction
Every source should have:

- source type
- canonical URL
- fetch method
- parser adapter name
- active/inactive status
- polling cadence

This lets you add library, school, or board sources later without redesigning storage.

## Content Pipeline

### Daily run sequence
1. Fetch source entry pages.
2. Detect newly published or changed agenda/minutes items.
3. Download linked HTML/PDF documents.
4. Extract text and metadata.
5. Build a structured meeting record.
6. Decide which content type(s) to generate.
7. Generate article body, headline, dek, summary, and citations.
8. Generate or update calendar entries.
9. Run validation and safety checks.
10. Auto-publish validated items to the site.

### Change detection
Store a content fingerprint for each fetched page or file:

- canonical URL
- HTTP last-modified or equivalent if available
- document hash
- first-seen timestamp
- last-seen timestamp

This avoids duplicate stories and unnecessary regeneration.

### Extraction outputs
Each document extraction should produce:

- plain text
- title if detected
- meeting body/committee
- meeting date/time if detected
- document type
- agenda items or key sections if parsed
- extraction confidence
- parsing warnings

### Generation triggers

#### Meeting preview
Generate when:
- a new agenda appears for a future official meeting

#### Minutes recap
Generate when:
- approved or posted minutes appear for a prior meeting

#### Civic brief
Generate when:
- a source item is too small for a full recap but still newsworthy

#### Explainer
Generate only when:
- recurring public topics benefit from reusable context
- example: "What the Select Board does"

Explainers should be generated more cautiously and may rely on accumulated source material.

### Auto-publish guardrails
Before publication, require:

- source URL present
- source document snapshot present
- publication date present
- minimum extraction confidence
- no empty body
- no unsupported claims
- at least one citation block

If a record fails checks, mark it for manual review rather than publishing.

## Database Design

### Core tables

#### `sources`
Defines source endpoints and parser behavior.

Suggested fields:
- `id`
- `name`
- `slug`
- `source_type`
- `base_url`
- `list_url`
- `parser_key`
- `is_active`
- `poll_frequency`
- `created_at`
- `updated_at`

#### `source_items`
Represents discovered documents or listing entries.

Suggested fields:
- `id`
- `source_id`
- `external_id`
- `canonical_url`
- `title`
- `item_type`
- `published_at`
- `first_seen_at`
- `last_seen_at`
- `content_hash`
- `status`
- `raw_meta_json`

#### `documents`
Stores fetched files or HTML snapshots.

Suggested fields:
- `id`
- `source_item_id`
- `document_url`
- `document_type`
- `mime_type`
- `storage_path`
- `sha256`
- `fetched_at`
- `http_status`

#### `document_extractions`
Stores parsed text and extraction diagnostics.

Suggested fields:
- `id`
- `document_id`
- `extractor_version`
- `title`
- `body_text`
- `structured_json`
- `confidence_score`
- `warnings_json`
- `created_at`

#### `meetings`
Canonical meeting record used by both stories and calendar entries.

Suggested fields:
- `id`
- `source_item_id`
- `governing_body`
- `meeting_type`
- `meeting_date`
- `meeting_time`
- `location_name`
- `status`
- `agenda_posted_at`
- `minutes_posted_at`
- `meeting_key`

#### `stories`
Published newsroom content.

Suggested fields:
- `id`
- `meeting_id` nullable
- `story_type`
- `slug`
- `headline`
- `dek`
- `summary`
- `body_html`
- `body_text`
- `tone_profile`
- `publish_status`
- `published_at`
- `source_basis_json`
- `created_at`
- `updated_at`

#### `story_citations`
Citation blocks for footnotes/sidenotes.

Suggested fields:
- `id`
- `story_id`
- `citation_number`
- `label`
- `source_url`
- `document_id`
- `quote_text`
- `note_text`

#### `calendar_events`
Official meetings displayed in the calendar.

Suggested fields:
- `id`
- `meeting_id`
- `title`
- `starts_at`
- `ends_at`
- `location_name`
- `body_name`
- `source_url`
- `status`
- `description`
- `created_at`
- `updated_at`

#### `generation_runs`
Audit trail for each daily run.

Suggested fields:
- `id`
- `started_at`
- `finished_at`
- `run_status`
- `items_discovered`
- `stories_published`
- `events_created`
- `warnings_json`
- `errors_json`

## Publishing Model

### Primary page types
- homepage
- section page for government/civic coverage
- story page
- calendar page
- meeting archive
- source transparency page

### Homepage structure
Recommended hierarchy:

- masthead
- lead story
- latest civic briefs
- upcoming meetings
- recent minutes recaps
- explainers

### Story page structure
- headline
- dek
- publication timestamp
- source badge
- body
- footnotes/sidenotes
- "source documents" block
- related meeting or calendar links

### Calendar page structure
- upcoming official meetings
- filter by board/body
- links to agendas
- links to related coverage

## Newspaper-Style Visual Direction

### Core design cues from references
- prominent masthead
- serif-led typography
- narrow, disciplined text columns
- strong hierarchy with dek/subhead treatment
- restrained palette with occasional accent color
- editorial spacing rather than app-style padding

### Design guidance
- use one display serif for masthead and headlines
- use a readable text serif for story body
- use a compact sans only for metadata, labels, and navigation
- keep cards to a minimum
- prefer rules, columns, pull quotes, and section dividers over rounded panels

## Safety and Accuracy Rules

### Hard rules
- never invent votes, dates, attendees, or decisions
- never claim an action was approved unless the source explicitly supports that
- label uncertainty clearly
- prefer "according to the posted agenda" or "according to meeting minutes" when warranted

### Publishing checks
- reject stories that do not cite at least one source
- reject stories if meeting date could not be established
- reject stories if extraction confidence falls below threshold
- reject stories if body repeats boilerplate too heavily

## V1 Operational Constraints

### Freehostia considerations
- assume limited cron availability
- assume no persistent queue worker
- keep the publish site simple
- make the daily job idempotent
- store enough audit data to re-run safely

### Asset strategy
- store source snapshots and extracted text in an organized file path or object-style directory layout
- keep derived publication data in MySQL

## Recommended Build Order

1. Create MySQL schema and migration plan.
2. Build Wareham `AgendaCenter` source discovery.
3. Implement HTML and PDF fetch/storage.
4. Implement extraction and meeting normalization.
5. Build story generation with citations.
6. Build calendar event generation.
7. Build publishing site templates.
8. Add daily cron entry and audit logging.
9. Tune prompts and auto-publish safeguards.

## Success Criteria For V1

- detects new Wareham agenda/minutes items daily
- publishes accurate linked stories automatically
- creates official meeting listings automatically
- stores source traceability for every article
- presents content in a distinct newspaper-style site
- can run reliably on a MySQL-centered deployment model
