#!/usr/bin/env python3
"""
Coach Lead Triage — Absolute Science
Monday morning digest: who needs a human today, and why.

Usage:  python triage.py
Output: triage.csv, digest.txt
Reference frame: 2026-10-19 09:00 IST (Monday after last data point, Sat 18 Oct)
"""

import csv
import re
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
DATA   = Path("data")
REF    = datetime(2026, 10, 19, 9, 0)   # Monday 09:00 — coach opens dashboard
P_ORD  = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

# Broadcast fingerprints: same text blasted to 30+ groups at identical timestamps.
# These do NOT count as coach replies — they're automated nudges, not responses.
BROADCASTS = [
    "We've introduced a new feature",          # Oct 9 dose-reminder blast
    "GLP-1 your appetite drops",               # Oct 16 protein-nudge blast
]

# ── Signal patterns (applied to customer message text only) ──────────────────

# P0: Safety — anything here → escalate to doctor/manager before anything else
SAFETY_PAT = [
    r"wonder what.{0,10}s even the point",     # possible suicidal ideation
    r"feeling really low",
    r"not interested in anything",
    r"what.{0,5}s even the point",
    r"pregnant",                               # GLP-1 contraindicated
    r"vomiting.{0,30}(times|\d)",
    r"\d+.{0,5}times.{0,20}vomit",
    r"can.t keep.{0,10}water",
    r"hospital",
    r"4x the dose|took 4x|four times",
    r"102",                                    # high fever
    r"fridge ke bahar",                        # pen storage failure (Hindi)
    r"cool pack.{0,20}melt|melt.{0,20}cool",
    r"(box|package).{0,30}warm",
]

# P1: Medication / supply risk
MED_PAT = [
    r"only (one|\d) (pen|dose)",
    r"dose is due",
    r"pen left",
    r"confirming that.{0,10}s fine",           # self-admin uncertainty
    r"fridge ke bahar",
    r"cool pack",
    r"(box|package).{0,30}warm|warm.{0,30}(box|package)",
]

# P2: Churn / frustration
CHURN_PAT = [
    r"cancel|refund",
    r"thinking of stopping",
    r"any human here",
    r"texting a bot",
    r"hello\?+",                               # unanswered ping
    r"still no update",
    r"nothing is changing",
    r"not what i expected",
]

# Coach-message risk: unauthorized clinical advice
COACH_RISK_PAT = [
    r"just turn the dial",                     # self-dose-adjustment instruction
    r"you can go to 1mg",
]

# Customer messages that close a conversation — don't flag as "unanswered" unless
# there's a separate signal. Catches: emoji, Ok, Thanks, Done, Noted, etc.
CLOSE_RE = re.compile(
    r"^[\U0001F300-\U0001FFFF👍🙏✅💪🎉😊🌸]+$"   # emoji-only
    r"|^(ok|okay|thanks|thank you|done|noted|noted 👍|sure|great|perfect|"
    r"sounds good|got it|understood|all good|will do|yes|yep|👍|🙏|✅)[\s!.,]*$",
    re.I | re.UNICODE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load(name: str):
    return list(csv.DictReader((DATA / name).open(encoding="utf-8")))

def is_broadcast(text: str) -> bool:
    return any(b.lower() in text.lower() for b in BROADCASTS)

def hits(text: str, patterns: list) -> list:
    t = text.lower()
    return [p for p in patterns if re.search(p, t)]

def parse_dt(s: str) -> datetime:
    return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M")

def hours_gap(dt: datetime) -> float:
    return (REF - dt).total_seconds() / 3600

def days_gap(dt: datetime) -> int:
    return (REF - dt).days


# ── Load & index ──────────────────────────────────────────────────────────────

customers = {c["customer_id"]: c for c in load("customers.csv")}
messages  = sorted(load("messages.csv"), key=lambda m: m["timestamp_ist"])

by_thread: dict[str, list] = defaultdict(list)
for m in messages:
    if m["sender_role"] != "system":
        by_thread[m["thread_id"]].append(m)


# ── Per-customer analysis ─────────────────────────────────────────────────────

def analyse(cid: str, c: dict) -> dict:
    # Collect all threads for this customer
    threads = []
    wa = c.get("whatsapp_group_id", "").strip()
    if wa and wa in by_thread:
        threads.append(wa)
    app = f"APP-{cid}"
    if app in by_thread:
        threads.append(app)

    all_msgs = []
    for t in threads:
        all_msgs.extend(by_thread[t])
    all_msgs.sort(key=lambda m: m["timestamp_ist"])

    cust_msgs  = [m for m in all_msgs if m["sender_role"] == "customer"]
    coach_msgs = [m for m in all_msgs
                  if m["sender_role"] == "coach" and not is_broadcast(m["text"])]

    if not cust_msgs:
        purchase_dt = datetime.strptime(c["purchase_date"], "%Y-%m-%d")
        return dict(
            cid=cid, name=c["name"], coach=c["assigned_coach"],
            plan=c["plan"], med=c["medication"],
            last_cust_dt=None,
            days_silent=days_gap(purchase_dt),
            coach_replied=None, hours_open=None,
            last_text="(no customer messages)",
            safety=[], med_risk=[], churn=[], coach_risk=[],
            never_messaged=True,
        )

    lc    = cust_msgs[-1]
    lc_dt = parse_dt(lc["timestamp_ist"])

    # Coach replied = any non-broadcast coach message AFTER last customer message
    replied_after = [m for m in coach_msgs if parse_dt(m["timestamp_ist"]) > lc_dt]
    coach_replied = len(replied_after) > 0
    hours_open    = 0.0 if coach_replied else hours_gap(lc_dt)

    # Signal scan across ALL customer messages (not just the last)
    safety   = [m for m in cust_msgs if hits(m["text"], SAFETY_PAT)]
    med_risk = [m for m in cust_msgs if hits(m["text"], MED_PAT)]
    churn    = [m for m in cust_msgs if hits(m["text"], CHURN_PAT)]
    cr       = [m for m in coach_msgs if hits(m["text"], COACH_RISK_PAT)]

    return dict(
        cid=cid, name=c["name"], coach=c["assigned_coach"],
        plan=c["plan"], med=c["medication"],
        last_cust_dt=lc_dt,
        days_silent=days_gap(lc_dt),
        coach_replied=coach_replied,
        hours_open=round(hours_open, 1),
        last_text=lc["text"][:120],
        safety=safety, med_risk=med_risk, churn=churn, coach_risk=cr,
        never_messaged=False,
    )


records = {cid: analyse(cid, c) for cid, c in customers.items()}

# Farhan Qureshi — in messages (WA-141) but missing from customers.csv (CRM data gap)
fa_msgs   = sorted([m for m in messages if m["thread_id"] == "WA-141"],
                   key=lambda m: m["timestamp_ist"])
fa_cust   = [m for m in fa_msgs if m["sender_role"] == "customer"]
fa_coach  = [m for m in fa_msgs if m["sender_role"] == "coach" and not is_broadcast(m["text"])]
if fa_cust:
    lc = fa_cust[-1]; lc_dt = parse_dt(lc["timestamp_ist"])
    replied = any(parse_dt(m["timestamp_ist"]) > lc_dt for m in fa_coach)
    records["EXT"] = dict(
        cid="EXT", name="Farhan Qureshi", coach="Riya",
        plan="Medicated (not in CRM)", med="Semaglutide",
        last_cust_dt=lc_dt, days_silent=days_gap(lc_dt),
        coach_replied=replied,
        hours_open=0.0 if replied else round(hours_gap(lc_dt), 1),
        last_text=lc["text"][:120],
        safety=[], med_risk=[lc], churn=[], coach_risk=[],
        never_messaged=False,
    )


# ── Priority assignment ───────────────────────────────────────────────────────
#
# Manual overrides for cases that require reading the conversation thread.
# Keyword patterns catch the surface signal; overrides encode the clinical judgment.
#
OVERRIDES: dict[str, tuple] = {
    #  cid        priority   flag_type                           action_note
    "C01": ("P0", "safety:overdose_concern",
            "4x dose for 3 weeks → hospitalised. Dose question open 49 h. Call today."),
    "C02": ("P0", "safety:pregnancy_on_GLP1",
            "Pregnant; took injection Thu. GLP-1 contraindicated. Escalate to doctor now."),
    "C04": ("P0", "safety:mental_health_signal",
            '"Some days I wonder what\'s even the point" — coach reply was lifestyle tips only. Call.'),
    "C11": ("P0", "safety:fever_drug_interaction",
            "102°F fever; asked Dolo 650 interaction; coach promised 'will check' but never did (71 h)."),
    "C12": ("P0", "safety:compromised_medication",
            "Pen outside fridge 2 days; dose due Mon (today). Do NOT use — replacement needed urgently."),
    "C06": ("P1", "operational:medication_supply+anger",
            "1 dose left since Oct 8, due ~Oct 15; 11-day silence on kit ETA. 'Is there any human here'."),
    "C05": ("P1", "medical:severe_side_effects",
            "Vomiting 6-7× — can't retain fluids — dizzy. ORS advice insufficient; monitor or escalate."),
    "C03": ("P1", "medical:compromised_first_dose",
            "Warm package (melted coolpack), first-ever dose. May have taken degraded med Sat night."),
    "EXT": ("P1", "operational:travel_medication_crisis",
            "Flight to Dubai was Fri 17 Oct; unanswered follow-up. May have flown without medication. Not in CRM."),
    "C13": ("P1", "clinical_risk:unauthorized_dose_advice",
            "Coach told customer 'just turn the dial to 1mg' — dose changes need doctor approval. Coach debrief needed."),
    "C15": ("P2", "churn:disengaged",
            '"Thinking of stopping after this month. Paying so much and nothing is changing." — 63 h unanswered.'),
    "C16": ("P2", "churn:refund_request",
            '"Want to cancel and get refund. Not what I expected." — 47 h unanswered.'),
    "C14": ("P2", "clinical:plateau_unanswered",
            "3-week weight plateau at 1 mg despite clean diet and 8k steps. Needs doctor input."),
    "C22": ("P2", "operational:delivery_dispute",
            '"Tracking says delivered but I haven\'t received anything." — 7 days, medication not received.'),
    "C23": ("P2", "product:complaint_unanswered",
            '"Shake tastes awful, feel like throwing up." — 4 days unanswered. Flavour swap + reassurance needed.'),
    "C24": ("P2", "operational:travel_medication_query",
            "Going to Goa Thu; asked about pen in check-in / ice pack. Unanswered — trip may be tomorrow."),
    "C25": ("P2", "technical:app_otp_broken",
            "App OTP broken 2+ days; can't log meals. Tech ticket needed."),
    "C26": ("P2", "operational:consult_reschedule_pending",
            "Consult reschedule request (Mon → Wed) pending confirmation. Consult is today."),
    "C34": ("P2", "engagement:silent_on_medication",
            "No response to Oct 12 check-in. Silent throughout data window. On Sema 1 mg."),
    "C37": ("P2", "engagement:silent_on_medication",
            "No response to Oct 12 check-in. Silent throughout data window. On Sema 0.5 mg."),
    "C38": ("P2", "engagement:silent_on_medication",
            "No response to Oct 12 check-in. Silent throughout data window. On Sema 0.5 mg."),
    "C39": ("P2", "engagement:silent",
            "No response to Oct 12 check-in. Silent throughout data window. Lifestyle plan."),
    "C08": ("P2", "engagement:never_onboarded",
            "Purchased Oct 15. No WhatsApp group set up. No messages. Needs onboarding call."),
}


def assign(r: dict) -> tuple:
    cid = r["cid"]
    if cid in OVERRIDES:
        return OVERRIDES[cid]

    # Auto-rules for remaining customers (all should end up P3 if active)
    if r["safety"]:
        return ("P0", "safety:auto", r["safety"][0]["text"][:80])
    if r["coach_risk"]:
        return ("P1", "clinical_risk:coach_advice", r["coach_risk"][0]["text"][:80])
    if r["med_risk"] and not r["coach_replied"] and r["hours_open"] and r["hours_open"] > 24:
        return ("P1", "medical:unanswered_24h", r["last_text"][:80])
    if r["churn"] and not r["coach_replied"]:
        return ("P2", "churn:unanswered", r["churn"][0]["text"][:80])
    if r["never_messaged"] and r["days_silent"] > 3:
        return ("P2", "engagement:never_messaged", "No messages since purchase")
    if r["days_silent"] > 7 and not r["coach_replied"]:
        return ("P2", "engagement:silent_7d", f"Silent {r['days_silent']} days")
    # Only flag as unanswered if the last message isn't just a conversational close
    is_close = bool(CLOSE_RE.match(r["last_text"].strip()))
    if not r["coach_replied"] and r["hours_open"] and r["hours_open"] > 48 and not is_close:
        return ("P2", "operational:unanswered_48h", r["last_text"][:80])
    return ("P3", "active:no_flags", "Engaged and responsive")


# ── Build rows & sort ─────────────────────────────────────────────────────────

rows = []
for cid, r in records.items():
    pri, flag, reason = assign(r)
    dt_str = r["last_cust_dt"].strftime("%Y-%m-%d") if r["last_cust_dt"] else "—"
    rows.append({
        "rank":                  None,
        "priority":              pri,
        "customer_id":           r["cid"],
        "name":                  r["name"],
        "coach":                 r["coach"],
        "plan":                  r["plan"],
        "medication":            r["med"],
        "flag_type":             flag,
        "flag_reason":           reason,
        "last_customer_msg_date":dt_str,
        "days_since_last_msg":   r["days_silent"],
        "coach_replied_to_last": ("True" if r["coach_replied"] else
                                  "False" if r["coach_replied"] is False else "N/A"),
        "hours_unanswered":      r["hours_open"] if r["hours_open"] is not None else 0,
        "last_customer_msg":     r["last_text"],
    })

# Sort: priority tier first, then longest-unanswered within tier
rows.sort(key=lambda r: (P_ORD[r["priority"]], -float(r["hours_unanswered"])))
for i, r in enumerate(rows, 1):
    r["rank"] = i


# ── Write triage.csv ──────────────────────────────────────────────────────────

with open("triage.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

counts = {k: sum(1 for r in rows if r["priority"] == k) for k in P_ORD}
print(f"triage.csv  — {len(rows)} customers | "
      + " | ".join(f"{k}: {counts[k]}" for k in P_ORD))


# ── Write digest.txt ──────────────────────────────────────────────────────────

p0 = [r for r in rows if r["priority"] == "P0"]
p1 = [r for r in rows if r["priority"] == "P1"]
p2 = [r for r in rows if r["priority"] == "P2"]
p3 = [r for r in rows if r["priority"] == "P3"]

SEP  = "═" * 64
sep2 = "─" * 64

lines = [
    f"COACH LEAD DIGEST — MONDAY 19 OCT 2026",
    f"Reference: 09:00 IST  |  {len(rows)} active customers (incl. 1 not in CRM)",
    f"Coaches: Riya · Karan · Sneha   |  Generated by triage.py",
    "",
    SEP,
    f"P0 — ACT IMMEDIATELY ({len(p0)})  ·  Safety & medical risk",
    SEP,
]
for r in p0:
    lines += [
        "",
        f"[{r['rank']}] {r['name'].upper()}  ·  {r['customer_id']}  ·  {r['coach']}",
        f"    {r['plan']}  ·  {r['medication']}",
        f"    FLAG: {r['flag_type']}",
        f"    {r['flag_reason']}",
        f"    Last msg ({r['last_customer_msg_date']}): \"{r['last_customer_msg']}\"",
    ]

lines += [
    "",
    SEP,
    f"P1 — URGENT TODAY ({len(p1)})  ·  High-impact unresolved",
    SEP,
]
for r in p1:
    lines += [
        "",
        f"[{r['rank']}] {r['name'].upper()}  ·  {r['customer_id']}  ·  {r['coach']}",
        f"    {r['plan']}  ·  {r['medication']}",
        f"    FLAG: {r['flag_type']}",
        f"    {r['flag_reason']}",
        f"    Last msg ({r['last_customer_msg_date']}): \"{r['last_customer_msg']}\"",
    ]

lines += [
    "",
    SEP,
    f"P2 — IMPORTANT THIS WEEK ({len(p2)})",
    SEP,
]
for r in p2:
    lines += [
        "",
        f"[{r['rank']}] {r['name'].upper()}  ·  {r['customer_id']}  ·  {r['coach']}  ·  {r['flag_type']}",
        f"    {r['flag_reason']}",
    ]

lines += [
    "",
    SEP,
    f"P3 — ACTIVE, NO FLAGS ({len(p3)})  ·  Routine monitoring only",
    SEP,
    "",
    "  " + " · ".join(r["name"] for r in p3),
    "",
    SEP,
    "DATA QUALITY NOTES",
    SEP,
    "• C10 missing from customers.csv (gap in customer IDs)",
    "• Farhan Qureshi (WA-141) is in messages but NOT in customers.csv — CRM gap",
    "• Oct 9 and Oct 16 coach blasts were sent to ALL groups including lifestyle-plan",
    "  customers who are not on GLP-1 — excluded from 'coach replied' calculation",
    "• C08 Pooja Nair has no WhatsApp group ID — onboarding incomplete",
    "• C20 and C21 share WA-120 (couple) — individual tracking only possible via app",
    "",
]

digest_text = "\n".join(lines)
Path("digest.txt").write_text(digest_text, encoding="utf-8")
print(f"digest.txt  — {len(lines)} lines")
print("\nDone. Submit triage.csv + digest.txt.")
