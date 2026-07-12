# website-clone-skill

Clone any website you have the right to copy — no API keys, no paid tools, nothing
tied to anyone else's account. Works entirely with free tools and **your own** GitHub
and Vercel.

## Install

This is a skill for **[Claude Code](https://claude.ai/code)** — Anthropic's AI coding tool that runs in your terminal.

**Step 1 — Get Claude Code** (if you don't have it yet):

Open your terminal and paste the command below, then press Enter:
- **Mac:** press `Cmd + Space`, type "Terminal", hit Enter
- **Windows:** press `Win + R`, type "cmd", hit Enter (or open PowerShell from the Start menu)

```bash
npm install -g @anthropic-ai/claude-code
```
After the installation, type `claude` and hit Enter to start it.

**Step 2 — Install this skill** (run this inside Claude Code, or in your terminal):
```bash
claude install dlinyvr/website-clone-skill
```

**Step 3 — Use it:**
```
/website-clone-skill https://example.com
```

That's it. The skill walks you through everything else from there.

---

## What it does

1. **Crawls** the target site with a headless browser (Playwright + Chromium) — captures every page as Markdown, extracts colors/fonts/logo, and downloads all images and media. No Firecrawl. No API key.
2. **Rebuilds** it as a clean static [Astro](https://astro.build) site using `/frontend-design` to generate distinctive, production-quality UI from the captured design tokens.
3. **Deploys** it under your own GitHub repo + Vercel account with a free `*.vercel.app` URL.

The clone is **noindexed by default** so it stays out of search engines until you're ready to launch.

---

## Before you start — what you'll need

The skill checks for everything and installs what's missing, but here's what it needs:

| Tool | What for | Install |
|------|----------|---------|
| Python 3 + Playwright | Crawling | `pip install playwright beautifulsoup4 && playwright install chromium` |
| Node.js | Building the Astro site | [nodejs.org](https://nodejs.org) or `brew install node` |
| GitHub account + `gh` CLI | Pushing your repo | [github.com/signup](https://github.com/signup) · [cli.github.com](https://cli.github.com) |
| Vercel account | Deploying | [vercel.com/signup](https://vercel.com/signup) (free) |
| `/frontend-design` skill | Generating the UI | `! claude install anthropics/claude-code/plugins/frontend-design` |

**New to all of this?** Don't worry — the skill walks you through each step, including creating GitHub and Vercel accounts if you don't have them yet.

---

## How to use it

In Claude Code, just type:

```
/website-clone-skill https://example.com
```

The skill will:
- Ask you to confirm you have the right to clone the site
- Check that all tools are installed (and walk you through anything missing)
- Ask for a project name and where to save it
- Crawl the site
- Rebuild it as a static Astro site
- Push it to a **private** GitHub repo under your account
- Deploy it to Vercel and give you a live URL

---

## What you get

After the crawl, your project folder contains:

```
_capture/
  content/          # every page as Markdown (title, description, body)
  design-tokens.json  # colors, fonts, spacing extracted from the live site
  brand-identity.json # logo, nav links, tagline
  assets/
    images/         # all downloaded images
    videos/         # all downloaded videos
    docs/           # PDFs and other documents
  assets-manifest.json  # maps every asset back to its original URL
  screenshots/      # reference screenshots of the original pages
```

---

## Modes

| Mode | What it does |
|------|-------------|
| **Faithful rebuild** (default) | Full Astro site that mirrors the original's design and content |
| **Extract only** | Just capture content + branding + assets, no build step |

---

## Limitations

- **Faithful interim copy, not pixel-perfect.** Dynamic features (forms, search, carts, logins) are replaced with static equivalents (Formspree, Pagefind) or flagged.
- **Bot-protected or login-required sites** may not crawl fully.
- **You are responsible** for only cloning sites you own or have permission to copy. The cloned content remains the original owner's property. The skill noindexes the result by default.

---

## License

MIT — use freely. You are responsible for respecting the copyright and terms of service of any site you clone.
