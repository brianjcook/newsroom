# Publisher review

The publisher queue is available at `/desk/reviews` or `/editorial-reviews.php`, and from the news desk navigation. Use the existing editorial login. If editorial credentials are missing, access fails closed.

## Make a decision

1. Open a queued story or enter its story number.
2. Read the headline, deck, summary, byline, rendered story preview and source citations. Sources and additional details expand when needed.
3. Choose Publish, Keep on hold, or Do not publish. Notes are optional; a short default reason is recorded when no note is entered. After a decision, the page returns to the queue.

Approval applies only to the fingerprinted story revision and citation set. A newer publisher decision invalidates older browser forms even when the text is unchanged. The decision history records the actor, UTC timestamp, reason and revision hash internally; the interface keeps this technical identifier out of the main view.

Held and withdrawn stories remain protected during automatic regeneration. Existing manually unpublished stories are not automatically revived. Material changes to approved generated stories are saved as a new held draft. Manual opinion edits are saved as drafts and require a fresh queue decision. Reviewed story pages omit independently regenerated meeting metadata and contextual panels; the reviewed article body and verified citations remain the publication record.

The first sensitivity screen is conservative pattern-based triage of generated copy and source text. It routes suspected allegations, crime, litigation, personnel/privacy issues and other configured indicators to review. It is not a comprehensive legal assessment. Expansion to a judgment-based newsroom editor remains separate work.

Held drafts are preserved while awaiting a decision. If their underlying source changes again, they are not silently replaced; approving the displayed version can therefore be followed by a new held revision on the next worker run. Check the cited source before approval.

## Queue and reminders

The default list contains outstanding review decisions. Other drafts and declined stories have separate views, so resolved withdrawals do not clutter the daily queue. Sources, optional notes and prior decisions are expandable.

A daily morning reminder in ChatGPT links to the queue. It does not inspect the private queue or assert that stories are waiting. Authenticated, event-based digest delivery remains separate work.

## Technical contract

- Migration 015 and the runtime initializers create `publication_reviews` with a durable state, revision and approval hashes, reason and monotonically increasing decision version. Publisher actions are recorded in `publication_review_events`.
- PHP and Python share the same SQL SHA-256 fingerprint over fourteen story fields and ordered citation digests. Citation aggregation overflow is unapprovable and fails closed.
- Worker and publisher mutations lock the story before its review row. The worker uses READ COMMITTED isolation; publisher decisions do likewise.
- Public story queries independently enforce review state and current hash, even if another writer incorrectly restores `publish_status=published`. Calendar summaries associated with held meeting stories are also excluded.
- Publisher decisions require authenticated POST requests, a session CSRF token, the exact content hash and the current decision version.
- Public dynamic responses use no-store. Historical copies retained outside the site cannot be recalled by this mechanism.
- Diagnostics at `/status` now require publisher authentication because source titles and extraction details can include unpublished material.

## Validation and deployment

Deployment runs PHP syntax checks, connection recovery regressions, Python publisher-policy tests, real MySQL policy and shared-hash tests, HTTP authentication/CSRF/stale-tab checks, and public-query checks against the full schema before upload. It verifies uploaded PHP bytes and checks the public homepage plus unauthenticated protection of the review queue.

Tests use disposable databases ending in `_test`; production credentials are used only by the existing FTPS deployment. No model API or new paid service is introduced.
