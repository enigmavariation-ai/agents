#!/usr/bin/env python3
"""
Send an email via Gmail API.

Usage:
  python3 tools/send_gmail.py --to "jelena@surfaize.com" --subject "Subject" --body "Body text"
"""
from __future__ import annotations

import os
import sys
import argparse
import base64
from email.mime.text import MIMEText

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

GOOGLE_CLIENT_ID     = os.environ['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET = os.environ['GOOGLE_CLIENT_SECRET']
GOOGLE_REFRESH_TOKEN = os.environ['GOOGLE_REFRESH_TOKEN']

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.readonly',
]


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


def send_email(to: str, subject: str, body: str) -> str:
    creds = get_creds()
    service = build('gmail', 'v1', credentials=creds)

    message = MIMEText(body, 'plain')
    message['to'] = to
    message['subject'] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(
        userId='me',
        body={'raw': raw}
    ).execute()

    return result.get('id', '')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--to', required=True)
    parser.add_argument('--subject', required=True)
    parser.add_argument('--body', required=True)
    args = parser.parse_args()

    msg_id = send_email(args.to, args.subject, args.body)
    print(f"Sent: {msg_id}")
