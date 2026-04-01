#!/usr/bin/env python3 -u
"""
Telegram bot listener — two-way agent interface.
Polls for messages, routes to scripts or Claude API, replies in Telegram.
Runs as a systemd service on the VM.

Security: only responds to the authorized TELEGRAM_CHAT_ID.
"""

import os
import sys
import json
import time
import subprocess
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import anthropic

# ── Config ────────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN   = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
ANTHROPIC_KEY    = os.environ['ANTHROPIC_API_KEY']

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
TOOLS_DIR = os.path.join(BASE_DIR, 'tools')
CONTEXT_FILE = os.path.join(BASE_DIR, 'context', 'personal.md')
PYTHON = os.path.join(BASE_DIR, '.venv', 'bin', 'python')

TELEGRAM_API = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}'

# ── Telegram helpers ──────────────────────────────────────────────────────────

def send_message(text: str):
    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
    for chunk in chunks:
        requests.post(f'{TELEGRAM_API}/sendMessage', json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': chunk,
        })

def send_email_direct(to: str, subject: str, body: str) -> str:
    """Send email directly via Gmail API without subprocess."""
    import base64
    from email.mime.text import MIMEText
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    GOOGLE_CLIENT_ID     = os.environ['GOOGLE_CLIENT_ID']
    GOOGLE_CLIENT_SECRET = os.environ['GOOGLE_CLIENT_SECRET']
    GOOGLE_REFRESH_TOKEN = os.environ['GOOGLE_REFRESH_TOKEN']

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
    service = build('gmail', 'v1', credentials=creds)
    msg = MIMEText(body, 'plain')
    msg['to'] = to
    msg['subject'] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = service.users().messages().send(userId='me', body={'raw': raw}).execute()
    return result.get('id', '')


def get_updates(offset: int) -> list[dict]:
    try:
        resp = requests.get(f'{TELEGRAM_API}/getUpdates', params={
            'offset': offset,
            'timeout': 60,
            'allowed_updates': ['message'],
        }, timeout=70)
        return resp.json().get('result', [])
    except Exception:
        return []

# ── Script runner ─────────────────────────────────────────────────────────────

def run_script(script_name: str) -> str:
    """Run a tool script and return stdout. The script sends its own Telegram message."""
    result = subprocess.run(
        [PYTHON, os.path.join(TOOLS_DIR, script_name)],
        capture_output=True, text=True, cwd=BASE_DIR
    )
    if result.returncode != 0:
        return f"Error running {script_name}:\n{result.stderr[:500]}"
    return result.stdout.strip()

def run_clickup_update(args: list[str]) -> str:
    result = subprocess.run(
        [PYTHON, os.path.join(TOOLS_DIR, 'update_clickup.py')] + args,
        capture_output=True, text=True, cwd=BASE_DIR
    )
    return (result.stdout + result.stderr).strip()

def run_clickup_fetch() -> str:
    result = subprocess.run(
        [PYTHON, os.path.join(TOOLS_DIR, 'fetch_clickup.py')],
        capture_output=True, text=True, cwd=BASE_DIR
    )
    return result.stdout.strip()

# ── Claude API handler ────────────────────────────────────────────────────────

def load_context() -> str:
    try:
        with open(CONTEXT_FILE) as f:
            return f.read()
    except Exception:
        return ''

PENDING_FILE = os.path.join(BASE_DIR, '.tmp', 'pending_reply.json')

def load_all_pending() -> dict:
    try:
        with open(PENDING_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def get_pending(num: int) -> dict | None:
    return load_all_pending().get(str(num))

def remove_pending(num: int):
    pending = load_all_pending()
    pending.pop(str(num), None)
    with open(PENDING_FILE, 'w') as f:
        json.dump(pending, f, indent=2)

def update_pending(num: int, data: dict):
    pending = load_all_pending()
    pending[str(num)] = data
    with open(PENDING_FILE, 'w') as f:
        json.dump(pending, f, indent=2)

def handle_send_pending(num: int) -> str:
    entry = get_pending(num)
    if not entry:
        return f"No pending reply #{num}."
    try:
        msg_id = send_email_direct(
            to=entry['to'],
            subject=entry['subject'],
            body=entry['draft'],
        )
        remove_pending(num)
        print(f"Sent pending reply #{num}: {msg_id}")
        return f"#{num} sent to {entry['to'].split('<')[0].strip()}."
    except Exception as e:
        return f"Send failed: {e}"

def handle_redraft_pending(num: int, direction: str) -> str:
    entry = get_pending(num)
    if not entry:
        return f"No pending reply #{num}."
    try:
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        prompt = f"""Redraft this email reply for Nik (CEO of Surfaize). Direct, crisp, no filler.

Original email was to: {entry['to']}
Subject: {entry['subject']}

Previous draft:
{entry['draft']}

New direction from Nik: {direction}

Write ONLY the new email body. End with: Best, Nik"""

        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=500,
            messages=[{'role': 'user', 'content': prompt}]
        )
        new_draft = response.content[0].text.strip()
        entry['draft'] = new_draft
        update_pending(num, entry)

        return (
            f"#{num} new draft:\n\n{new_draft}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Reply 'send {num}' to send or 'edit {num}: [direction]' to redraft again."
        )
    except Exception as e:
        return f"Redraft failed: {e}"


def fetch_recent_emails_summary() -> str:
    """Fetch recent emails for live context in Claude queries."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=os.environ['GOOGLE_REFRESH_TOKEN'],
            token_uri='https://oauth2.googleapis.com/token',
            client_id=os.environ['GOOGLE_CLIENT_ID'],
            client_secret=os.environ['GOOGLE_CLIENT_SECRET'],
            scopes=[
                'https://www.googleapis.com/auth/gmail.readonly',
                'https://www.googleapis.com/auth/gmail.send',
                'https://www.googleapis.com/auth/calendar.readonly',
            ],
        )
        creds.refresh(Request())
        service = build('gmail', 'v1', credentials=creds)
        results = service.users().messages().list(
            userId='me',
            q='newer_than:2d -category:promotions -category:social -from:noreply -from:notifications',
            maxResults=15
        ).execute()
        messages = results.get('messages', [])
        lines = []
        for msg in messages:
            detail = service.users().messages().get(
                userId='me', id=msg['id'], format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()
            headers = {h['name']: h['value'] for h in detail['payload']['headers']}
            read = 'UNREAD' not in detail.get('labelIds', [])
            status = 'read' if read else 'UNREAD'
            lines.append(f"[{status}] {headers.get('From','')} — {headers.get('Subject','')} ({headers.get('Date','')})")
        return '\n'.join(lines) if lines else 'No recent emails.'
    except Exception as e:
        return f'Email fetch unavailable: {e}'


def ask_claude(user_message: str, conversation_history: list[dict]) -> tuple[str, list[str]]:
    """
    Send message to Claude with full agent context.
    Returns (reply_text, list_of_actions_to_execute).
    Claude can request script execution using: [ACTION: <command>]
    """
    context = load_context()
    clickup = run_clickup_fetch()
    recent_emails = fetch_recent_emails_summary()

    system = f"""You are the personal Executive Assistant for Nik, CEO of Surfaize (AI OS for e-commerce brands, seed stage, Berlin). You are running as a Telegram bot on a VM.

Personal context:
{context}

Current ClickUp board:
{clickup}

Recent emails (last 2 days):
{recent_emails}

You can execute actions by including them on their own line in exactly this format:
[ACTION: morning] — trigger full morning briefing (it will be sent to Telegram separately)
[ACTION: evening] — trigger full evening briefing
[ACTION: clickup done --name "task name"] — mark a task complete
[ACTION: clickup create --name "task name" --assignee nik] — create a task
[ACTION: clickup update --name "task name" --status "in progress"] — update a task status
[ACTION: clickup find --name "task name"] — find a task
[EMAIL: {{"to": "email@address.com", "subject": "Subject here", "body": "Full email body here"}}] — send an email (use this exact JSON format, body can span multiple lines but must be valid JSON string)

Rules:
- NEVER execute clickup write actions (done, create, update) without first confirming with the user.
- NEVER include [ACTION: send_email ...] in the same message as a draft. Always show the full draft first, then ask "Shall I send this? (yes/no)". Only include [ACTION: send_email ...] in a follow-up response AFTER the user explicitly says yes/send/confirm.
- For read actions (find, morning, evening, kanban) execute immediately.
- Be direct and crisp — this is Telegram, not email.
- Plain text only, no markdown.
- Today's date is {time.strftime('%A, %d %B %Y')}.
- Nik's Q1 priorities: first paying customers, strategy execution, 100k MRR in 6 months.
"""

    messages = conversation_history + [{'role': 'user', 'content': user_message}]

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    response = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=1000,
        system=system,
        messages=messages,
    )
    reply = response.content[0].text

    # Parse [ACTION: ...] and [EMAIL: {...}] tags
    import re
    actions = []
    clean_reply = reply

    # Extract [EMAIL: {...}] blocks (may span multiple lines)
    email_pattern = re.compile(r'\[EMAIL:\s*(\{.*?\})\]', re.DOTALL)
    for match in email_pattern.finditer(reply):
        actions.append(('email', match.group(1)))
    clean_reply = email_pattern.sub('', clean_reply)

    # Extract [ACTION: ...] single-line tags
    action_pattern = re.compile(r'\[ACTION:\s*(.+?)\]')
    for match in action_pattern.finditer(reply):
        actions.append(('action', match.group(1).strip()))
    clean_reply = action_pattern.sub('', clean_reply)

    clean_reply = clean_reply.strip()
    return clean_reply, actions

def execute_action(action: tuple) -> str:
    """Execute a parsed action tuple: ('action', cmd) or ('email', json_str)."""
    kind, payload = action

    if kind == 'email':
        try:
            data = json.loads(payload)
            msg_id = send_email_direct(data['to'], data['subject'], data['body'])
            print(f"Email sent: {msg_id} to {data['to']}")
            return f"Email sent to {data['to']}."
        except Exception as e:
            print(f"Email error: {e}")
            return f"Email failed: {e}"

    # kind == 'action'
    cmd = payload
    if cmd == 'morning':
        run_script('morning_briefing.py')
        return '☕ Morning briefing sent.'
    elif cmd == 'evening':
        run_script('evening_briefing.py')
        return '🌙 Evening briefing sent.'
    elif cmd.startswith('clickup '):
        args = cmd[8:].split()
        return run_clickup_update(args)
    return f"Unknown action: {cmd}"

# ── Conversation state ─────────────────────────────────────────────────────────

# Keep last N messages for context
MAX_HISTORY = 10
conversation_history: list[dict] = []

def add_to_history(role: str, content: str):
    conversation_history.append({'role': role, 'content': content})
    # Keep history bounded
    while len(conversation_history) > MAX_HISTORY * 2:
        conversation_history.pop(0)

# ── Message router ────────────────────────────────────────────────────────────

def handle_message(text: str) -> str:
    text_stripped = text.strip()
    text_lower = text_stripped.lower()

    # Handle numbered pending email replies: 'send 1', 'edit 2: direction'
    import re as _re
    send_match = _re.match(r'^send\s+(\d+)$', text_lower)
    edit_match = _re.match(r'^edit\s+(\d+):\s*(.+)$', text_stripped, _re.IGNORECASE)
    if send_match:
        return handle_send_pending(int(send_match.group(1)))
    if edit_match:
        return handle_redraft_pending(int(edit_match.group(1)), edit_match.group(2))

    # Direct script commands — no confirmation needed
    if text_lower in ('morning', '/morning'):
        send_message('Running morning briefing...')
        run_script('morning_briefing.py')
        return None  # Script sends its own message

    if text_lower in ('evening', '/evening'):
        send_message('Running evening briefing...')
        run_script('evening_briefing.py')
        return None

    if text_lower in ('tasks', 'kanban', '/tasks'):
        return run_clickup_fetch()

    # Everything else → Claude
    add_to_history('user', text_stripped)
    reply, actions = ask_claude(text_stripped, conversation_history[:-1])

    # Execute any actions Claude requested
    action_results = []
    for action in actions:
        result = execute_action(action)
        if result:
            action_results.append(result)

    # Build final reply
    parts = []
    if reply:
        parts.append(reply)
    if action_results:
        parts.extend(action_results)

    final_reply = '\n\n'.join(parts) if parts else None
    if final_reply:
        add_to_history('assistant', final_reply)
    return final_reply

# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    print('Telegram listener started.')
    send_message('Agent online. Send me a message.')

    offset = 0
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update['update_id'] + 1
            message = update.get('message', {})
            chat_id = str(message.get('chat', {}).get('id', ''))
            text = message.get('text', '').strip()

            # Security: ignore messages from unauthorized chats
            if chat_id != TELEGRAM_CHAT_ID:
                print(f'Ignoring message from unauthorized chat: {chat_id}')
                continue

            if not text:
                continue

            print(f'Message: {text}')
            try:
                reply = handle_message(text)
                if reply:
                    send_message(reply)
            except Exception as e:
                send_message(f'Error: {e}')
                print(f'Error handling message: {e}')

if __name__ == '__main__':
    main()
