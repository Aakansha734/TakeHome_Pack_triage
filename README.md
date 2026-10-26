# Absolute Science — Coach Lead Triage

**Submitted by:** Aakansha  
**Assignment:** Take-home — Monday morning triage digest

## What this is

A script that reads three CSVs of customer + WhatsApp/app message data and produces a ranked triage list for coach leads, telling them who needs a human today and why.

## Run it

```bash
# From this directory (where data/ folder is)
python triage.py
```

Outputs:
- `triage.csv` — 40 customers ranked P0→P3, one row each
- `digest.txt` — Monday morning brief (human-readable, ~140 lines)

Requires Python 3.8+, no external dependencies (stdlib only).

## Files

| File | Description |
|------|-------------|
| `triage.py` | Main script — signal detection + priority assignment + output |
| `triage.csv` | Pre-generated output (Monday 19 Oct 2026 09:00 IST reference) |
| `digest.txt` | Pre-generated digest |
| `product_note.md` | Product note · assumptions · self-evaluation · AI log |
| `data/customers.csv` | 38 customers (C10 missing — data gap noted) |
| `data/messages.csv` | 302 messages, Oct 5–18 2026 |
| `data/groups.csv` | 54 thread mappings (WA + app) |

## Priority tiers

| Tier | Count | Meaning |
|------|-------|---------|
| P0 | 5 | Safety or medical risk — call before anything else |
| P1 | 5 | Urgent operational/clinical issue — resolve today |
| P2 | 16 | Needs attention this week — churn, tech, disengaged |
| P3 | 14 | Active and responsive — routine monitoring |

## Key design decisions

- **Broadcast blasts excluded from "coach replied" check.** Two mass-sends (Oct 9 and Oct 16) are excluded — otherwise every thread looks attended to.
- **Manual overrides for cases that require reading both sides of a thread** (e.g., Shreya's mental health signal was caught by keyword but flagged P0 because the coach reply was inadequate; Kavita's `coach_replied=True` but the promised follow-up never came).
- **Conversational closes don't trigger "unanswered" flags** — emoji-only messages and single-word closes (Ok, Thanks, Done) don't require a reply.

See `product_note.md` for full reasoning and trade-offs.
