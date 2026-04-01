#!/usr/bin/env python3
"""
Standalone morning briefing script.
Fetches Gmail, Calendar, ClickUp, news — synthesizes via Anthropic API — sends to Telegram.
Runs via GitHub Actions cron at 7:03am CET daily.
"""

import os
import sys
import json
import time
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

ANTHROPIC_KEY     = os.environ['ANTHROPIC_API_KEY']
TELEGRAM_TOKEN    = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID  = os.environ['TELEGRAM_CHAT_ID']
CLICKUP_TOKEN     = os.environ['CLICKUP_API_TOKEN']
TAVILY_KEY        = os.environ['TAVILY_API_KEY']

GOOGLE_CLIENT_ID      = os.environ['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET  = os.environ['GOOGLE_CLIENT_SECRET']
GOOGLE_REFRESH_TOKEN  = os.environ['GOOGLE_REFRESH_TOKEN']

CLICKUP_LIST_ID = '901521517857'
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
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/calendar.readonly',
        ],
    )
    creds.refresh(Request())
    return creds

# ── Gmail ─────────────────────────────────────────────────────────────────────

def fetch_emails(creds: Credentials) -> list[dict]:
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(
        userId='me',
        q='is:unread newer_than:1d -from:notifications@vercel.com -from:noreply -category:promotions -category:social',
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

# ── Calendar ──────────────────────────────────────────────────────────────────

def fetch_calendar(creds: Credentials) -> list[dict]:
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(days=1)

    events_result = service.events().list(
        calendarId='primary',
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
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

# ── ClickUp ───────────────────────────────────────────────────────────────────

def fetch_clickup() -> str:
    script = os.path.join(os.path.dirname(__file__), 'fetch_clickup.py')
    import subprocess
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True, text=True
    )
    return result.stdout.strip()

# ── News ──────────────────────────────────────────────────────────────────────

def fetch_news() -> list[dict]:
    from tavily import TavilyClient
    client = TavilyClient(api_key=TAVILY_KEY)

    queries = [
        'AI agents e-commerce operations news',
        'multi-agent AI systems funding startup news',
    ]

    results = []
    for q in queries:
        try:
            resp = client.search(q, max_results=3, days=3)
            for r in resp.get('results', []):
                results.append({
                    'title': r.get('title', ''),
                    'url': r.get('url', ''),
                    'content': (r.get('content', '') or '')[:300],
                })
        except Exception:
            pass

    return results[:5]

# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(text: str):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
    for chunk in chunks:
        requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': chunk})

# ── Synthesize via Claude ─────────────────────────────────────────────────────

def synthesize(emails, calendar, clickup, news, today: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    context = f"""
Today: {today}

CALENDAR EVENTS:
{json.dumps(calendar, indent=2)}

UNREAD EMAILS (last 24h, filtered):
{json.dumps(emails, indent=2)}

TEAM KANBAN (ClickUp):
{clickup}

NEWS RESULTS:
{json.dumps(news, indent=2)}
"""

    prompt = f"""You are the personal Executive Assistant for Nik, CEO of Surfaize (AI OS for e-commerce brands, seed stage, Berlin).

Generate his morning briefing using this exact format. Be direct, crisp, no filler.

{context}

Output the briefing in this format:

☕ MORNING BRIEFING — [Weekday, Date]

TO START YOUR DAY
Philosophy: "[obscure, genuinely thought-provoking quote]" — [Author]
Drive: "[earned, non-cliche motivational quote]" — [Author]

━━━━━━━━━━━━━━━━━━━━━━━━━

📅 CALENDAR
[Time] [Event]
  -> [Attendees / what to prep — 1 line]
[Flag conflicts or missing prep with ⚠️]

━━━━━━━━━━━━━━━━━━━━━━━━━

📬 EMAIL PRIORITIES
1. [Sender] — [Subject]
   -> [Why it matters / action needed]
(Max 5. Skip automated alerts, receipts, newsletters.)

━━━━━━━━━━━━━━━━━━━━━━━━━

✅ TEAM KANBAN — [X] total tasks

Nik: [X in progress / X to do / X blocked]
[icon] [task]

Jelena: [X in progress / X to do / X blocked]
[icon] [task]

Fabi: [X in progress / X to do / X blocked]
[icon] [task]

⚠️ BLOCKED: [task] — [who]

━━━━━━━━━━━━━━━━━━━━━━━━━

📰 NEWS THAT MATTERS
- [Headline] — [Why relevant to Surfaize, 1 sentence]
(3 items max)

━━━━━━━━━━━━━━━━━━━━━━━━━

🚦 TOP 3 TODAY
1. [Priority] — [Why it can't wait]
2. [Priority] — [Why it can't wait]
3. [Priority] — [Why it can't wait]

━━━━━━━━━━━━━━━━━━━━━━━━━

✉️ CO-FOUNDER UPDATE (draft — edit before sending)

Hey Jelena & Fabi 👋

Quick update for today:

🔴 Needs a decision / urgent
- [item]

🟡 In progress on my end
- [item]

🟢 Done since yesterday
- [item]

📌 FYI
- [item]

Catch you at [next shared slot] ✌️

Rules:
- Quote rules: philosophical = Cioran, Wittgenstein, Simone Weil, Borges, Pessoa, Arendt, Taleb or similar — never obvious. Motivational = Marcus Aurelius specific passage, Epictetus, Rilke, Seneca — no hustle clichés.
- Co-founder update under 200 words, startup-casual tone.
- Never send anything — this is always a draft.
- Use plain text only, no markdown asterisks or symbols that don't render in Telegram.
"""

    message = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=2000,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return message.content[0].text

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print('Fetching data...')
    today = datetime.datetime.now(TZ).strftime('%A, %d %B %Y')

    try:
        creds = get_google_creds()
        emails = fetch_emails(creds)
        calendar = fetch_calendar(creds)
    except Exception as e:
        print(f'Google API error: {e}')
        emails, calendar = [], []

    try:
        clickup = fetch_clickup()
    except Exception as e:
        print(f'ClickUp error: {e}')
        clickup = 'ClickUp unavailable'

    try:
        news = fetch_news()
    except Exception as e:
        print(f'News error: {e}')
        news = []

    print('Synthesizing briefing...')
    briefing = synthesize(emails, calendar, clickup, news, today)

    print('Sending to Telegram...')
    send_telegram(briefing)
    print('Done.')

if __name__ == '__main__':
    main()
