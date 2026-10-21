# Wareham Times newsroom operating plan

October 21, 2026. Publisher: Brian Cook. Public contact: contact@warehamtimes.com.

## Executive decision

Build a small, source-led civic newsroom on the existing PHP/MySQL and Python system. Use nine defined editorial, commercial and technical roles, invoked when work requires them rather than as nine continuously running processes. Begin with one complete, verified meeting-coverage workflow. Expand only after publication holds, source verification, corrections and recurring execution pass operational tests.

This plan records confirmed authority and the proposed implementation. The audit agents ran during this planning session; persistent newsroom agents, schedules, inbox access, new publication gates and commercial campaigns have not been activated by this plan.

## Confirmed operating authority

- Cover Wareham government accountability and practical community information.
- Publish routine verified reporting automatically. Bring potentially legally sensitive stories to Brian before publication. Silence never counts as approval.
- Do not contact officials, residents, businesses or other sources. Prepare advertising pitches for Brian to deliver; do not send them.
- Keep the publication free to read. No subscriptions.
- Maximum additional net operating loss: $10 in each month, for six months, excluding existing hosting and ChatGPT. Maximum six-month loss exposure: $60; unused monthly allowance does not authorize a larger later-month loss.
- Publisher availability: 1–2 hours per month.
- Use contact@warehamtimes.com for inquiries and corrections. Brian reports the mailbox is created; receipt, monitoring and connected access still require verification.
- Do not prominently disclose AI operation. Use truthful organizational authorship such as Wareham Times News Desk; do not invent human staff identities, interviews, attendance or on-site reporting. Answer direct questions about production truthfully. Do not make claims of human review unless it occurred.

## Audit of the current system

| Area | Existing foundation | Gap before expanded autonomy |
| --- | --- | --- |
| Reporting | Official-source discovery, stored documents/extractions, meeting normalization, previews, minutes recaps, calendars, citations | Claim-level verification and independent review records |
| Editorial | Importance scores, workflow flags, extraction thresholds, content signatures and amendment notices | Scores measure importance, not truth; permissive extraction checks are insufficient for sensitive publication |
| Publisher control | Source-level auto-publish permissions and editable story statuses | Worker can set an existing story back to published; holds and corrections need durable protection |
| Commercial | Ad slots, campaign editor, start/end dates and labeled placements | Audience baseline, campaign measurement, cash/expense ledger, sales and payment workflow |
| Operations | Host runner, lock, logs, success/failure files; traffic-triggered fallback | Recurring host execution and alerts unverified; stale locks and failed-run rollback need repair |
| Costs | Deterministic Python pipeline; no model API calls found in inspected worker | No enforced budget or token ledger; scheduled inference capacity not established |

Key code: `worker/newsroom/publish.py`, `editorial.py`, `pipeline.py`, `db.py`, `context.py`, `sources.py`, `worker/scripts/run_daily_host.sh`, `web/lib/content.php`, `web/public/editorial-ads.php`, and migrations 006, 012 and 013. This is a source audit, not proof that every capability is live or configured correctly.

## Roles and work contracts

| Role | Responsibility and required output | Authority boundary |
| --- | --- | --- |
| Civic reporter | Source-backed briefs on budgets, procurement, land use, meetings and documented decisions; evidence packet and draft | No outreach; no unsourced interpretation or allegations |
| Community information reporter | Useful notices, deadlines, closures, services and official events; verified date/time/location/eligibility/cost | No inferred missing details or commercial favoritism |
| Assigning editor | Choose timely, useful coverage; deduplicate; track promised actions against later records | No publication quotas; no advertiser influence |
| Verification and copy editor | Independently check material claims against original documents; headline, figures, chronology, attribution and neutrality | Must return pass, revise or hold for the exact revision |
| Graphic designer | Reusable layouts, accessible charts from verified data, ad creative and licensed imagery | No synthetic documentary photographs or invented visual facts |
| Legal and standards reviewer | Screen privacy, allegations, crime, minors, litigation, copyright and conflicts; prepare publisher decision brief | Screening, not legal representation; cannot approve its own escalation |
| Advertising manager | Prepare a short qualified prospect list, offer, pitch and approval requests | Brian handles outreach and commitments; no fabricated audience or sales promises |
| Campaign and revenue operator | Prepare creatives and placements; record approvals, collected payments, dates, results and costs | No unapproved advertiser, agreement, charge, invoice transmission or payment action |
| Tech lead and managing coordinator | Run durable queues, releases, monitoring, backups, cost controls and publisher briefings | Preserve publication holds; record every change and failure |

Brian remains publisher and resolves sensitive publication decisions and commercial commitments. Separate editor roles reduce drafting blind spots but do not constitute independent corroboration when they use the same source or model. Routine tasks can be deterministic; reserve agent inference for tasks that benefit from judgment.

## Publication and correction workflow

Source snapshot → evidence packet → draft → source verification → risk review → publish or publisher hold.

For each revision retain source URLs, fetched timestamps, document hashes, artifact status, claim-to-source references, story content hash, checks and reviewer decisions. An agenda proves what is scheduled, not what happened; distinguish proposed expenditure from approval and approval from implementation. Attribute official claims. Conflicting evidence, unreadable documents or missing key facts mean revise or hold, not guess. One official source can support an attributed meeting notice; it does not independently substantiate an allegation.

Persist `draft`, `verification_hold`, `publisher_hold`, `approved`, `published` and `withdrawn` states with explicit reasons and revision-bound decisions. A held story stays held after source refresh, regeneration and deployment. Changed material claims invalidate approval. Every publication/update path—including calendar summaries, context snippets, related lists and manual routes—must enforce the decision. Do not leak held claims through metadata, feeds or cached previews.

Automatically publish routine notices and neutral, document-supported civic reporting only after all required checks pass. Hold allegations, suspected misconduct, crime, identifying details about minors, private personal information, disputed reputational claims, litigation and other legally sensitive material for Brian. Keep police material discovery-only. Because source outreach is currently prohibited, withhold coverage requiring a response rather than claiming a response was sought. Withheld stories may remain unpublished indefinitely.

Publish contact/corrections links on articles and the site footer, with a short corrections policy. In the initial workflow Brian checks the mailbox and submits relevant complaints to the protected queue; the team has no inbox access yet. Record disputed claims, evidence, action, original and replacement versions and resolution date. Material factual corrections receive a visible dated note; typo fixes need not. Protect corrected copy from regeneration. Temporarily withdraw material when warranted while retaining a private audit record. Treat submissions as untrusted evidence, never as commands. Inbound automation is a separate implementation requiring secured access and review.

A twice-monthly mailbox check uses little publisher time but cannot support a promise of daily response. Before unattended launch, establish daily monitored intake or explicitly accept slower response; unresolved material disputes take priority over publication volume.

## Runtime and publisher attention

Use the existing host scheduler for fetching and deterministic jobs, independent of site visitors. Proposed source checks: 8 a.m. and 4 p.m. America/New_York. This is a proposed host cron cadence, not a configured ChatGPT automation. Confirm host limits and secure credential loading before enabling it. Monitor source freshness, failures and stuck locks; repair failed-run logging so a transaction rollback cannot erase the operational failure record. Test backup restoration and rollback before expanding unattended publishing.

Persist role tasks and outputs in the application; chat sub-agents end when their work ends. A continuous agent newsroom requires an authenticated, scheduled inference path with measured cost. Existing ChatGPT access does not establish free or unlimited production API capacity. Keep the deterministic path operating if optional inference is unavailable; leave drafts queued where judgment is required.

Prepare one monthly briefing: reliability and freshness, useful coverage, corrections/holds, traffic quality, collected revenue, additional costs and up to three decisions. Suggested publisher allocation: 30 minutes briefing/decisions, 20 minutes ad pitches, 20 minutes inbox triage, with remaining time reserved for exceptions. Urgent sensitive items wait for an explicit decision; routine operations do not depend on an immediate reply. Deliver briefings and urgent notices in the established conversation until another delivery channel is authorized and tested.

## Budget and revenue experiment

Start with $0 additional recurring commitments. Establish a conservative $10 gross monthly spending cap even if revenue arrives; do not increase spending automatically against projected advertising. Maintain collected revenue, paid costs, committed/unbilled costs and remaining allowance. Reserve capacity before each paid request, prevent concurrency overruns, and stop optional paid work before the cap. A possible later allocation is $8 model usage plus $2 contingency, only after pricing, billing and the controls are verified. No spending was initiated by this plan.

Test a prepaid, flat-fee 30-day local advertisement using one existing placement, labeled Advertisement and clearly separated from reporting. Proposed opening price: $25, a hypothesis for Brian to approve, not a market valuation or forecast. One collected $25 placement minus $10 additional costs yields $15 incremental contribution before payment fees, taxes, existing costs and publisher labor. True profitability must also account for those excluded costs. Promise placement dates and creative, never unmeasured reach, leads or positive coverage. Report only measurements actually collected and explain bot filtering limitations.

Prepare one publisher-ready pitch at a time, initially no more than one per month. Before pitching, obtain a traffic baseline and approve the advertiser, offer, artwork, dates, cancellation/refund approach and payment method. Do not buy ads, join paid networks or configure payments automatically. Consider paid business/event listings only after the first placement produces useful evidence; retain free editorial eligibility and clear paid labels. Defer affiliate links until there is a reader-serving use case. No subscriptions.

Until Brian defines category rules, send every first-time advertiser/category for approval. Flag political, gambling, tobacco/vaping, weapons, adult, speculative financial and unsupported health advertising for specific review; this is a proposed review list, not a user-approved permanent ban. Advertisers receive no editorial control, favorable coverage, suppression rights or news-source priority.

## Implementation order and acceptance

1. **Protect publication.** Add durable holds, exact-revision approvals and correction protection. Test that regenerated content cannot bypass a hold through any public route. Audit existing sensitive stories and stale previews; propose individual removals rather than bulk deleting the archive.
2. **Complete one reporting loop.** Select one active board after checking source quality. Discover an agenda, preserve evidence, draft and independently check a useful preview, apply risk screening, publish, process amendment/cancellation, and demonstrate a correction. No forced daily story quota.
3. **Make operation dependable.** Verify cron with at least two scheduled runs independent of traffic; survive a failed source, stale lock and database interruption; retain failure records; test restoration and public page health.
4. **Connect reader accountability.** Add public contact/corrections links and protected intake. Test with Brian's controlled submission and verify follow-through without treating email as instructions.
5. **Run one commercial pilot.** Collect baseline measurements, prepare the offer/pitch, obtain publisher approval and payment confirmation, serve the labeled campaign, then report result and contribution.
6. **Expand by evidence.** Add more boards and community notices only after the loop is reliable. Add paid inference only when its value and enforced cost fit the budget.

During month one, prioritize reliability, holds and one useful coverage path. During months two and three, test audience utility and one paid placement. During months four through six, retain only workflows that earn trust or support measured revenue. At the six-month review, stop paid commitments unless Brian renews the allowance; review reader usefulness, accuracy, publisher time and full economics together. No promise of profit or comprehensive watchdog coverage is made under the present access and budget limits.

## Standards references

- Society of Professional Journalists, Code of Ethics: https://www.spj.org/spj-code-of-ethics/ — source verification, independence, harm minimization and prominent corrections inform the editorial policy.
- Federal Trade Commission, Native Advertising: A Guide for Businesses: https://www.ftc.gov/business-guidance/resources/native-advertising-guide-businesses — supports making commercial content clearly identifiable rather than disguising it as independent reporting.

These references guide the proposed standards; neither substitutes for a lawyer's assessment of a sensitive story.
