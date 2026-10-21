# Publisher review

The publisher queue is available at `/desk/reviews` or `/editorial-reviews.php`, and from the news desk navigation. Use the existing editorial login. If editorial credentials are missing, access fails closed.

## Make a decision

1. Open a queued story or enter its story number.
2. Read the headline, deck, summary, byline, rendered story preview and source citations. The stored text and HTML are also available for inspection.
3. Choose Keep on hold, Withdraw story, or Approve and publish this version. A reason is required for a hold or withdrawal.

Approval applies only to the fingerprinted story revision and citation set. A newer publisher decision invalidates older browser forms even when the text is unchanged. The decision history records the actor, UTC timestamp, reason and revision hash.

Held and withdrawn stories remain protected during automatic regeneration. Existing manually unpublished stories are not automatically revived. Material changes to approved generated stories are saved as a new held draft. Manual opinion edits are saved as drafts and require a fresh queue decision. Reviewed story pages omit independently regenerated meeting metadata and contextual panels; the reviewed article body and verified citations remain the publication record.

The first sensitivity screen is conservative pattern-based triage of generated copy and source text. It routes suspected allegations, crime, litigation, personnel/privacy issues and other configured indicators to review. It is not a comprehensive legal assessment. Expansion to a judgment-based newsroom editor remains separate work.

Held drafts are preserved while awaiting a decision. If their underlying source changes again, they are not silently replaced; approving the displayed version can therefore be followed by a new held revision on the next worker run. Check the cited source before approval.

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
