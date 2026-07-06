import httpx
import json

BASE = 'http://localhost:8000/api/campaigns'

csv_data = (
    "name,phone,city\n"
    "Ali,+923001234567,Karachi\n"
    "Sara,+923111234567,Lahore\n"
    "Test,+923422454713,Lahore\n"
    "Ali,+923001234567,Karachi\n"
)

print('Uploading CSV...')
with httpx.Client(timeout=20) as client:
    files = {'file': ('contacts.csv', csv_data.encode(), 'text/csv')}
    r = client.post(f'{BASE}/upload-contacts', files=files)
    print('upload status', r.status_code)
    print(r.text)
    if r.status_code != 200:
        raise SystemExit('Upload failed')
    data = r.json()

contacts = data.get('contacts', [])
print('Normalized contacts:', len(contacts))

print('Calling /mvp/generate...')
payload = {
    'contacts_json': [{'name': c.get('name'), 'phone': c.get('phone'), 'city': c.get('city')} for c in contacts],
    'business_context': 'Clothing store weekend sale',
    'tone': 'Friendly',
}

r = client.post(f'{BASE}/mvp/generate', json=payload, timeout=60)
print('generate status', r.status_code)
print(r.text)
if r.status_code != 200:
    raise SystemExit('Generate failed')

preview = r.json()
message = '\n\n'.join([preview.get('headline',''), preview.get('message',''), preview.get('cta','')]).strip()
print('\nPreview message:\n', message)

print('\nCalling /mvp/send (will send to MVP_PHONE)...')
r = client.post(f'{BASE}/mvp/send', json={'message': message}, timeout=60)
print('send status', r.status_code)
print(r.text)
if r.status_code != 200:
    raise SystemExit('Send failed')

print('\nE2E test succeeded')
