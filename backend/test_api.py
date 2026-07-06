"""
Live API test script — runs against the running FastAPI server.
Usage:  python test_api.py
Requires the server to be running:  uvicorn app.main:app --reload
"""

import sys
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = "http://127.0.0.1:8000"
TEST_PHONE = os.getenv("TEST_PHONE", "924224547133")   # +92 422 454 713 3

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

results = []


def check(name: str, ok: bool, detail: str = ""):
    symbol = PASS if ok else FAIL
    print(f"  {symbol} {name}" + (f" — {detail}" if detail else ""))
    results.append(ok)


def section(title: str):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


# ──────────────────────────────────────────────────────
# 1. Health check
# ──────────────────────────────────────────────────────
section("1. Health check")
try:
    r = httpx.get(f"{BASE}/health", timeout=5)
    body = r.json()
    check("HTTP 200", r.status_code == 200)
    check("Groq configured",     body.get("groq_configured"),     str(body.get("groq_configured")))
    check("GreenAPI configured", body.get("greenapi_configured"), str(body.get("greenapi_configured")))
except Exception as e:
    check("Server reachable", False, str(e))
    print("\n  ⚠  Server not running. Start it with:\n     uvicorn app.main:app --reload\n")
    sys.exit(1)


# ──────────────────────────────────────────────────────
# 2. GreenAPI — instance state
# ──────────────────────────────────────────────────────
section("2. GreenAPI — instance state")
greenapi_authorized = False
try:
    r = httpx.get(f"{BASE}/api/campaigns/greenapi/state", timeout=10)
    body = r.json()
    check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    state = body.get("stateInstance", "unknown")
    greenapi_authorized = state == "authorized"
    check(
        f"Instance state: {state}",
        greenapi_authorized,
        "Ready to send ✓" if greenapi_authorized
        else "Not authorized — scan QR at /api/campaigns/greenapi/qr",
    )
except Exception as e:
    check("GreenAPI reachable", False, str(e))


# ──────────────────────────────────────────────────────
# 3. GreenAPI — instance settings
# ──────────────────────────────────────────────────────
section("3. GreenAPI — instance settings")
try:
    r = httpx.get(f"{BASE}/api/campaigns/greenapi/settings", timeout=10)
    check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        body = r.json()
        print(f"     wid            : {body.get('wid', 'n/a')}")
        print(f"     webhookUrl     : {body.get('webhookUrl', 'n/a')}")
        print(f"     outgoingWebhook: {body.get('outgoingWebhook', 'n/a')}")
except Exception as e:
    check("GreenAPI settings", False, str(e))


# ──────────────────────────────────────────────────────
# 4. GreenAPI — send test message to dummy number
# ──────────────────────────────────────────────────────
section(f"4. GreenAPI — send text to {TEST_PHONE}")
if greenapi_authorized:
    try:
        r = httpx.post(
            f"{BASE}/api/campaigns/send-message",
            json={
                "phone": TEST_PHONE,
                "message_type": "text",
                "message_text": "🤖 Test message from B2C Campaign Manager — API is working!",
            },
            timeout=30,
        )
        body = r.json()
        check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
        if r.status_code == 200:
            msg_id = body.get("greenapi_response", {}).get("idMessage", "")
            check("idMessage returned", bool(msg_id), msg_id)
            print(f"     idMessage: {msg_id}")
    except Exception as e:
        check("Send message", False, str(e))
else:
    print(f"  ⚠  Skipped — GreenAPI not authorized yet.")
    print(f"     Scan QR at: {BASE}/api/campaigns/greenapi/qr")
    results.append(None)   # neutral — not a failure


# ──────────────────────────────────────────────────────
# 5. Spam check
# ──────────────────────────────────────────────────────
section("5. Spam check")
try:
    r = httpx.post(
        f"{BASE}/api/campaigns/spam-check",
        json={"message": "BUY NOW!!! FREE OFFER http://example.com 🎉🎊🥳✨🔥💥💯😀😃"},
        timeout=5,
    )
    check("HTTP 200", r.status_code == 200)
    body = r.json()
    check(f"spam_risk={body.get('spam_risk')}", body.get("spam_risk", 0) > 0, f"quality={body.get('quality')}")
    check("reasons returned", len(body.get("reasons", [])) > 0, str(body.get("reasons")))
except Exception as e:
    check("Spam check", False, str(e))


# ──────────────────────────────────────────────────────
# 6. Groq — generate campaign copy
# ──────────────────────────────────────────────────────
section("6. Groq — generate campaign copy")
try:
    r = httpx.post(
        f"{BASE}/api/campaigns/generate-copy",
        json={
            "business_type": "Online Clothing Store",
            "campaign_goal": "Drive sales with a flash sale",
            "audience": "Women aged 18-35",
            "offer": "50% off all dresses this weekend",
            "tone": "Exciting",
        },
        timeout=30,
    )
    check("HTTP 200", r.status_code == 200, f"got {r.status_code} — {r.text[:120]}")
    if r.status_code == 200:
        body = r.json()
        check("headline returned", bool(body.get("headline")), body.get("headline", "")[:60])
        check("caption returned",  bool(body.get("caption")),  body.get("caption",  "")[:60])
        check("cta returned",      bool(body.get("cta")),      body.get("cta",      "")[:60])
        print(f"     headline : {body.get('headline','')[:60]}")
        print(f"     caption  : {body.get('caption','')[:70]}")
        print(f"     cta      : {body.get('cta','')[:60]}")
        print(f"     spam_risk: {body.get('spam_score')}")
except Exception as e:
    check("Groq generate-copy", False, str(e))


# ──────────────────────────────────────────────────────
# 7. AI campaign draft (message_type=ai)
# ──────────────────────────────────────────────────────
section("7. AI campaign draft (auto-generates copy)")
ai_draft_id = None
try:
    r = httpx.post(
        f"{BASE}/api/campaigns/create",
        json={
            "name": "AI Flash Sale",
            "campaign_type": "promotional",
            "message_type": "ai",
            "contacts": [TEST_PHONE],
            "business_type": "Clothing Store",
            "campaign_goal": "Weekend flash sale",
            "audience": "All customers",
            "offer": "30% off everything",
            "tone": "Friendly",
        },
        timeout=30,
    )
    check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        body = r.json()
        ai_draft_id = body.get("draft_id")
        generated = body.get("payload", {}).get("generated_copy", {})
        check("draft_id returned",      bool(ai_draft_id), ai_draft_id)
        check("AI copy generated",      bool(generated),   str(bool(generated)))
        check("message_text populated", bool(body["payload"].get("message_text")), "")
        print(f"     headline : {generated.get('headline','')[:60]}")
        print(f"     caption  : {generated.get('caption','')[:70]}")
except Exception as e:
    check("AI draft", False, str(e))


# ──────────────────────────────────────────────────────
# 8. Campaign draft flow (create → list → get → delete)
# ──────────────────────────────────────────────────────
section("8. Text campaign draft flow")
draft_id = None
try:
    r = httpx.post(
        f"{BASE}/api/campaigns/create",
        json={
            "name": "Test Text Campaign",
            "campaign_type": "promotional",
            "message_type": "text",
            "message_text": "Hello from B2C test!",
            "contacts": [TEST_PHONE],
        },
        timeout=10,
    )
    check("POST /create — HTTP 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        draft_id = r.json().get("draft_id")
        check("draft_id returned", bool(draft_id), draft_id)
except Exception as e:
    check("Create draft", False, str(e))

if draft_id:
    r = httpx.get(f"{BASE}/api/campaigns/drafts", timeout=5)
    check("GET /drafts lists draft", draft_id in [d["draft_id"] for d in r.json()])

    r = httpx.get(f"{BASE}/api/campaigns/drafts/{draft_id}", timeout=5)
    check("GET /drafts/{id} — HTTP 200", r.status_code == 200)

    r = httpx.delete(f"{BASE}/api/campaigns/drafts/{draft_id}", timeout=5)
    check("DELETE /drafts/{id} — HTTP 200", r.status_code == 200)

    r = httpx.get(f"{BASE}/api/campaigns/drafts/{draft_id}", timeout=5)
    check("Draft gone after delete", r.status_code == 404)


# ──────────────────────────────────────────────────────
# 9. Upload contacts CSV
# ──────────────────────────────────────────────────────
section("9. Upload contacts CSV")
try:
    csv_data = (
        "name,phone,city\n"
        "Ali,+923001234567,Karachi\n"
        "Sara,+923111234567,Lahore\n"
        f"Test,+{TEST_PHONE},Lahore\n"
        "Ali,+923001234567,Karachi\n"   # duplicate
    )
    r = httpx.post(
        f"{BASE}/api/campaigns/upload-contacts",
        files={"file": ("contacts.csv", csv_data.encode(), "text/csv")},
        timeout=10,
    )
    check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        s = r.json().get("summary", {})
        check(f"total=4",        s.get("total") == 4,        str(s))
        check(f"valid=3",        s.get("valid") == 3,        str(s))
        check(f"duplicates=1",   s.get("duplicates") == 1,   str(s))
except Exception as e:
    check("Upload contacts", False, str(e))


# ──────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────
print(f"\n{'═'*55}")
real_results = [r for r in results if r is not None]  # exclude neutral skips
passed = sum(real_results)
total  = len(real_results)
skipped = results.count(None)
print(f"  Results : {passed}/{total} passed" + (f"  ({skipped} skipped)" if skipped else ""))
if passed == total:
    print("  \033[92mAll tests passed!\033[0m")
else:
    print(f"  \033[91m{total - passed} test(s) failed.\033[0m")
print(f"{'═'*55}\n")

sys.exit(0 if passed == total else 1)
