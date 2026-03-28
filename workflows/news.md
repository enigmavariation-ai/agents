# Workflow: /news — Quick News Brief

## Objective
Surface 3–5 relevant news items on a given topic or default topic set. One-line summary per item explaining why it matters.

## Trigger
`/news [topic]`

If no topic is given, use the default topics from `context/personal.md` (primary and secondary news topics).

## Required Inputs
- Topic (from command, or default from `context/personal.md`)
- Web search (built-in)

## Steps

1. **Determine topics** — If a topic was specified, use it. Otherwise load primary + secondary topics from `context/personal.md`.

2. **Run searches** — Search each topic separately. Use general, non-identifying queries.
   - NEVER include the user's name, company name, or contact details in any query.
   - Focus queries on: competitive landscape, funding/market moves, AI/tech developments, regulation.

3. **Filter results** — Keep only items from the last 72 hours unless no recent results exist. Prefer primary sources (TechCrunch, Bloomberg, FT, Reuters, company blogs) over aggregators.

4. **Select top items** — Pick 3–5 items that are most relevant to the user's industry, competitors, or quarterly priorities. Cut anything generic or already widely known.

5. **Write summaries** — For each item: headline + one sentence on why it matters specifically to the user's context.

## Output Format

📰 NEWS — [Date]

- **[Headline]** — [Why it matters, 1 sentence. Source: Publication]
- **[Headline]** — [Why it matters, 1 sentence. Source: Publication]
- **[Headline]** — [Why it matters, 1 sentence. Source: Publication]

*(3–5 items max)*

## Hard Rules
- Maximum 5 items. Quality over quantity.
- NEVER include personal identifiers in search queries.
- Only flag items that are genuinely relevant — don't pad with noise.
- If searching for competitor news, use the competitor's public name only.

## Edge Cases
- **No recent results**: Broaden the time window to 7 days; note this in the output
- **Topic too broad**: Narrow it to the most likely interpretation and note what you searched
- **No topic in personal.md**: Ask the user what topics to monitor before proceeding — don't guess
