# Product Note — Coach Lead Triage Tool

**Submitted by:** Aakansha  
**Date:** 26 Oct 2026  
**Assignment:** Absolute Science — Coach Lead Take-Home

---

## The Problem

Coaches reply fast to people who message. The problem is the people who don't message — or whose messages slip through because they look fine on the surface. A coach lead reviewing 40 threads on Monday morning has no reliable way to know:

- Which customers are medically at risk right now
- Which threads have a question that has gone unanswered for 3 days (and looks "replied" because a broadcast blast was sent)
- Who is about to churn quietly vs. who has a complaint that just needs acknowledgment

The noise-to-signal ratio is terrible. There are 300+ messages in this window. The ones that matter most take the longest to find.

---

## What I Built

A Python script (`triage.py`) that reads the three CSVs and produces:

1. **`triage.csv`** — 40 customers ranked P0→P3 with flag type, reason, hours unanswered, and last message excerpt
2. **`digest.txt`** — Monday morning brief a coach lead can scan in 2 minutes

The triage logic has two layers:

**Layer 1 — Structural signals** (computed from data):
- Hours since last customer message, stratified by whether coach replied (non-broadcast only — the Oct 9 and Oct 16 blasts are explicitly excluded)
- Whether the last message is a "conversational close" (emoji, "Ok", "Thanks") vs. an open question or complaint
- Keyword pattern matching for safety (mental health, medication, fever, storage), churn, and clinical risk in coach messages

**Layer 2 — Manual overrides** (judgment calls requiring reading threads):
- Shreya's mental health signal was caught by keyword but flagged as P0 *because the coach reply was inadequate* — this requires a human to read both sides of the exchange
- Kavita got a "will check" promise that was never delivered — the auto-rule sees `coach_replied=True`; the override overrides that
- Rahul's P1 flag is on the *coach's* message, not the customer's — detecting unauthorized dose advice requires a different scan direction
- Neha's `coach_replied=True` (the hydration nudge on Oct 16 was technically after her Oct 14 message), but it ignored her actual question — flagged P1 via override

The split between auto-rules and overrides is intentional: it makes the reasoning auditable and correctable.

---

## Assumptions

1. **Reference time is Monday 19 Oct 2026 09:00 IST** — last data point is Sat 18 Oct. "Monday morning" is the next business day.
2. **Broadcast blasts don't count as coach replies.** Two blasts detected by text fingerprint: the Oct 9 dose-review feature announcement and the Oct 16 protein-nudge nudge. Both were sent at identical timestamps to 30+ threads.
3. **Farhan Qureshi is a real customer.** His WA-141 thread contains 4 messages; he's not in customers.csv. Treated as an active medicated customer (CRM data gap, not a test record).
4. **"Ok" / emoji / short affirmations to a coach message** don't require a reply — filtered from the "unanswered >48h" rule. Longer closing messages ("Done thanks", "Ok noted") still slip through at present — a known limitation.
5. **Medication stored outside refrigerator is presumed compromised** — semaglutide requires 2–8°C; 2 days at room temp is clinically significant.
6. **C10 is genuinely missing** from the data (gap in customer IDs between C09 and C11). Not treated as a data error to investigate — just noted.
7. **Mental health language is interpreted conservatively.** "Some days I wonder what's even the point" is ambiguous — it could be mundane or could signal ideation. I flagged it P0 and noted the ambiguity. Over-escalation of mental health signals is preferable to under-escalation in a healthcare context.

---

## Self-Evaluation

**What worked:**
- The two-layer design (auto-rules + overrides) means the script catches the obvious cases fast and documents the nuanced ones explicitly. A new coach lead can see *why* each customer is flagged, not just *that* they are.
- Stripping broadcasts before computing "coach replied" is the most impactful single fix — without it, every thread looks like it was attended to on Oct 9 and Oct 16.
- P0 cases are genuinely P0: pregnancy on GLP-1, possible overdose, mental health signal, fever with drug interaction query, compromised medication. I'm confident a clinician would agree with all five.

**What I'd improve with more time:**
- **Sentiment-aware "is this closed?" detection.** The current regex misses two-word closers like "Ok noted" and "Done thanks." A simple classifier (or even a bag-of-words model) trained on coach feedback would reduce false positives in P2.
- **Track the *specific unanswered question*, not just hours since last message.** Currently Kavita shows `coach_replied=True` because the coach *did* reply — but with a holding message. A Q&A extraction step (even keyword-based: does the thread contain a "?" that has no substantive answer after it?) would catch this more reliably.
- **Time-of-day weighting.** Meera's pregnancy message came at 11:41 PM on a Saturday. That's 33 hours unanswered by Monday morning, but it should be P0 regardless — the clock should start from "when a human could realistically have seen it," not from the message timestamp.
- **Churn risk scoring.** Right now "thinking of stopping" is a binary flag. A simple scoring model weighting plan value, weeks on programme, and message sentiment would help the coach lead prioritize which P2 churn risks to call first.
- **Link to chat context.** The digest shows a truncated last message. The actionable version would deep-link directly to the relevant thread in whatever tool coaches use.

---

## AI Log

| Step | Tool used | How I used it | What it contributed |
|------|-----------|---------------|---------------------|
| Data exploration | Claude Code (claude-sonnet-4-6) | Read all 3 CSVs, asked Claude to identify notable patterns across the 302 messages | Identified the Oct 9 + Oct 16 broadcast blasts, the Shreya mental health thread, Ananya's overdose concern, Meera's pregnancy, and the Kavita/Sunita medication safety cases |
| Triage logic design | Claude (conversation) | Described the problem; worked through what signals matter clinically (safety > medication > churn > engagement) and which are detectable automatically vs. which require judgment | Helped articulate the two-layer design: auto-rules for structural signals, manual overrides for cases requiring reading both sides of a conversation |
| Python script | Claude Code | Wrote the first draft of `triage.py`; I reviewed, corrected the broadcast exclusion logic, and added the conversational-close filter after reviewing false positives in the first output run | First-pass code generation; I caught and fixed the false positives before finalising |
| Product note | Claude (conversation) | Used as a thinking partner to stress-test the assumptions (e.g., "is 'what's even the point' always a red flag?") | Helped me articulate the conservative-over-escalation principle for mental health signals |

All final judgments — which cases are P0, whether a coach reply was adequate, what the action should be — were mine, not the model's. The model is fast at finding and organising; the clinical and operational judgment is what I'm bringing.
