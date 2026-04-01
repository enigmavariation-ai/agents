#!/usr/bin/env python3 -u
"""
Pre-meeting brief — runs every 15 minutes via cron.
Detects meetings starting in 25-35 minutes with external attendees.
Sends a Telegram brief: who they are, prior email history, talking points.
"""

import os
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
from tavily import TavilyClient

# ── Config ────────────────────────────────────────────────────────────────────

ANTHROPIC_KEY    = os.environ['ANTHROPIC_API_KEY']
TELEGRAM_TOKEN   = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
TAVILY_KEY       = os.environ['TAVILY_API_KEY']

GOOGLE_CLIENT_ID     = os.environ['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET = os.environ['GOOGLE_CLIENT_SECRET']
GOOGLE_REFRESH_TOKEN = os.environ['GOOGLE_REFRESH_TOKEN']

BASE_DIR   = os.path.join(os.path.dirname(__file__), '..')
STATE_FILE = os.path.join(BASE_DIR, '.tmp', 'briefed_meetings.json')

TZ = ZoneInfo('Europe/Berlin')
MY_EMAIL = 'niklas@surfaize.com'

INTERNAL_DOMAINS = {'surfaize.com'}

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.readonly',
]

# ── State ─────────────────────────────────────────────────────────────────────

def load_briefed() -> set:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
            return set(data.get('briefed', []))
    except Exception:
        return set()

def save_briefed(briefed: set):
    briefed_list = list(briefed)[-200:]
    with open(STATE_FILE, 'w') as f:
        json.dump({'briefed': briefed_list}, f)

# ── Google Auth ───────────────────────────────────────────────────────────────

def get_creds() -> Credentials:
    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds

# ── Calendar ──────────────────────────────────────────────────────────────────

def get_upcoming_meetings(service) -> list[dict]:
    """Find meetings starting in 25-35 minutes."""
    now = datetime.datetime.now(TZ)
    window_start = now + datetime.timedelta(minutes=25)
    window_end   = now + datetime.timedelta(minutes=35)

    result = service.events().list(
        calendarId='primary',
        timeMin=window_start.isoformat(),
        timeMax=window_end.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    meetings = []
    for event in result.get('items', []):
        # Skip all-day events
        if 'dateTime' not in event.get('start', {}):
            continue
        # Skip declined events
        if event.get('status') == 'cancelled':
            continue

        attendees = event.get('attendees', [])
        external = [
            a for a in attendees
            if not a.get('self')
            and a.get('responseStatus') != 'declined'
            and a.get('email', '').split('@')[-1] not in INTERNAL_DOMAINS
            and not a.get('email', '').endswith('calendar.google.com')
        ]

        # Only brief if there are external attendees
        if not external:
            continue

        start_dt = datetime.datetime.fromisoformat(event['start']['dateTime'])
        meetings.append({
            'id': event['id'],
            'title': event.get('summary', 'Meeting'),
            'start': start_dt,
            'duration_min': int((
                datetime.datetime.fromisoformat(event['end']['dateTime']) - start_dt
            ).total_seconds() / 60),
            'description': (event.get('description', '') or '')[:500],
            'location': event.get('location', ''),
            'external_attendees': [
                {'email': a['email'], 'name': a.get('displayName', '')}
                for a in external
            ],
        })
    return meetings

# ── Gmail history ─────────────────────────────────────────────────────────────

def get_email_history(gmail_service, email: str) -> str:
    """Get last 3 email exchanges with this person."""
    try:
        results = gmail_service.users().messages().list(
            userId='me',
            q=f'from:{email} OR to:{email}',
            maxResults=5
        ).execute()
        messages = results.get('messages', [])
        if not messages:
            return 'No prior email history.'

        excerpts = []
        for msg in messages[:3]:
            detail = gmail_service.users().messages().get(
                userId='me', id=msg['id'], format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()
            headers = {h['name']: h['value'] for h in detail['payload']['headers']}
            excerpts.append(
                f"{headers.get('Date', '')} | {headers.get('From', '')} | {headers.get('Subject', '')}\n"
                f"  {detail.get('snippet', '')[:200]}"
            )
        return '\n\n'.join(excerpts)
    except Exception:
        return 'Email history unavailable.'

# ── Web research ──────────────────────────────────────────────────────────────

def research_attendee(name: str, email: str) -> str:
    """Search for context on the attendee — company, role, recent news."""
    if not name and not email:
        return ''
    try:
        client = TavilyClient(api_key=TAVILY_KEY)
        domain = email.split('@')[-1] if '@' in email else ''
        query = f"{name} {domain}".strip() if name else domain
        if not query:
            return ''
        resp = client.search(query, max_results=3, days=90)
        results = resp.get('results', [])
        if not results:
            return 'No web results found.'
        lines = []
        for r in results[:3]:
            lines.append(f"- {r.get('title', '')}: {(r.get('content', '') or '')[:200]}")
        return '\n'.join(lines)
    except Exception:
        return ''

# ── Synthesize brief ──────────────────────────────────────────────────────────

def synthesize_brief(meeting: dict, attendee_context: list[dict]) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    attendee_block = ''
    for a in attendee_context:
        attendee_block += f"\nAttendee: {a['name']} <{a['email']}>\n"
        if a.get('web_research'):
            attendee_block += f"Web context:\n{a['web_research']}\n"
        if a.get('email_history'):
            attendee_block += f"Email history:\n{a['email_history']}\n"

    start_str = meeting['start'].strftime('%H:%M')

    prompt = f"""You are briefing Nik (CEO of Surfaize) on a meeting starting in ~30 minutes. Be direct, crisp. Max 2 minutes to read.

Meeting: {meeting['title']}
Time: {start_str} ({meeting['duration_min']} min)
Location/Link: {meeting['location'] or 'See calendar'}
Calendar description: {meeting['description'] or 'None'}

Attendees and context:
{attendee_block}

Surfaize context: AI OS for e-commerce brands, seed stage, Berlin. Q1 priority: first paying customers, 100k MRR.

Write the brief in this format:

🗓 PRE-MEETING BRIEF — {meeting['title']}
{start_str} · {meeting['duration_min']} min

WHO
[Name, role, company — 1-2 lines per person. What they do, why they matter.]

CONTEXT
[What's the history? Any prior emails, last interaction, what was discussed or promised.]

THEIR LIKELY AGENDA
[What do they probably want from this meeting?]

TALKING POINTS
1. [Point]
2. [Point]
3. [Point]

WATCH OUT FOR
[Any risk, tension, or thing to be careful about — skip if none]

Plain text only, no markdown symbols."""

    response = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=800,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return response.content[0].text.strip()

# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(text: str):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
    for chunk in chunks:
        requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': chunk})

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    briefed = load_briefed()
    creds = get_creds()
    cal_service = build('calendar', 'v3', credentials=creds)
    gmail_service = build('gmail', 'v1', credentials=creds)

    meetings = get_upcoming_meetings(cal_service)

    for meeting in meetings:
        if meeting['id'] in briefed:
            print(f"Already briefed: {meeting['title']}")
            continue

        print(f"Briefing: {meeting['title']} at {meeting['start'].strftime('%H:%M')}")

        # Research each external attendee
        attendee_context = []
        for attendee in meeting['external_attendees']:
            email = attendee['email']
            name  = attendee['name']
            print(f"  Researching {name or email}...")
            attendee_context.append({
                'name': name or email,
                'email': email,
                'web_research': research_attendee(name, email),
                'email_history': get_email_history(gmail_service, email),
            })

        brief = synthesize_brief(meeting, attendee_context)
        send_telegram(brief)
        briefed.add(meeting['id'])
        print(f"Brief sent for: {meeting['title']}")

    save_briefed(briefed)
    if not meetings:
        print('No upcoming external meetings in window.')

if __name__ == '__main__':
    main()
