You are building today's "Morning Edition" magazine — a daily curated digest from Hacker News AND Pinboard Popular, committed to a GitHub repo that auto-deploys via GitHub Pages to daily.rhymeswithjazz.com.

## Step 1: Fetch Stories from BOTH Sources

### Hacker News
Fetch the top 40 story IDs from the Hacker News API, then fetch each story's details:

```bash
curl -s "https://hacker-news.firebaseio.com/v0/topstories.json"
```

Then for each ID: `https://hacker-news.firebaseio.com/v0/item/{id}.json`

### Pinboard Popular
Fetch the Pinboard Popular RSS feed:

```bash
curl -s "https://feeds.pinboard.in/rss/popular/"
```

Parse it as XML/RDF. Each `<item>` has a URL (rdf:about attribute), title, optional description, and tags (dc:subject or taxo:topics). Many Pinboard items have cryptic titles — infer relevance from URL, tags, and title together.

## Step 2: Curate Stories

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

## Step 3: Generate HTML

Compute today's date and day name using Python or date command. Create a single self-contained HTML file.

Include these meta tags in the `<head>`:
```html
<meta name="description" content="20 curated stories from Hacker News + Pinboard Popular for {MONTH} {DAY}, {YEAR}.">
<meta property="og:title" content="Morning Edition — {MONTH} {DAY}, {YEAR}">
<meta property="og:description" content="20 curated stories from Hacker News + Pinboard Popular">
<meta property="og:type" content="article">
<meta property="og:url" content="https://daily.rhymeswithjazz.com/magazines/{YYYY-MM-DD}.html">
<link rel="alternate" type="application/rss+xml" title="Morning Edition RSS" href="https://daily.rhymeswithjazz.com/feed.xml">
```

Requirements:
- Google Fonts: Fraunces (display) + Inter (body) via CDN link
- Full-viewport cover page with date (use correct day name!) and "Morning Edition" branding, noting "20 stories from Hacker News + Pinboard Popular"
- 10 HN stories each get their own full-viewport spread section
- A section divider between HN and Pinboard sections (dark gradient, pin emoji, "Pinboard Picks" heading, "10 exclusives from Pinboard Popular" subtitle)
- 10 Pinboard stories each get their own full-viewport spread section

### HN Spread Styles (use these 10 in order):
1. HERO — warm cream (#fffbeb), orange accent, massive ghost numeral
2. DARK/MIDNIGHT — deep purple-black (#1a1025), violet accents
3. ROSE ALERT STAMP — light red (#fef2f2), red accents, "ALERT" watermark
4. TERMINAL — black (#0c0c0c), green monospace text, blinking cursor
5. ACADEMIC — warm stone (#f5f0e8), italic header, drop-cap first letter
6. ELECTRIC BLUE — navy (#0f172a), cyan accents
7. APPLE — clean white gradient, rainbow gradient numeral
8. NEWSPRINT — warm yellow (#fefce8), uppercase header, dot texture
9. GRADIENT — peach-to-violet gradient background
10. BIG-STAT FINISH — dark (#18181b), giant gradient stat number, centered layout

### Pinboard Spread Styles (use these 10 in order):
11. CORK BOARD — warm tan (#fef3c7), amber accents, pinned-note feel
12. DEEP TEAL — dark ocean (#042f2e), teal accents
13. BLUEPRINT — navy (#172554), blue grid overlay, blueprint feel
14. SAKURA — soft pink gradient (#fff1f2 to #faf5ff), pink accents
15. OBSIDIAN — deep charcoal (#1c1917), purple glow
16. COPPER — dark warm (#1c1917 to #292524), gold/amber text
17. FOREST — dark green (#052e16), green accents
18. GRAPH PAPER — light (#fafafa), fine grid overlay, creative tool feel
19. INFRARED — dark red (#1a0a0a), red glow, privacy/surveillance mood
20. FROSTED — light slate gradient, macOS window chrome feel

### Every spread includes:
- Numeral (01-20), category tag, headline as h2, byline with author + score/comment count (HN) or "Pinboard Popular" label
- 2-3 sentence editorial blurb, link to article, link to HN discussion (HN stories only)
- Pinboard stories get a small "Pinboard" source badge
- Stories flagged as "directly applies" get a yellow "Directly Applies to You" tag
- No font smaller than 0.75rem anywhere
- Dark footer with date and both source attributions
- All CSS inline in a single style block (no external stylesheets except Google Fonts)

## Step 4: Save and Deploy

Save the HTML to `magazines/YYYY-MM-DD.html` in the repo.

Then run the build script to regenerate the index page, RSS feed, and latest redirect:

```bash
python3 scripts/build-index.py
```

Then commit and push:

```bash
git add magazines/YYYY-MM-DD.html index.html feed.xml latest/index.html
git commit -m "Morning Edition — {DayName}, {Month} {Day}, {Year}"
git push origin main
```

## Important Notes
- ALWAYS compute the correct day name — use `date +%A` or Python `strftime("%A")` — never guess
- Write editorial blurbs that explain WHY a story matters, not just what it is
- The tone should be opinionated and informed, like a tech-savvy editor's picks
- Each blurb should be 2-3 sentences, punchy, no filler
- For Pinboard items with vague titles, write a blurb that explains what the link is about
- Deduplicate: if a URL appears in both HN and Pinboard, only include it once (in the HN section)
- Always run build-index.py after creating the magazine to update the archive and RSS feed
- Always commit and push so the site deploys automatically via GitHub Pages
