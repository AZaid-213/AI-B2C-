# AI B2C WhatsApp Campaign Manager Backend

## Setup

1. Create a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in values.
4. Start Redis locally or use a hosted Redis instance.
5. Run the app:
   ```powershell
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
6. Start the worker:
   ```powershell
   rq worker campaigns
   ```

## API Endpoints

- `POST /api/campaigns/upload-contacts` — upload CSV and clean contacts
- `POST /api/campaigns/generate-copy` — generate WhatsApp copy with AI
- `POST /api/campaigns/create` — build a campaign draft
- `POST /api/campaigns/confirm` — confirm and enqueue the campaign send
- `GET /api/campaigns/drafts/{draft_id}` — inspect draft payload
- `GET /api/campaigns/greenapi/state` — verify GreenAPI authorization

## Notes

This backend now supports the AI automation workflow: upload contacts, auto-generate copy, create a campaign draft, and confirm send with Redis queue processing.
