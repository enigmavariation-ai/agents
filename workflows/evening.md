# Workflow: /evening — Next Day Preview

## Objective
End-of-day briefing: what's on tomorrow, what's unfinished today, what to prepare tonight so tomorrow starts clean.

## Trigger
`/evening`

## Required Inputs
- `context/personal.md` — co-founders, key relationships, priorities
- `gcal` MCP — tomorrow's full calendar
- `gmail` MCP — unresolved threads from today + anything arriving this evening
- ClickUp — `python3 tools/fetch_clickup.py`

## Steps

1. **Load context** — Read `context/personal.md`.

2. **Fetch tomorrow's calendar** — Use `gcal` MCP for the full next day (midnight to midnight, Berlin time).
   - Identify meetings that need prep
   - Flag back-to-backs, early starts, or heavy days
   - Note any meetings with external stakeholders (investors, customers, advisors)

3. **Scan open email threads** — Use `gmail` MCP to find:
   - Threads where a reply from Nik is overdue (sent > 24h ago with no response from him)
   - Anything that arrived today that still needs action
   - Commitments made by Nik in email that are due tomorrow

4. **Review ClickUp** — Run `python3 tools/fetch_clickup.py`. Highlight:
   - Tasks in progress that should be closed today
   - Tasks assigned to Nik that are due tomorrow
   - Anything blocked that will affect tomorrow's work

5. **Draft tomorrow's priorities** — Based on calendar + open threads + ClickUp, propose the top 3 things to attack first tomorrow morning.

6. **Flag anything to do tonight** — Is there prep, a reply, or a decision that needs to happen before bed to make tomorrow smoother?

## Output Format

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌙 EVENING BRIEFING — [Weekday, Date]
Prep for [Tomorrow's Weekday]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 TOMORROW'S CALENDAR
[Time] [Event]
  -> [Who / what to prepare]
⚠️ [Flag heavy days, back-to-backs, early starts]
(If no events: "Clear day — use it.")

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📬 OPEN EMAIL THREADS
- [Sender] — [Subject] — [What's needed / how long it's been waiting]
(Only threads needing action before tomorrow. Skip if none.)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ CLICKUP — CLOSE OUT TODAY
- [Task] — [why it should be closed or moved forward tonight]
(Only tasks that realistically could/should be done tonight.)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚦 TOMORROW'S TOP 3
1. [Priority] — [Why first]
2. [Priority] — [Why second]
3. [Priority] — [Why third]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌙 DO TONIGHT
- [Action] — [Why it matters for tomorrow]
(Keep this short — max 3 items. If nothing urgent: "Nothing blocking. Rest.")

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Hard Rules
- NEVER send or schedule anything automatically.
- Keep the full briefing under 2 minutes to read.
- "Do tonight" should be ruthlessly filtered — only things that genuinely unblock tomorrow.
- If tomorrow is a weekend day, still run it but note it's a rest day unless calendar says otherwise.

## Edge Cases
- **Empty calendar tomorrow**: Flag it as a focus day — suggest using it for deep work on top priorities
- **Back-to-back day tomorrow**: Flag the lack of buffer and suggest what to prepare in advance
- **No open threads**: Say "Inbox clear" and skip that section
