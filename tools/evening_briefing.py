#!/usr/bin/env python3
"""
Standalone evening briefing script.
Fetches tomorrow's calendar, open email threads, ClickUp closeout — synthesizes via Anthropic — sends to Telegram.
Runs via cron at 8pm Berlin time daily.
"""

import os
import sys
import json
import datetime
import requests
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import anthropic
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ── Config ────────────────────────────────────────────────────────────────────

ANTHROPIC_KEY    = os.environ['ANTHROPIC_API_KEY']
TELEGRAM_TOKEN   = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

GOOGLE_CLIENT_ID     = os.environ['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET = os.environ['GOOGLE_CLIENT_SECRET']
GOOGLE_REFRESH_TOKEN = os.environ['GOOGLE_REFRESH_TOKEN']

TZ = ZoneInfo('Europe/Berlin')

# ── Google Auth ───────────────────────────────────────────────────────────────

def get_google_creds() -> Credentials:
    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=[
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/calendar.readonly',
        ],
    )
    creds.refresh(Request())
    return creds

# ── Calendar (tomorrow) ───────────────────────────────────────────────────────

def fetch_tomorrow_calendar(creds: Credentials) -> list[dict]:
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.now(TZ)
    tomorrow_start = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow_start + datetime.timedelta(days=1)

    events_result = service.events().list(
        calendarId='primary',
        timeMin=tomorrow_start.isoformat(),
        timeMax=tomorrow_end.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = []
    for e in events_result.get('items', []):
        start_dt = e['start'].get('dateTime', e['start'].get('date', ''))
        end_dt = e['end'].get('dateTime', e['end'].get('date', ''))
        attendees = [a.get('email', '') for a in e.get('attendees', []) if not a.get('self')]
        events.append({
            'summary': e.get('summary', 'No title'),
            'start': start_dt,
            'end': end_dt,
            'attendees': attendees,
            'description': (e.get('description', '') or '')[:200],
        })
    return events

# ── Gmail (open threads) ──────────────────────────────────────────────────────

def fetch_open_threads(creds: Credentials) -> list[dict]:
    service = build('gmail', 'v1', credentials=creds)

    # Threads where someone is waiting on a reply from Nik
    results = service.users().messages().list(
        userId='me',
        q='is:unread -from:notifications@vercel.com -from:noreply -from:no-reply -category:promotions -category:social -category:updates newer_than:3d',
        maxResults=10
    ).execute()

    messages = results.get('messages', [])
    emails = []
    for msg in messages:
        detail = service.users().messages().get(
            userId='me', id=msg['id'], format='metadata',
            metadataHeaders=['From', 'Subject', 'Date']
        ).execute()
        headers = {h['name']: h['value'] for h in detail['payload']['headers']}
        snippet = detail.get('snippet', '')
        emails.append({
            'from': headers.get('From', ''),
            'subject': headers.get('Subject', ''),
            'date': headers.get('Date', ''),
            'snippet': snippet[:200],
        })
    return emails

# ── ClickUp ───────────────────────────────────────────────────────────────────

def fetch_clickup() -> str:
    script = os.path.join(os.path.dirname(__file__), 'fetch_clickup.py')
    import subprocess
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True, text=True
    )
    return result.stdout.strip()

# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(text: str):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
    for chunk in chunks:
        requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': chunk})

# ── Synthesize via Claude ─────────────────────────────────────────────────────

def synthesize(tomorrow_calendar, open_threads, clickup, today: str, tomorrow: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    context = f"""
Today: {today}
Tomorrow: {tomorrow}

TOMORROW'S CALENDAR:
{json.dumps(tomorrow_calendar, indent=2)}

OPEN EMAIL THREADS (unread, last 3 days):
{json.dumps(open_threads, indent=2)}

TEAM KANBAN (ClickUp):
{clickup}
"""

    prompt = f"""You are the personal Executive Assistant for Nik, CEO of Surfaize (AI OS for e-commerce brands, seed stage, Berlin).

Generate his evening briefing — a next-day preview to end the day clean and start tomorrow sharp. Be direct, crisp, no filler. Under 2 minutes to read.

{context}

Output the briefing in this exact format:

🌙 EVENING BRIEFING — [Weekday, Date]
Prep for [Tomorrow's Weekday]

━━━━━━━━━━━━━━━━━━━━━━━━━

📅 TOMORROW'S CALENDAR
[Time] [Event]
  -> [Who / what to prepare — 1 line max]
[Flag back-to-backs, early starts, heavy days with ⚠️]
(If empty: "Clear day — use it for deep work.")

━━━━━━━━━━━━━━━━━━━━━━━━━

📬 OPEN EMAIL THREADS
- [Sender] — [Subject] — [What's needed]
(Only threads needing action before tomorrow. If none: "Inbox clear.")

━━━━━━━━━━━━━━━━━━━━━━━━━

✅ CLOSE OUT TODAY
- [Task] — [why close it tonight or move it forward]
(Only tasks that realistically could/should be done tonight. Max 3.)

━━━━━━━━━━━━━━━━━━━━━━━━━

🚦 TOMORROW'S TOP 3
1. [Priority] — [Why first]
2. [Priority] — [Why second]
3. [Priority] — [Why third]

━━━━━━━━━━━━━━━━━━━━━━━━━

🌙 DO TONIGHT
- [Action] — [Why it matters for tomorrow]
(Max 3. If nothing urgent: "Nothing blocking. Rest.")

━━━━━━━━━━━━━━━━━━━━━━━━━

Rules:
- Plain text only, no markdown asterisks.
- Ruthlessly filter "do tonight" — only things that genuinely unblock tomorrow.
- If tomorrow is weekend, note it but still run it.
- Keep total under 2 minutes to read.
- Q1 priorities for Nik: first paying customers, strategy execution, 100k MRR in 6 months.
"""

    message = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=1500,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return message.content[0].text

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print('Fetching data...')
    now = datetime.datetime.now(TZ)
    today = now.strftime('%A, %d %B %Y')
    tomorrow = (now + datetime.timedelta(days=1)).strftime('%A, %d %B %Y')

    try:
        creds = get_google_creds()
        tomorrow_calendar = fetch_tomorrow_calendar(creds)
        open_threads = fetch_open_threads(creds)
    except Exception as e:
        print(f'Google API error: {e}')
        tomorrow_calendar, open_threads = [], []

    try:
        clickup = fetch_clickup()
    except Exception as e:
        print(f'ClickUp error: {e}')
        clickup = 'ClickUp unavailable'

    print('Synthesizing briefing...')
    briefing = synthesize(tomorrow_calendar, open_threads, clickup, today, tomorrow)

    print('Sending to Telegram...')
    send_telegram(briefing)
    print('Done.')

if __name__ == '__main__':
    main()
