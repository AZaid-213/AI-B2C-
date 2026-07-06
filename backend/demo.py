"""
╔══════════════════════════════════════════════════════════════╗
║       B2C WhatsApp Campaign Manager — End-to-End Demo       ║
╚══════════════════════════════════════════════════════════════╝

Full real-world flow:
  1. Parse contacts from CSV
  2. Generate personalised AI copy (Groq) for each contact
  3. Send each message via GreenAPI with random 1-10s delay
  4. Print a live delivery report

Usage:
    python demo.py
    python demo.py --csv demo_contacts.csv --business "Clothing Store" --goal "Weekend sale" --offer "30% off"
"""

import argparse
import asyncio
import csv
import io
import json
import os
import random
import sys
import time
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
BASE          = "http://127.0.0.1:8000"
CSV_FILE      = "demo_contacts.csv"
BUSINESS_TYPE = "Fashion & Clothing Store"
CAMPAIGN_GOAL = "Weekend flash sale — drive immediate purchases"
AUDIENCE      = "Pakistani shoppers aged 18–40"
OFFER         = "30% off on all items this weekend only"
TONE          = "Exciting and friendly"

# ANSI colours
G  = "\033[92m"   # green
R  = "\033[91m"   # red
Y  = "\033[93m"   # yellow
B  = "\033[94m"   # blue
C  = "\033[96m"   # cyan
W  = "\033[97m"   # white bold
RS = "\033[0m"    # reset

def hdr(txt):  print(f"\n{C}{'─'*60}{RS}\n  {W}{txt}{RS}\n{C}{'─'*60}{RS}")
def ok(txt):   print(f"  {G}✓{RS}  {txt}")
def err(txt):  print(f"  {R}✗{RS}  {txt}")
def info(txt): print(f"  {Y}→{RS}  {txt}")
def sep():     print(f"{B}{'═'*60}{RS}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_server():
    try:
        r = httpx.get(f"{BASE}/health", timeout=4)
        return r.status_code == 200
    except Exception:
        return False


def parse_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


async def generate_copy_for_contact(client: httpx.AsyncClient, contact: dict) -> dict:
    """Generate personalised AI copy mentioning the contact's name."""
    name = contact.get("name") or "Valued Customer"
    city = contact.get("city") or ""
    personalised_offer = (
        f"{OFFER}. Address this message personally to {name}"
        + (f" from {city}" if city else "")
        + "."
    )
    payload = {
        "business_type": BUSINESS_TYPE,
        "campaign_goal": CAMPAIGN_GOAL,
        "audience": AUDIENCE,
        "offer": personalised_offer,
        "tone": TONE,
    }
    resp = await client.post(f"{BASE}/api/campaigns/generate-copy", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


async def send_whatsapp(client: httpx.AsyncClient, phone: str, message: str) -> dict:
    """Send via the /send-message endpoint (which includes the random delay internally)."""
    payload = {
        "phone": phone,
        "message_type": "text",
        "message_text": message,
    }
    resp = await client.post(f"{BASE}/api/campaigns/send-message", json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ── Main demo ─────────────────────────────────────────────────────────────────

async def run_demo(csv_path: str, business: str, goal: str, offer: str):
    sep()
    print(f"\n  {W}B2C WhatsApp Campaign Manager{RS}  —  {C}Live Demo{RS}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sep()

    # ── Step 1: Server health ─────────────────────────────────────────────────
    hdr("Step 1 — Server health check")
    if not check_server():
        err("Server not running at http://127.0.0.1:8000")
        err("Start it with:  uvicorn app.main:app --port 8000")
        sys.exit(1)

    r = httpx.get(f"{BASE}/health")
    h = r.json()
    ok(f"Server is up  |  env={h['env']}")
    ok(f"Groq configured    : {h['groq_configured']}")
    ok(f"GreenAPI configured: {h['greenapi_configured']}")

    # ── Step 2: GreenAPI state ────────────────────────────────────────────────
    hdr("Step 2 — GreenAPI instance state")
    r = httpx.get(f"{BASE}/api/campaigns/greenapi/state", timeout=10)
    state = r.json().get("stateInstance", "unknown")
    if state != "authorized":
        err(f"GreenAPI state: {state}")
        err(f"Scan QR at: {BASE}/api/campaigns/greenapi/qr")
        sys.exit(1)
    ok(f"GreenAPI authorized  (wid ready to send)")

    # ── Step 3: Parse CSV ─────────────────────────────────────────────────────
    hdr(f"Step 3 — Parse contacts from {csv_path}")
    rows = parse_csv(csv_path)
    info(f"Raw rows in CSV: {len(rows)}")

    # Upload to backend for normalisation + dedup
    with open(csv_path, "rb") as f:
        upload = httpx.post(
            f"{BASE}/api/campaigns/upload-contacts",
            files={"file": (os.path.basename(csv_path), f, "text/csv")},
            timeout=15,
        )
    upload.raise_for_status()
    result  = upload.json()
    summary = result["summary"]
    contacts = result["contacts"]   # normalised, deduped

    ok(f"Total rows    : {summary['total']}")
    ok(f"Valid contacts: {summary['valid']}")
    info(f"Duplicates    : {summary['duplicates']}")
    info(f"Invalid phones: {summary['invalid']}")

    if not contacts:
        err("No valid contacts to send to.")
        sys.exit(1)

    print(f"\n  {Y}Contacts to message:{RS}")
    for c in contacts:
        print(f"    • {c['name'] or 'Unknown':20s}  {c['phone']}  {c.get('city') or ''}")

    # ── Step 4: Generate AI copy & send ───────────────────────────────────────
    hdr(f"Step 4 — Generate AI copy (Groq) + Send via GreenAPI")
    print(f"  {Y}Campaign brief:{RS}")
    print(f"    Business : {BUSINESS_TYPE}")
    print(f"    Goal     : {CAMPAIGN_GOAL}")
    print(f"    Offer    : {OFFER}")
    print(f"    Tone     : {TONE}\n")

    report = []   # [{name, phone, message, status, delay, msg_id, error}]

    async with httpx.AsyncClient() as http:
        for idx, contact in enumerate(contacts, 1):
            name  = contact.get("name") or "Customer"
            phone = contact["phone"]

            print(f"  {B}[{idx}/{len(contacts)}]{RS} {W}{name}{RS} — {phone}")

            # 4a. Generate personalised copy
            info("Generating AI copy...")
            try:
                copy = await generate_copy_for_contact(http, contact)
                headline = copy.get("headline", "")
                caption  = copy.get("caption",  "")
                cta      = copy.get("cta",      "")
                message  = f"{headline}\n\n{caption}\n\n{cta}".strip()
                ok(f"Headline: {headline[:55]}")
                ok(f"Caption : {caption[:60]}...")
                ok(f"CTA     : {cta[:55]}")
            except Exception as e:
                err(f"Groq failed: {e}")
                report.append({"name": name, "phone": phone, "status": "copy_failed", "error": str(e)})
                continue

            # 4b. Send via GreenAPI (delay is applied inside /send-message)
            info("Sending WhatsApp message (random delay 1–10s)...")
            try:
                send_result = await send_whatsapp(http, phone, message)
                delay  = send_result.get("delay_seconds", "?")
                msg_id = send_result.get("greenapi_response", {}).get("idMessage", "?")
                ok(f"Sent!  delay={delay}s  idMessage={msg_id}")
                report.append({
                    "name": name, "phone": phone,
                    "message": message[:80] + "...",
                    "status": "sent",
                    "delay_s": delay,
                    "msg_id": msg_id,
                })
            except Exception as e:
                err(f"Send failed: {e}")
                report.append({"name": name, "phone": phone, "status": "send_failed", "error": str(e)})

            print()   # blank line between contacts

    # ── Step 5: Delivery report ───────────────────────────────────────────────
    hdr("Step 5 — Delivery Report")
    sent   = [r for r in report if r["status"] == "sent"]
    failed = [r for r in report if r["status"] != "sent"]

    print(f"  {'Contact':<22} {'Phone':<16} {'Status':<12} {'Delay':>7}  {'idMessage'}")
    print(f"  {'─'*22} {'─'*16} {'─'*12} {'─'*7}  {'─'*24}")
    for r in report:
        status_str = f"{G}sent{RS}" if r["status"] == "sent" else f"{R}{r['status']}{RS}"
        delay_str  = f"{r.get('delay_s',''):.2f}s" if r.get('delay_s') else "—"
        msg_id     = r.get("msg_id", r.get("error", "")[:24])
        print(f"  {r['name']:<22} {r['phone']:<16} {status_str:<20} {delay_str:>7}  {msg_id}")

    sep()
    print(f"\n  {G}✓ Sent    : {len(sent)}/{len(report)}{RS}")
    if failed:
        print(f"  {R}✗ Failed  : {len(failed)}/{len(report)}{RS}")
    print(f"\n  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sep()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="B2C Campaign Demo")
    parser.add_argument("--csv",      default=CSV_FILE,      help="Path to contacts CSV")
    parser.add_argument("--business", default=BUSINESS_TYPE, help="Business type")
    parser.add_argument("--goal",     default=CAMPAIGN_GOAL, help="Campaign goal")
    parser.add_argument("--offer",    default=OFFER,         help="Offer details")
    args = parser.parse_args()

    # Override globals if passed via CLI
    BUSINESS_TYPE = args.business
    CAMPAIGN_GOAL = args.goal
    OFFER         = args.offer

    asyncio.run(run_demo(args.csv, args.business, args.goal, args.offer))
