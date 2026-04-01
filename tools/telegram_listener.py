#!/usr/bin/env python3
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

def ask_claude(user_message: str, conversation_history: list[dict]) -> tuple[str, list[str]]:
    """
    Send message to Claude with full agent context.
    Returns (reply_text, list_of_actions_to_execute).
    Claude can request script execution using: [ACTION: <command>]
    """
    context = load_context()
    clickup = run_clickup_fetch()

    system = f"""You are the personal Executive Assistant for Nik, CEO of Surfaize (AI OS for e-commerce brands, seed stage, Berlin). You are running as a Telegram bot on a VM.

Personal context:
{context}

Current ClickUp board:
{clickup}

You can execute actions by including them on their own line in exactly this format:
[ACTION: morning] — trigger full morning briefing (it will be sent to Telegram separately)
[ACTION: evening] — trigger full evening briefing
[ACTION: clickup done --name "task name"] — mark a task complete
[ACTION: clickup create --name "task name" --assignee nik] — create a task
[ACTION: clickup update --name "task name" --status "in progress"] — update a task status
[ACTION: clickup find --name "task name"] — find a task

Rules:
- NEVER execute clickup write actions (done, create, update) without first confirming with the user.
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

    # Parse any actions Claude wants to execute
    actions = []
    clean_lines = []
    for line in reply.split('\n'):
        if line.strip().startswith('[ACTION:') and line.strip().endswith(']'):
            action = line.strip()[8:-1].strip()
            actions.append(action)
        else:
            clean_lines.append(line)

    clean_reply = '\n'.join(clean_lines).strip()
    return clean_reply, actions

def execute_action(action: str) -> str:
    """Execute a parsed [ACTION: ...] command."""
    if action == 'morning':
        run_script('morning_briefing.py')
        return '☕ Morning briefing sent.'
    elif action == 'evening':
        run_script('evening_briefing.py')
        return '🌙 Evening briefing sent.'
    elif action.startswith('clickup '):
        args = action[8:].split()
        return run_clickup_update(args)
    return f"Unknown action: {action}"

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
