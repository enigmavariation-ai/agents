# Workflow: ClickUp Task Management

## Objective
Create, update, close, and propose ClickUp tasks on behalf of Nik and his co-founders. All writes require explicit confirmation before executing — never create or modify tasks silently.

## Trigger
Conversational commands, e.g.:
- "Mark [task] as done"
- "Create a task for Fabi: [task name]"
- "Move [task] to in progress"
- "Create these tasks for the team: [list]"
- "Propose tasks based on our priorities"

## Team Member Reference
- Nik / Niklas: ID 106594777
- Jelena / Jele: ID 106594776
- Fabi / Fabian: ID 278590897

## Steps

### For single task operations (create / update / close):

1. **Parse the request** — Extract: task name, assignee, desired status, priority if mentioned.
2. **Confirm before writing** — Show the user what will be created/changed:
   - "I'll create: [name] → assigned to [person], status: to do. Confirm?"
   - "I'll mark [task name] as done. Confirm?"
3. **Execute** — Run `python3 tools/update_clickup.py [command] [args]`
4. **Confirm result** — Show the outcome.

### For bulk task creation (list of tasks):

1. **Parse the list** — Extract all tasks with assignees, statuses, priorities.
2. **Present the full list** for confirmation before creating anything.
3. **Execute bulk** — Run `python3 tools/update_clickup.py bulk --json-file .tmp/tasks.json`
4. **Report** — List all created tasks with their IDs.

### For task proposals (proactive suggestions):

1. **Load context** — Read `context/personal.md` (quarterly priorities) and run `python3 tools/fetch_clickup.py` (current board state).
2. **Identify gaps** — Cross-reference current tasks against priorities. Look for:
   - Missing tasks that would directly advance a quarterly priority
   - Tasks that are blocked and need a prerequisite task
   - Tasks assigned to Nik that could be delegated to Jelena or Fabi
   - Recurring patterns that should be systematized
3. **Propose** — Present a numbered list of suggested tasks with assignee and rationale.
4. **Wait for confirmation** — User approves individual items ("add 1, 3, 5") or all ("add all").
5. **Create approved tasks only.**

## Hard Rules
- NEVER create or modify tasks without explicit user confirmation.
- NEVER assign tasks to someone without confirming the assignee.
- When finding a task by name, if multiple matches exist, ask the user to clarify.
- Always show what will happen before it happens.

## Examples

**Close a task:**
User: "Mark Set up Surfaize UG as done"
→ "Marking [86c8xxx] Set up Surfaize's UG as done. Confirm?"
→ User: "yes"
→ `python3 tools/update_clickup.py done --name "Set up Surfaize UG"`

**Create a task:**
User: "Create a task for Fabi: scope the pricing page"
→ "Creating: Scope the pricing page → Fabi, status: to do. Confirm?"
→ `python3 tools/update_clickup.py create --name "Scope the pricing page" --assignee fabi`

**Bulk create:**
User: "Add these tasks for Jelena: write case study, update website copy, prep demo script"
→ Show full list with assignee + status
→ On confirm: create all three

**Propose tasks:**
User: "Propose tasks based on our priorities"
→ Read priorities + current board
→ Return numbered proposal list
→ Create only what user approves
