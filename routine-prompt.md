You are building today's "Morning Edition" magazine — a daily curated digest from Hacker News AND Pinboard Popular, committed to a GitHub repo that auto-deploys via GitHub Pages to daily.rhymeswithjazz.com.

Your job is to CURATE stories and output a JSON file. A Python template script handles all HTML rendering — you do NOT generate HTML.

## Step 1: Compute Today's Date

```bash
python3 -c "from datetime import datetime; d=datetime.now(); print(d.strftime('%Y-%m-%d'))"
```

Save the output as YYYY-MM-DD for use in filenames.

## Step 2: Fetch Stories from BOTH Sources

### Hacker News
Fetch the top 40 story IDs from the Hacker News API, then fetch each story's details:

```bash
curl -s "https://hacker-news.firebaseio.com/v0/topstories.json"
```

Then for each ID: `https://hacker-news.firebaseio.com/v0/item/{id}.json`

Use a Python script to fetch all 40 in a single batch to save time.

### Pinboard Popular
Fetch the Pinboard Popular RSS feed:

```bash
curl -s "https://feeds.pinboard.in/rss/popular/"
```

Parse it as XML/RDF. Each `<item>` has a URL (rdf:about attribute), title, optional description, and tags (dc:subject or taxo:topics). Many Pinboard items have cryptic titles — infer relevance from URL, tags, and title together.

## Step 3: Curate Stories

### From Hacker News: Pick the Top 10
Filter and rank stories by these interest categories (in priority order):
- **AI tools** — LLMs, coding assistants, AI workflows, prompt engineering
- **Creative software** — photo/video/audio/design tools, creative coding
- **Dev tools** — CLI tools, editors, version control, databases, infrastructure
- **Privacy & security** — surveillance, data breaches, encryption, rights
- **Weird science** — unusual research, space, biology oddities
- **New Apple apps** — macOS and iOS software, Apple ecosystem
- **Actionable** — anything a developer could use or try today

Skip: pure politics without tech angle, sports, finance/crypto price speculation, culture war.

### From Pinboard: Pick the Top 10 EXCLUSIVES
Find the 10 best Pinboard Popular items that:
1. Match the same interest categories above
2. Are NOT already in your HN top 10 (deduplicate by URL)
3. Pinboard often surfaces niche tools, Apple utilities, dev blog posts, and creative software that HN misses

### Flag Stories
Flag stories that directly apply to the reader (they are a developer who uses Claude Code, builds with AI tools, works with Angular/TypeScript/.NET, uses Obsidian, and cares about privacy and Apple/macOS).

## Step 4: Write the JSON File

Save a JSON file to `magazines/YYYY-MM-DD.json` with this exact structure:

```json
{
  "date": "YYYY-MM-DD",
  "stories": [
    {
      "title": "Headline text",
      "url": "https://example.com/article",
      "hn_link": "https://news.ycombinator.com/item?id=12345",
      "category": "AI Tools",
      "applies": true,
      "byline": "by username · 500 points · 200 comments",
      "blurb": "2-3 sentence editorial blurb explaining WHY this story matters."
    }
  ]
}
```

**Stories 1-10** are HN stories (include `hn_link`).
**Stories 11-20** are Pinboard stories (omit `hn_link`, use byline like `"Pinboard Popular · tagged: tag1, tag2"`).

### Blurb Guidelines
- 2-3 sentences, punchy, no filler
- Explain WHY the story matters, not just what it is
- Opinionated and informed, like a tech-savvy editor's picks
- For Pinboard items with vague titles, explain what the link is actually about

## Step 5: Render and Build

Run the template renderer to generate the HTML magazine from your JSON:

```bash
python3 scripts/build-edition.py magazines/YYYY-MM-DD.json
```

Then run the build script to regenerate the index page, RSS feed, and latest redirect:

```bash
python3 scripts/build-index.py
```

## Step 6: Commit and Push DIRECTLY to main

IMPORTANT: Do NOT create a branch. Do NOT create a pull request. Commit and push directly to the main branch. This site deploys automatically via GitHub Pages on push to main, so a PR would block deployment and require manual approval, which defeats the purpose of this automated routine.

```bash
git checkout main
git add magazines/YYYY-MM-DD.json magazines/YYYY-MM-DD.html index.html feed.xml latest/index.html
git commit -m "Morning Edition — {DayName}, {Month} {Day}, {Year}"
git push origin main
```

Do NOT run `git checkout -b`, do NOT use `gh pr create`, do NOT create any branch other than main. Push directly to main.

## Important Notes
- ALWAYS compute the correct day name — use Python `strftime("%A")` — never guess
- The JSON file is small (~60 lines). The HTML rendering is handled entirely by Python. Do NOT generate HTML yourself.
- Write editorial blurbs that explain WHY a story matters, not just what it is
- Each blurb should be 2-3 sentences, punchy, no filler
- Deduplicate: if a URL appears in both HN and Pinboard, only include it once (in the HN section)
- Always run both build scripts after creating the JSON
- Always commit and push directly to main so the site deploys automatically via GitHub Pages
- Do NOT create a pull request. Do NOT create a branch. Push directly to main.
