#!/usr/bin/env python3
"""
Fetch tasks from the Surfaize Team Kanban ClickUp list.
Returns tasks grouped by person and status, including recently completed (last 24h).

Usage: python3 tools/fetch_clickup.py
       python3 tools/fetch_clickup.py --json   # raw JSON output
"""

import os
import sys
import json
import time
import argparse
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

API_TOKEN = os.getenv('CLICKUP_API_TOKEN')
LIST_ID = '901521517857'   # Team Kanban > List

HEADERS = {'Authorization': API_TOKEN}

SKIP_STATUSES = {'recurring'}
COMPLETED_STATUSES = {'done', 'complete', 'closed', 'completed'}
ICON = {'in progress': '🔄', 'to do': '📋', 'blocked': '🚫', 'review': '👀'}

# 24 hours in milliseconds
RECENT_WINDOW_MS = 24 * 60 * 60 * 1000


def fetch_tasks(include_closed: bool = False) -> list:
    params = {
        'archived': 'false',
        'include_closed': 'true' if include_closed else 'false',
        'subtasks': 'false',
    }
    resp = requests.get(
        f'https://api.clickup.com/api/v2/list/{LIST_ID}/task',
        headers=HEADERS,
        params=params
    )
    resp.raise_for_status()
    return resp.json().get('tasks', [])


def format_for_morning(tasks: list) -> str:
    now_ms = int(time.time() * 1000)
    by_person: dict = {}

    for task in tasks:
        status = task.get('status', {}).get('status', 'unknown').lower()
        if status in SKIP_STATUSES:
            continue

        assignees = [a.get('username', '').split()[0] for a in task.get('assignees', [])]
        if not assignees:
            assignees = ['Unassigned']

        date_closed = task.get('date_closed')
        is_recent_done = (
            status in COMPLETED_STATUSES and
            date_closed and
            (now_ms - int(date_closed)) < RECENT_WINDOW_MS
        )

        # skip completed tasks older than 24h
        if status in COMPLETED_STATUSES and not is_recent_done:
            continue

        for person in assignees:
            if person not in by_person:
                by_person[person] = {'in progress': [], 'to do': [], 'blocked': [], 'review': [], 'done': []}
            bucket = status if status in by_person[person] else 'to do'
            by_person[person][bucket].append(task['name'])

    if not by_person:
        return 'No open tasks found.'

    # Count totals
    total = sum(len(v) for p in by_person.values() for v in p.values())
    lines = [f'Total: {total} tasks\n']

    person_order = ['Niklas', 'Jelena', 'Fabi']
    all_people = person_order + [p for p in sorted(by_person) if p not in person_order]

    for person in all_people:
        if person not in by_person:
            continue
        buckets = by_person[person]
        n_ip = len(buckets['in progress'])
        n_td = len(buckets['to do'])
        n_bl = len(buckets['blocked'])
        n_dn = len(buckets['done'])

        counts = []
        if n_ip: counts.append(f'{n_ip} in progress')
        if n_td: counts.append(f'{n_td} to do')
        if n_bl: counts.append(f'{n_bl} blocked')
        if n_dn: counts.append(f'{n_dn} recently done')

        lines.append(f'{person}: {" / ".join(counts) if counts else "no tasks"}')

        for status in ['in progress', 'blocked', 'to do', 'review']:
            for t in buckets[status]:
                icon = ICON.get(status, '📋')
                lines.append(f'  {icon} {t}')
        for t in buckets['done']:
            lines.append(f'  ✅ {t}')
        lines.append('')

    # Blocked summary
    blocked_all = [
        f"{t} [{p}]"
        for p in by_person
        for t in by_person[p]['blocked']
    ]
    if blocked_all:
        lines.append('⚠️ BLOCKED:')
        for b in blocked_all:
            lines.append(f'  • {b}')

    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', dest='as_json', action='store_true', help='Output raw JSON')
    args = parser.parse_args()

    if not API_TOKEN:
        print('Missing CLICKUP_API_TOKEN in .env', file=sys.stderr)
        sys.exit(1)

    # Fetch open + closed (for recent completions)
    open_tasks = fetch_tasks(include_closed=False)
    closed_tasks = fetch_tasks(include_closed=True)
    # Merge, dedup by id
    all_ids = {t['id'] for t in open_tasks}
    all_tasks = open_tasks + [t for t in closed_tasks if t['id'] not in all_ids]

    if args.as_json:
        print(json.dumps(all_tasks, indent=2))
    else:
        print('✅ TEAM KANBAN')
        print(format_for_morning(all_tasks))
