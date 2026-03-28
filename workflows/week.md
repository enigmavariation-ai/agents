# Workflow: /week — Weekly Preview

## Objective
Produce a structured weekly overview: key meetings, deadlines, focus priorities, and schedule risks. Typically run Sunday evening or Monday morning.

## Trigger
`/week`

## Required Inputs
- `gcal` MCP — all events for the current Mon–Sun week
- `gmail` MCP — any emails with explicit deadlines mentioned this week
- `context/personal.md` — quarterly priorities, key relationships

## Steps

1. **Determine week boundaries** — Calculate Monday and Sunday of the current week based on today's date and CET timezone.

2. **Fetch all calendar events** — Use `gcal` MCP to pull the full week. Group by day.

3. **Identify key meetings** — Flag meetings that require prep: investor calls, customer demos, co-founder strategy sessions, external stakeholders. Note what prep is likely needed.

4. **Scan for deadlines** — Use `gmail` MCP to search for emails mentioning deadlines this week (keywords: "by", "due", "deadline", "EOD", "Friday", specific dates).

5. **Map focus priorities** — Cross-reference the week's commitments against the quarterly priorities in `context/personal.md`. Identify the top 3 focus areas that will move the needle most.

6. **Flag risks** — Look for: back-to-back days with no buffer, days over-scheduled (>5 hours of meetings), missing prep time before key meetings, conflicts.

## Output Format

📆 WEEK OF [Monday Date] – [Friday Date]

**Key Meetings**
[Day] [Time] — [Meeting] — [Prep needed, 1 line]
[Day] [Time] — [Meeting] — [Prep needed, 1 line]

**Deadlines**
- [Item] — due [date]
- [Item] — due [date]
(If none found: "No explicit deadlines identified — check manually.")

**Focus Priorities**
1. [Item]
2. [Item]
3. [Item]

**Watch Out For**
- [Risk or conflict — e.g., "Tuesday has 6h of meetings with no buffer"]
- [Missing prep time before [meeting]]
- [Back-to-back on [day]]

## Hard Rules
- NEVER create, modify, or suggest creating calendar events without explicit approval.
- Do not fabricate deadlines — only surface what's explicitly mentioned in emails or calendar descriptions.
- Keep the full output skimmable in under 60 seconds.

## Edge Cases
- **Sparse week**: Still produce the output — note it's a light week and suggest using the space intentionally
- **No deadlines found in email**: Say "No explicit deadlines found in email — verify manually"
- **Public holidays**: Note them if they affect the work week
