#!/usr/bin/env python3 -u
"""
Email watcher — polls Gmail every 5 minutes for priority emails.
Sends Telegram notification with auto-drafted reply.
Stores seen message IDs to avoid duplicate notifications.
"""

import os
import sys
import json
import base64
import datetime
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import anthropic
import requests
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

BASE_DIR   = os.path.join(os.path.dirname(__file__), '..')
STATE_FILE = os.path.join(BASE_DIR, '.tmp', 'seen_emails.json')
PENDING_FILE = os.path.join(BASE_DIR, '.tmp', 'pending_reply.json')

TZ = ZoneInfo('Europe/Berlin')

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.readonly',
]

# ── Priority senders ──────────────────────────────────────────────────────────

PRIORITY_SENDERS = [
    'jelena@surfaize.com',
    'fabian@surfaize.com',
    'fabi@surfaize.com',
]

SKIP_PATTERNS = [
    'noreply', 'no-reply', 'notifications@', 'updates@',
    'mailer-daemon', 'postmaster', 'dmarc', 'vercel.com',
    'linkedin.com', 'apollo.io', 'clickup.com', 'calendly.com',
    'read.ai', 'ironwifi.com', 'tavily.com',
]

def is_priority(sender: str, subject: str, in_reply_to: str) -> bool:
    sender_lower = sender.lower()

    # Skip automated senders
    for pattern in SKIP_PATTERNS:
        if pattern in sender_lower:
            return False

    # Always notify for co-founders
    for p in PRIORITY_SENDERS:
        if p in sender_lower:
            return True

    # Always notify for replies to threads Nik started
    if in_reply_to:
        return True

    # Notify for anyone emailing surfaize.com domain directly
    if 'surfaize' in subject.lower():
        return True

    return False

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

# ── State management ──────────────────────────────────────────────────────────

def load_seen() -> set:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
            return set(data.get('seen', []))
    except Exception:
        return set()

def save_seen(seen: set):
    # Keep last 500 IDs to avoid unbounded growth
    seen_list = list(seen)[-500:]
    with open(STATE_FILE, 'w') as f:
        json.dump({'seen': seen_list}, f)

def load_pending() -> dict:
    try:
        with open(PENDING_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_pending_entry(email_data: dict) -> int:
    """Add a pending reply and return its assigned number."""
    os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
    pending = load_pending()
    # Find next available number
    existing = [int(k) for k in pending.keys()] if pending else [0]
    next_num = max(existing) + 1
    pending[str(next_num)] = email_data
    with open(PENDING_FILE, 'w') as f:
        json.dump(pending, f, indent=2)
    return next_num

# ── Gmail ─────────────────────────────────────────────────────────────────────

def fetch_new_emails(service) -> list[dict]:
    """Fetch unread emails from the last 10 minutes."""
    results = service.users().messages().list(
        userId='me',
        q='is:unread newer_than:10m -category:promotions -category:social',
        maxResults=20
    ).execute()

    messages = results.get('messages', [])
    emails = []
    for msg in messages:
        detail = service.users().messages().get(
            userId='me', id=msg['id'], format='metadata',
            metadataHeaders=['From', 'Subject', 'Date', 'In-Reply-To', 'Message-ID']
        ).execute()
        headers = {h['name']: h['value'] for h in detail['payload']['headers']}
        snippet = detail.get('snippet', '')
        emails.append({
            'id': msg['id'],
            'thread_id': detail.get('threadId', ''),
            'from': headers.get('From', ''),
            'subject': headers.get('Subject', ''),
            'date': headers.get('Date', ''),
            'in_reply_to': headers.get('In-Reply-To', ''),
            'message_id': headers.get('Message-ID', ''),
            'snippet': snippet[:400],
        })
    return emails

def fetch_thread(service, thread_id: str) -> str:
    """Fetch thread context for drafting a reply."""
    try:
        thread = service.users().threads().get(
            userId='me', id=thread_id, format='metadata',
            metadataHeaders=['From', 'Subject', 'Date']
        ).execute()
        messages = thread.get('messages', [])[-5:]  # last 5 messages
        parts = []
        for m in messages:
            headers = {h['name']: h['value'] for h in m['payload']['headers']}
            parts.append(f"From: {headers.get('From', '')}\nDate: {headers.get('Date', '')}\n{m.get('snippet', '')}")
        return '\n\n---\n\n'.join(parts)
    except Exception:
        return ''

# ── Draft reply via Claude ────────────────────────────────────────────────────

def draft_reply(email: dict, thread_context: str, direction: str = '') -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    direction_line = f"\nDrafting direction from Nik: {direction}" if direction else ''

    prompt = f"""You are drafting a reply email for Nik, CEO of Surfaize. Write in his voice: direct, crisp, warm, startup-casual. No filler phrases.

Email to reply to:
From: {email['from']}
Subject: {email['subject']}
Message: {email['snippet']}

Thread context:
{thread_context}
{direction_line}

Write ONLY the email body (no subject line, no "From:", no metadata). End with:
Best, Nik

Keep it under 100 words unless the content demands more."""

    response = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=500,
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
    seen = load_seen()
    creds = get_creds()
    service = build('gmail', 'v1', credentials=creds)

    emails = fetch_new_emails(service)
    new_priority = []

    for email in emails:
        if email['id'] in seen:
            continue
        if not is_priority(email['from'], email['subject'], email['in_reply_to']):
            seen.add(email['id'])
            continue
        new_priority.append(email)

    for email in new_priority:
        print(f"New priority email: {email['from']} — {email['subject']}")

        # Fetch thread for context
        thread_context = fetch_thread(service, email['thread_id'])

        # Draft reply
        draft = draft_reply(email, thread_context)

        # Extract sender name
        sender = email['from'].split('<')[0].strip().strip('"') or email['from']

        # Save as numbered pending reply
        num = save_pending_entry({
            'message_id': email['id'],
            'thread_id': email['thread_id'],
            'to': email['from'],
            'subject': email['subject'],
            'in_reply_to': email['message_id'],
            'draft': draft,
        })

        # Send Telegram notification
        notification = (
            f"📬 #{num} {sender} — {email['subject']}\n"
            f"{email['snippet'][:200]}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Draft reply:\n\n"
            f"{draft}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Reply 'send {num}', 'edit {num}: [direction]', or ignore."
        )
        send_telegram(notification)
        seen.add(email['id'])

    save_seen(seen)
    if new_priority:
        print(f"Notified for {len(new_priority)} email(s).")
    else:
        print("No new priority emails.")

if __name__ == '__main__':
    main()
