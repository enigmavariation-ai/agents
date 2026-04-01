#!/usr/bin/env python3
"""
One-time script to generate Google OAuth refresh token.
Run this once locally, then store the token as a GitHub Secret.

Usage: python3 tools/get_google_token.py
"""

import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import google.oauth2.credentials

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.readonly',
]

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')

def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print("ERROR: credentials.json not found in /Users/rnf/Agents/")
        print("Download it from Google Cloud Console first.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': list(creds.scopes),
    }

    output_path = os.path.join(os.path.dirname(__file__), '..', 'token.json')
    with open(output_path, 'w') as f:
        json.dump(token_data, f, indent=2)

    print("\n✅ Token saved to token.json")
    print("\nAdd these as GitHub Secrets:")
    print(f"  GOOGLE_REFRESH_TOKEN  = {creds.refresh_token}")
    print(f"  GOOGLE_CLIENT_ID      = {creds.client_id}")
    print(f"  GOOGLE_CLIENT_SECRET  = {creds.client_secret}")

if __name__ == '__main__':
    main()
