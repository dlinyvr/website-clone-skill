---
name: website-clone-skill
version: 1.0.0
description: |
  Standalone website cloner — no API keys, no accounts of mine baked in.
  Scrapes a site's content + branding + all media with free headless-browser
  crawling (Playwright), rebuilds it as a static Astro site, then helps you
  push to YOUR GitHub and deploy to YOUR Vercel with a temp URL.
triggers:
  - website clone skill
  - clone a website
  - copy a website
  - clone site standalone
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - AskUserQuestion
---

# /website-clone-skill — standalone website cloner

Clone any website you have the right to copy, then publish it under your own
accounts. Everything here is **free and self-contained**: free crawling
(Playwright headless Chromium, the same engine `/reddit-research` uses — no
Firecrawl, no API key), a local Astro rebuild, your GitHub, your Vercel.

The crawler lives next to this file at **`<this-skill-dir>/scripts/clone.py`**.
Resolve the skill directory from the "Base directory for this skill" line the
runtime prints, and use `"$SKILL_DIR/scripts/clone.py"` throughout.

---

## Step 0 — Permission gate (do this first, every time)

Cloning a live site copies someone's copyrighted content and trademarks.
**Ask, and do not proceed until the user confirms one of these:**

> Before we clone **<site>**, confirm you have the right to copy it:
> - A) It's my own site
> - B) I have the owner's written permission (client work)
> - C) It's a template/demo I'm licensed to reuse

If none apply, stop and explain you can't help clone a third party's site
without permission.

---

## Step 1 — Preflight: dependencies + skills

### 1a — Install the `frontend-design` skill (required)

This skill depends on **`/frontend-design`** — an official free plugin from Anthropic that generates
distinctive, production-quality UI from design tokens. Without it, the rebuilt site will look generic.
You can read exactly what it does here: https://github.com/anthropics/claude-code/tree/main/plugins/frontend-design

Check if it's already installed:

```bash
ls ~/.claude/skills/frontend-design/SKILL.md 2>/dev/null && echo "ok" || echo "MISSING"
```

If **already installed** → continue to Step 1b.

If **MISSING** → install it automatically now:

```bash
claude install anthropics/claude-code/plugins/frontend-design
```

Tell the user:

> Installing the **frontend-design** plugin — this is a free official plugin from Anthropic that
> handles the visual design of your rebuilt site. It reads the colors, fonts, and layout captured
> from your site and turns them into a polished, production-ready result instead of a generic template.
> More info: https://github.com/anthropics/claude-code/tree/main/plugins/frontend-design

Run the install command, wait for confirmation, then verify:

```bash
ls ~/.claude/skills/frontend-design/SKILL.md 2>/dev/null && echo "ok" || echo "STILL MISSING"
```

If still missing after install, stop and ask the user to run:
```
! claude install anthropics/claude-code/plugins/frontend-design
```

Do **not** proceed to Step 2 until confirmed installed.

### 1b — Check system dependencies

Check each tool; if missing, show the install command and offer to run it.

```bash
echo "python3: $(python3 --version 2>&1)"
python3 -c "import playwright" 2>/dev/null && echo "playwright: ok" || echo "playwright: MISSING"
python3 -c "import bs4" 2>/dev/null && echo "beautifulsoup4: ok" || echo "beautifulsoup4: MISSING"
node --version 2>/dev/null && echo "node: ok" || echo "node: MISSING"
git --version 2>/dev/null | head -1
gh --version 2>/dev/null | head -1 || echo "gh: MISSING (GitHub CLI)"
npx vercel --version 2>/dev/null || echo "vercel: will use npx (no install needed)"
```

Install instructions to surface as needed:
- **Playwright + BS4:** `pip install playwright beautifulsoup4 && playwright install chromium`
- **Node (for Astro):** macOS `brew install node` · or nodejs.org · or `nvm install --lts`
- **GitHub CLI:** macOS `brew install gh` · Linux see cli.github.com · Windows `winget install GitHub.cli`
- **Vercel:** no install — we use `npx vercel`

Node, Playwright+BS4 are required to build. `gh` is required only for the GitHub
push (Step 7). Vercel is needed only for deploy (Step 8).

---

## Step 2 — Onboard GitHub (first-time users)

Ask: **"Do you already have a GitHub account + the `gh` CLI logged in?"**

If **no**, walk them through it (don't do it for them — these are personal accounts):
1. **Create the account:** go to https://github.com/signup, pick a username, verify email. (Free.)
2. **Install the CLI:** see Step 1.
3. **Log in — they run this themselves** (it's an interactive browser/device flow):
   > In your terminal, type:  `gh auth login`
   > Choose **GitHub.com → HTTPS → Login with a web browser**, then paste the
   > one-time code. When it says "Logged in as <you>", you're set.
   (In this session they can prefix it: `! gh auth login`.)
4. Confirm with `gh auth status` — capture the username for the repo path.

Record `GH_USER` (their GitHub username). All repo operations target
`GH_USER/<project>` — never any hardcoded account.

---

## Step 3 — Get context

Ask (AskUserQuestion or args):
1. **Target URL** — full URL of the site to clone.
2. **Project name** — lowercase-hyphenated; becomes the folder + repo name.
3. **Where to build it** — default `~/projects/<project-name>` (create if missing). Never assume a fixed machine path.
4. **Clone mode:**
   - A) **Faithful rebuild** — a deployable copy mirroring the design (default)
   - B) **Extract only** — just pull content + branding + assets into a folder

Set `PROJECT_DIR`. Detect WordPress as a hint (`curl -s <url> | grep -i wp-content`) but it doesn't change the engine — Playwright handles any stack.

---

## Step 4 — Crawl (content + branding + assets) — FREE

Run the bundled crawler. It discovers URLs (sitemap, else same-domain crawl),
renders each page, and writes content/, design tokens, brand-identity, and all
downloaded assets + a manifest.

```bash
SKILL_DIR="<this skill's base directory>"
mkdir -p "$PROJECT_DIR"
python3 "$SKILL_DIR/scripts/clone.py" "<url>" "$PROJECT_DIR/_capture" --max 40
```

Verify before continuing:
```bash
ls "$PROJECT_DIR/_capture/content/" | head
cat "$PROJECT_DIR/_capture/design-tokens.json"
ls "$PROJECT_DIR/_capture/assets/"*/ 2>/dev/null | head
```
If `content/` is empty, the site may block bots or require login — report and stop.
If **Mode B (extract only)**, you're done: tell the user where the capture is and stop.

---

## Step 5 — Rebuild as a static Astro site (Mode A)

Scaffold the Astro project skeleton, then **invoke `/frontend-design` to build the UI**.

```bash
cd "$PROJECT_DIR"
npm install astro@^4
mkdir -p src/pages src/layouts src/components src/styles public/images
cp -r _capture/assets/images/* public/images/ 2>/dev/null || true
```

### Call `/frontend-design` for the visual implementation

Pass it a design brief assembled from the capture:

> **Brief for `/frontend-design`:**
> Rebuild `<site name>` as a static Astro site.
> Design tokens: `$PROJECT_DIR/_capture/design-tokens.json` (background, text, accent, fonts).
> Brand identity: `$PROJECT_DIR/_capture/brand-identity.json`.
> Content pages: one `.astro` page per file in `$PROJECT_DIR/_capture/content/`.
> Images already in `public/images/`.
> **Goal:** a faithful rebuild — match the original's visual identity (palette, type, layout)
> rather than inventing a new look. Map any licensed fonts to their closest Google Fonts substitute.
> Include a `noindex` prop in BaseLayout defaulting to `true` (required — see Step 6).

Invoke it now: `/frontend-design`

`/frontend-design` will:
- Scaffold `src/styles/global.css` from the design tokens
- Build `BaseLayout.astro`, `Nav.astro`, `Footer.astro` from `nav_links` + logo
- Generate `src/pages/*.astro` from the captured content
- Dedupe any repeated hero text (animation artifacts from the crawler)

**Dynamic features** that can't be cloned 1:1 — handle after `/frontend-design` returns:
- Forms → Formspree / Tally embed (or leave inert for a demo, with a note)
- Search → Pagefind (build-time, static)
- E-commerce / login → out of scope; flag to the user

---

## Step 6 — noindex by default (it's a clone)

Keep the clone out of search engines until the user explicitly launches:
- `BaseLayout` renders `<meta name="robots" content="noindex, nofollow">` when `noindex` (default true).
- `public/robots.txt` → `User-agent: *` / `Disallow: /`.
- `public/_headers`? Vercel ignores `_headers`; instead add `vercel.json` headers:
  ```json
  { "headers": [ { "source": "/(.*)", "headers": [ { "key": "X-Robots-Tag", "value": "noindex, nofollow" } ] } ] }
  ```
To launch later: flip `noindex` to false, relax robots.txt, remove the X-Robots-Tag.

---

## Step 7 — Build, then push to the user's GitHub

```bash
cd "$PROJECT_DIR"
npm run build            # fix any errors before continuing
git init -q && git add -A
git commit -q -m "feat: clone <site> to a static Astro site (website-clone-skill)"
```
Push to **their** account (requires Step 2 `gh auth`):
```bash
gh repo create "$GH_USER/<project-name>" --private --source=. --remote=origin --push
```
Never push without the user's confirmation. Private by default.

---

## Step 8 — Deploy to Vercel (their account, temp URL)

Vercel auto-detects Astro and gives a free temporary `*.vercel.app` URL.

1. **Log in (they run it — interactive):**
   > `npx vercel login` — pick your email/GitHub and confirm the link Vercel emails/opens.
   (In session: `! npx vercel login`.)
2. **Deploy** (from `$PROJECT_DIR`):
   ```bash
   npx vercel --yes            # first run links + creates the project, returns a preview URL
   npx vercel --prod --yes     # promotes to the project's production *.vercel.app URL
   ```
   Vercel detects Astro automatically (build `astro build`, output `dist`). The
   `vercel.json` from Step 6 keeps the deploy noindexed.
3. Print the live URL and confirm `X-Robots-Tag: noindex` is present:
   ```bash
   curl -sI <vercel-url> | grep -i x-robots-tag
   ```

---

## Step 9 — Write todo.md + drive remaining work

Create `$PROJECT_DIR/todo.md` with the checklist below, then work it top to
bottom, marking `[x]` as each is verified. Re-read it at the start of each
session. Don't call the clone "done" until every box is checked.

```markdown
# TODO — <project>

## Website clone — <site> (<date>)
| Status | Task |
|--------|------|
| [x] | Crawl content + branding + assets |
| [x] | Rebuild as static Astro + noindex |
| [ ] | Spot-check pages vs the original |
| [ ] | Wire forms (Formspree/Tally) if needed |
| [ ] | Push to GitHub (<user>/<project>) |
| [ ] | Deploy to Vercel (temp URL) |
| [ ] | When launching: remove noindex (meta + robots.txt + vercel.json) |
```

---

## Guardrails
- Permission gate (Step 0) is mandatory.
- Never push or deploy without explicit confirmation.
- No API keys, no hardcoded accounts/paths — everything targets the user's own GitHub + Vercel.
- Honest fidelity: this produces a faithful **interim** static copy, not a pixel-perfect or dynamic replica.
