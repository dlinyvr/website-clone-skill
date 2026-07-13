#!/usr/bin/env python3
"""
clone.py — free, standalone website cloner (no API keys).

Uses Playwright (headless Chromium) + BeautifulSoup to:
  1. discover  — find all page URLs (sitemap.xml, else same-domain crawl)
  2. content   — render each page and save it as Markdown
  3. design    — screenshot + extract computed CSS tokens (colors, fonts, logo)
  4. assets    — download every image / video / doc + write a manifest

Everything is written under <outdir>/. No third-party API, no credentials.

Install once:
    pip install playwright beautifulsoup4
    playwright install chromium

Run:
    python3 clone.py https://example.com ./out --max 40
"""
import sys, os, re, json, time, argparse, hashlib
from urllib.parse import urlparse, urljoin, unquote
from urllib.request import Request, urlopen

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Missing Playwright. Run:  pip install playwright beautifulsoup4 && playwright install chromium")
try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing BeautifulSoup. Run:  pip install beautifulsoup4")

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"


# ── browser helpers ────────────────────────────────────────────────────────
def new_browser(p):
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(user_agent=UA, viewport={"width": 1440, "height": 900})
    return b, ctx


def render(ctx, url, wait_ms=2500):
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=45000)
    except Exception:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception:
            page.close(); return None, None
    page.wait_for_timeout(wait_ms)
    html = page.content()
    return page, html


# ── 1. discover ─────────────────────────────────────────────────────────────
def discover(ctx, base, limit):
    root = f"{urlparse(base).scheme}://{urlparse(base).netloc}"
    found = []
    for sm in ("sitemap.xml", "sitemap_index.xml", "wp-sitemap.xml"):
        try:
            xml = urlopen(Request(f"{root}/{sm}", headers={"User-Agent": UA}), timeout=20).read().decode("utf-8", "ignore")
        except Exception:
            continue
        locs = re.findall(r"<loc>([^<]+)</loc>", xml)
        # sitemap index → expand sub-sitemaps
        if locs and all(l.endswith(".xml") for l in locs[:3]):
            for sub in locs:
                try:
                    subxml = urlopen(Request(sub, headers={"User-Agent": UA}), timeout=20).read().decode("utf-8", "ignore")
                    found += re.findall(r"<loc>([^<]+)</loc>", subxml)
                except Exception:
                    pass
        else:
            found += locs
        if found:
            break

    # fallback: breadth-first crawl of same-domain links from the homepage
    if not found:
        page, html = render(ctx, base)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.select("a[href]"):
                u = urljoin(base, a["href"]).split("#")[0].rstrip("/")
                if urlparse(u).netloc == urlparse(base).netloc and u not in found:
                    found.append(u)
            page.close()
        found = [base.rstrip("/")] + found

    # de-dupe, drop common WP cruft + non-page assets
    skip = re.compile(r"/(wp-json|feed|xmlrpc|author/|tag/|/page/\d|\.(xml|json|pdf|jpg|png))", re.I)
    seen, out = set(), []
    for u in found:
        u = u.split("#")[0].rstrip("/") or root
        if u in seen or skip.search(u):
            continue
        seen.add(u); out.append(u)
    return out[:limit]


# ── 2. content → markdown ───────────────────────────────────────────────────
def html_to_md(soup):
    main = soup.find("main") or soup.find("article") or soup.body or soup
    # strip noise
    for sel in ["script", "style", "noscript", "svg", "form", "nav", "footer", "header"]:
        for t in main.find_all(sel):
            t.decompose()
    out = []
    for el in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "img", "a", "blockquote"], recursive=True):
        txt = el.get_text(" ", strip=True)
        if el.name in ("h1", "h2", "h3", "h4"):
            if txt: out.append("#" * int(el.name[1]) + " " + txt)
        elif el.name == "li":
            if txt: out.append("- " + txt)
        elif el.name == "blockquote":
            if txt: out.append("> " + txt)
        elif el.name == "img":
            src = el.get("src") or el.get("data-src") or ""
            if src: out.append(f"![{el.get('alt','')}]({src})")
        elif el.name == "p":
            if txt: out.append(txt)
    # collapse runs of identical lines (animation/marquee duplication)
    dedup, prev = [], None
    for line in out:
        if line != prev:
            dedup.append(line)
        prev = line
    return "\n\n".join(dedup)


def grab_content(ctx, urls, outdir):
    cdir = os.path.join(outdir, "content"); os.makedirs(cdir, exist_ok=True)
    meta = {}
    for i, u in enumerate(urls):
        page, html = render(ctx, u)
        if not html:
            print(f"[{i+1}/{len(urls)}] FAIL {u}"); continue
        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.string if soup.title else "") or ""
        desc = ""
        m = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if m: desc = m.get("content", "")
        slug = (urlparse(u).path.strip("/").replace("/", "-") or "home")
        md = f"---\nurl: {u}\ntitle: {title.strip()}\ndescription: {desc.strip()}\n---\n\n" + html_to_md(soup)
        open(os.path.join(cdir, f"{slug}.md"), "w").write(md)
        meta[u] = {"title": title.strip(), "description": desc.strip(), "slug": slug}
        print(f"[{i+1}/{len(urls)}] OK {slug} ({len(md)} chars)")
        page.close()
    json.dump(meta, open(os.path.join(outdir, "page-meta.json"), "w"), indent=2)
    return meta


# ── 3. design tokens + screenshots ──────────────────────────────────────────
TOKEN_JS = r"""() => {
  const cs = el => el ? getComputedStyle(el) : {};
  const body = document.body,
    h1 = document.querySelector('h1,h2'),
    btn = document.querySelector('a[class*=btn],button,.button,.elementor-button,.wp-block-button a'),
    nav = document.querySelector('header,nav,.site-header'),
    footer = document.querySelector('footer,.site-footer'),
    link = document.querySelector('a');
  const bgs = {};
  document.querySelectorAll('a,button,.btn,.elementor-button').forEach(e => {
    const b = getComputedStyle(e).backgroundColor;
    if (b && b !== 'rgba(0, 0, 0, 0)') bgs[b] = (bgs[b] || 0) + 1;
  });
  return {
    bg: cs(body).backgroundColor, text_color: cs(body).color,
    body_font: cs(body).fontFamily, body_size: cs(body).fontSize,
    h1_font: cs(h1).fontFamily, h1_size: cs(h1).fontSize, h1_weight: cs(h1).fontWeight, h1_color: cs(h1).color,
    btn_bg: cs(btn).backgroundColor, btn_color: cs(btn).color, btn_radius: cs(btn).borderRadius,
    nav_bg: cs(nav).backgroundColor, footer_bg: cs(footer).backgroundColor, link_color: cs(link).color,
    nav_links: [...document.querySelectorAll('header nav a,.main-navigation a,header a')].map(a=>a.textContent.trim()).filter(Boolean).slice(0,8),
    logo_src: (document.querySelector('header img,.site-logo img,.custom-logo,img[src*=logo],a[class*=logo] img')||{}).src,
    og_image: (document.querySelector('meta[property="og:image"]')||{}).content,
    favicon: (document.querySelector('link[rel*=icon]')||{}).href,
    button_bgs: bgs,
  };
}"""


def grab_design(ctx, base, urls, outdir):
    sdir = os.path.join(outdir, "screenshots"); os.makedirs(sdir, exist_ok=True)
    page, html = render(ctx, base)
    if not page:
        return {}
    try:
        page.screenshot(path=os.path.join(sdir, "home.png"), full_page=True)
    except Exception:
        pass
    tokens = page.evaluate(TOKEN_JS)
    page.close()
    # a couple of inner-page screenshots for reference
    for u in [x for x in urls if x.rstrip("/") != base.rstrip("/")][:2]:
        p2, _ = render(ctx, u)
        if p2:
            try: p2.screenshot(path=os.path.join(sdir, (urlparse(u).path.strip("/").replace("/", "-") or "page") + ".png"), full_page=True)
            except Exception: pass
            p2.close()
    json.dump(tokens, open(os.path.join(outdir, "design-tokens.json"), "w"), indent=2)
    # human-readable brand identity
    bi = [
        "# Brand Identity (auto-captured)\n",
        f"- Background: `{tokens.get('bg')}`",
        f"- Text: `{tokens.get('text_color')}`",
        f"- Body font: `{tokens.get('body_font')}`  ·  H1 font: `{tokens.get('h1_font')}` ({tokens.get('h1_weight')})",
        f"- Button: bg `{tokens.get('btn_bg')}` · text `{tokens.get('btn_color')}` · radius `{tokens.get('btn_radius')}`",
        f"- Nav links: {', '.join(tokens.get('nav_links', []))}",
        f"- Logo: {tokens.get('logo_src')}",
        f"- Accent candidates (button bg counts): {tokens.get('button_bgs')}",
        "\n> Map licensed fonts (e.g. Gotham, Proxima Nova) to the closest Google Fonts substitute (Montserrat, etc.).",
    ]
    open(os.path.join(outdir, "brand-identity.md"), "w").write("\n".join(bi))
    return tokens


# ── 4. assets ───────────────────────────────────────────────────────────────
ASSET_JS = r"""() => [...new Set([
  ...[...document.querySelectorAll('img')].flatMap(i => [i.src, i.currentSrc, ...((i.srcset||'').split(',').map(s=>s.trim().split(' ')[0]))]),
  ...[...document.querySelectorAll('video,source')].map(v => v.src),
  ...[...document.querySelectorAll('a[href]')].map(a=>a.href).filter(h=>/\.(pdf|docx?|mp3|zip|csv|xlsx?)$/i.test(h)),
  ...[...document.querySelectorAll('link[rel*=icon]')].map(l=>l.href),
  (document.querySelector('meta[property="og:image"]')||{}).content,
  ...[...document.querySelectorAll('*')].map(e=>getComputedStyle(e).backgroundImage)
     .filter(b=>b&&b!=='none').flatMap(b=>[...b.matchAll(/url\(["']?([^"')]+)/g)].map(m=>m[1])),
].filter(Boolean))]"""

IMG = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif", ".ico"}
VID = {".mp4", ".webm", ".mov", ".m4v"}
DOC = {".pdf", ".doc", ".docx", ".csv", ".xlsx", ".mp3", ".zip"}


def grab_assets(ctx, base, urls, outdir):
    host = urlparse(base).netloc
    found = set()
    for u in [base] + urls[:8]:
        page, _ = render(ctx, u, wait_ms=1500)
        if not page: continue
        try:
            for a in page.evaluate(ASSET_JS):
                if a and a.startswith("http"):
                    found.add(urljoin(u, a))
        except Exception:
            pass
        page.close()
    # keep brand-domain assets (+ any pdf/doc), skip 3rd-party tracking/maps tiles
    keep = [a for a in found if (urlparse(a).netloc == host or os.path.splitext(urlparse(a).path)[1].lower() in DOC)
            and not re.search(r"(googleapis|gstatic|google-analytics|doubleclick|facebook|/blank\.)", a)]
    man = []
    for a in sorted(set(keep)):
        ext = os.path.splitext(urlparse(a).path)[1].lower() or ".bin"
        sub = "images" if ext in IMG else "videos" if ext in VID else "docs" if ext in DOC else "other"
        d = os.path.join(outdir, "assets", sub); os.makedirs(d, exist_ok=True)
        name = unquote(os.path.basename(urlparse(a).path)) or (hashlib.md5(a.encode()).hexdigest()[:10] + ext)
        local = os.path.join(d, name)
        if os.path.exists(local):
            man.append({"url": a, "local": local, "type": sub, "status": "exists"}); continue
        try:
            data = urlopen(Request(a, headers={"User-Agent": UA}), timeout=60).read()
            open(local, "wb").write(data)
            man.append({"url": a, "local": local, "type": sub, "bytes": len(data), "status": "ok"})
            print(f"  asset OK {sub}/{name}")
        except Exception as e:
            man.append({"url": a, "local": None, "type": sub, "status": f"fail: {e}"})
    json.dump(man, open(os.path.join(outdir, "assets-manifest.json"), "w"), indent=2)
    ok = sum(1 for m in man if m["status"] in ("ok", "exists"))
    print(f"Assets: {ok}/{len(man)} downloaded → {outdir}/assets/")
    return man


# ── main ────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Free standalone website cloner (Playwright).")
    ap.add_argument("url")
    ap.add_argument("outdir")
    ap.add_argument("--max", type=int, default=40, help="max pages to crawl")
    ap.add_argument("--only", choices=["discover", "content", "design", "assets"], help="run one stage only")
    a = ap.parse_args()
    base = a.url.rstrip("/")
    os.makedirs(a.outdir, exist_ok=True)

    with sync_playwright() as p:
        b, ctx = new_browser(p)
        try:
            print("→ discovering URLs…")
            urls = discover(ctx, base, a.max)
            json.dump(urls, open(os.path.join(a.outdir, "urls.json"), "w"), indent=2)
            print(f"  {len(urls)} pages")
            if a.only == "discover":
                return
            if a.only in (None, "content"):
                print("→ extracting content…"); grab_content(ctx, urls, a.outdir)
            if a.only in (None, "design"):
                print("→ capturing design…"); grab_design(ctx, base, urls, a.outdir)
            if a.only in (None, "assets"):
                print("→ downloading assets…"); grab_assets(ctx, base, urls, a.outdir)
        finally:
            ctx.close(); b.close()
    print(f"\n✓ Clone captured to {a.outdir}/  (content/, design-tokens.json, brand-identity.md, assets/, assets-manifest.json)")


if __name__ == "__main__":
    main()
