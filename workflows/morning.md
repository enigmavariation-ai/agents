# Workflow: /morning — Daily Morning Briefing

## Objective
Produce a complete morning briefing: today's calendar, ranked email priorities, Telegram highlights, relevant news, top 3 priorities for the day, and a co-founder update draft.

## Trigger
`/morning`

## Required Inputs
- Today's date and day of week
- `context/personal.md` (identity, co-founders, news topics, key relationships)

## Steps

Execute in this exact order:

1. **Load personal context** — Read `context/personal.md`. Extract: co-founder names, key relationships, news topics, timezone.

2. **Fetch calendar** — Use the `gcal` MCP to get all events for today. Also pull tomorrow's first event (to flag early starts).
   - Note each event's time, title, and attendees
   - Flag: conflicts, back-to-backs, missing prep materials, or events with no description

3. **Fetch emails** — Use the `gmail` MCP to fetch unread emails from the last 18 hours.
   - Rank by urgency using prioritization logic (see CLAUDE.md)
   - Skip: newsletters, receipts, automated notifications, marketing
   - Cap at 5 items

4. **Fetch Telegram** — Use the `telegram` MCP to fetch unread messages.
   - Only include threads that need a response or a decision
   - Skip: broadcast channels, bots, read-only groups

5. **Fetch ClickUp tasks** — Run `python3 tools/fetch_clickup.py` to get all Team Kanban tasks.
   - Show Nik's tasks (IN PROGRESS, BLOCKED, TO DO) grouped under his name
   - Show Jelena's tasks grouped under her name
   - Show Fabi's tasks grouped under his name
   - Flag anything BLOCKED across the whole team — surface the blocker if visible
   - Skip RECURRING tasks and DONE tasks

6. **Fetch news** — Run web searches on the primary and secondary topics from `context/personal.md`.
   - Do NOT include the user's name, company name, or contact details in queries
   - Cap at 3 items
   - Prioritize: competitive landscape, funding market, AI/tech, regulation

6. **Synthesize top 3 priorities** — Based on calendar urgency, email triage, and Telegram, identify the three things that cannot wait today. State why each one can't wait.

7. **Draft co-founder update** — Run the `/cofounder` workflow and embed the output in the briefing.

8. **Select quotes** — Choose one philosophical quote and one motivational quote following the rules in CLAUDE.md. Never repeat a thinker used in the previous 7 days.

## Output Format

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
☕ MORNING BRIEFING — [Weekday, Date]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💭 TO START YOUR DAY
Philosophy: "[Quote]" — [Author, work if known]
Drive:      "[Quote]" — [Author]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 CALENDAR
[Time] [Title]
  → [Attendees / what to prepare — 1 line max]
⚠️ [Flag conflicts, back-to-backs, or missing prep]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📬 EMAIL PRIORITIES
1. [Sender] — [Subject]
   → [Why it matters / action needed]
(Max 5)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 TELEGRAM
- [Person / chat]: [What needs attention]
(Only threads needing response or decision)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ TEAM KANBAN — [X] total tasks
Nik: [X in progress / X to do / X blocked]
- [🔄/📋/🚫] [task]
- ✅ Recently completed: [task] (if completed in last 24h)

Jelena: [X in progress / X to do / X blocked]
- [🔄/📋/🚫] [task]
- ✅ Recently completed: [task] (if completed in last 24h)

Fabi: [X in progress / X to do / X blocked]
- [🔄/📋/🚫] [task]
- ✅ Recently completed: [task] (if completed in last 24h)

⚠️ BLOCKED: [task] — [who / why if known]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📰 NEWS THAT MATTERS
- [Headline] — [Why relevant, 1 sentence]
(3 items max)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚦 TODAY'S TOP 3
1. [Priority] — [Why it can't wait]
2. [Priority] — [Why it can't wait]
3. [Priority] — [Why it can't wait]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✉️ CO-FOUNDER UPDATE (draft — edit before sending)
[Output of /cofounder workflow]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Hard Rules
- NEVER send the co-founder update automatically. It is always a draft.
- If Telegram MCP is unavailable, skip that section and note it.
- If calendar is empty, say so — don't fabricate events.
- Keep the full briefing readable in under 2 minutes.

## Edge Cases
- **No unread emails**: Say "Inbox clear — no priority items."
- **No calendar events**: Say "No scheduled events today."
- **MCP unavailable**: Note which source is unavailable and continue with the rest.
- **News search returns nothing relevant**: Omit the section rather than padding with irrelevant items.
