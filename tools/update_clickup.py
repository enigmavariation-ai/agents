#!/usr/bin/env python3
from __future__ import annotations
"""
ClickUp write operations for the Surfaize EA agent.
Supports: create task, update status, assign, close task.

Usage:
  python3 tools/update_clickup.py create --name "Task name" --assignee fabi --status "to do"
  python3 tools/update_clickup.py done --task-id 86c9045uj
  python3 tools/update_clickup.py update --task-id 86c9045uj --status "in progress"
  python3 tools/update_clickup.py find --name "Review OTTO Deck"
"""

import os
import sys
import json
import argparse
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

API_TOKEN = os.getenv('CLICKUP_API_TOKEN')
LIST_ID   = '901521517857'  # Team Kanban > List
HEADERS   = {'Authorization': API_TOKEN, 'Content-Type': 'application/json'}

MEMBERS = {
    'nik':    106594777,
    'niklas': 106594777,
    'jelena': 106594776,
    'jele':   106594776,
    'fabi':   278590897,
    'fabian': 278590897,
}

STATUSES = {
    'todo':        'to do',
    'to do':       'to do',
    'inprogress':  'in progress',
    'in progress': 'in progress',
    'blocked':     'blocked',
    'review':      'in progress',
    'done':        'complete',
    'closed':      'complete',
    'complete':    'complete',
}


def resolve_assignee(name: str) -> int:
    key = name.lower().strip()
    if key not in MEMBERS:
        print(f"Unknown assignee '{name}'. Valid: {', '.join(MEMBERS.keys())}", file=sys.stderr)
        sys.exit(1)
    return MEMBERS[key]


def find_task(name: str) -> dict | None:
    """Find a task by partial name match."""
    resp = requests.get(
        f'https://api.clickup.com/api/v2/list/{LIST_ID}/task',
        headers=HEADERS,
        params={'archived': 'false', 'include_closed': 'false'}
    )
    resp.raise_for_status()
    tasks = resp.json().get('tasks', [])
    name_lower = name.lower()
    matches = [t for t in tasks if name_lower in t['name'].lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Multiple matches for '{name}':")
        for t in matches:
            print(f"  {t['id']} — {t['name']}")
        return None
    print(f"No task found matching '{name}'")
    return None


def create_task(name: str, assignee: str | None, status: str, priority: str | None, description: str | None) -> dict:
    payload = {
        'name': name,
        'status': STATUSES.get(status.lower().strip(), status),
    }
    if assignee:
        payload['assignees'] = [resolve_assignee(assignee)]
    if priority:
        levels = {'urgent': 1, 'high': 2, 'normal': 3, 'low': 4}
        payload['priority'] = levels.get(priority.lower(), 3)
    if description:
        payload['description'] = description

    resp = requests.post(
        f'https://api.clickup.com/api/v2/list/{LIST_ID}/task',
        headers=HEADERS,
        json=payload
    )
    resp.raise_for_status()
    task = resp.json()
    print(f"Created: [{task['id']}] {task['name']} — {task['status']['status']}")
    return task


def update_task(task_id: str, status: str | None, assignee: str | None, name: str | None) -> dict:
    payload = {}
    if status:
        payload['status'] = STATUSES.get(status.lower().strip(), status)
    if assignee:
        payload['assignees'] = {'add': [resolve_assignee(assignee)], 'rem': []}
    if name:
        payload['name'] = name

    resp = requests.put(
        f'https://api.clickup.com/api/v2/task/{task_id}',
        headers=HEADERS,
        json=payload
    )
    resp.raise_for_status()
    task = resp.json()
    print(f"Updated: [{task['id']}] {task['name']} — {task['status']['status']}")
    return task


def close_task(task_id: str) -> dict:
    return update_task(task_id, status='done', assignee=None, name=None)


def bulk_create(tasks: list[dict]) -> list:
    """Create multiple tasks from a list of dicts with keys: name, assignee, status, priority, description."""
    created = []
    for t in tasks:
        task = create_task(
            name=t.get('name', ''),
            assignee=t.get('assignee'),
            status=t.get('status', 'to do'),
            priority=t.get('priority'),
            description=t.get('description'),
        )
        created.append(task)
    return created


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command')

    # create
    p_create = sub.add_parser('create')
    p_create.add_argument('--name', required=True)
    p_create.add_argument('--assignee', default=None)
    p_create.add_argument('--status', default='to do')
    p_create.add_argument('--priority', default=None)
    p_create.add_argument('--description', default=None)

    # done
    p_done = sub.add_parser('done')
    p_done.add_argument('--task-id', default=None)
    p_done.add_argument('--name', default=None)

    # update
    p_update = sub.add_parser('update')
    p_update.add_argument('--task-id', default=None)
    p_update.add_argument('--name', default=None)
    p_update.add_argument('--status', default=None)
    p_update.add_argument('--assignee', default=None)
    p_update.add_argument('--new-name', default=None)

    # find
    p_find = sub.add_parser('find')
    p_find.add_argument('--name', required=True)

    # bulk
    p_bulk = sub.add_parser('bulk')
    p_bulk.add_argument('--json-file', required=True, help='Path to JSON file with task list')

    args = parser.parse_args()

    if not API_TOKEN:
        print('Missing CLICKUP_API_TOKEN in .env', file=sys.stderr)
        sys.exit(1)

    if args.command == 'create':
        create_task(args.name, args.assignee, args.status, args.priority, args.description)

    elif args.command == 'done':
        task_id = args.task_id
        if not task_id and args.name:
            task = find_task(args.name)
            if task:
                task_id = task['id']
        if task_id:
            close_task(task_id)

    elif args.command == 'update':
        task_id = args.task_id
        if not task_id and args.name:
            task = find_task(args.name)
            if task:
                task_id = task['id']
        if task_id:
            update_task(task_id, args.status, args.assignee, args.new_name)

    elif args.command == 'find':
        task = find_task(args.name)
        if task:
            print(json.dumps({
                'id': task['id'],
                'name': task['name'],
                'status': task['status']['status'],
                'assignees': [a['username'] for a in task.get('assignees', [])],
            }, indent=2))

    elif args.command == 'bulk':
        with open(args.json_file) as f:
            tasks = json.load(f)
        bulk_create(tasks)

    else:
        parser.print_help()
