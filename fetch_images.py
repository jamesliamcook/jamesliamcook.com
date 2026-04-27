#!/usr/bin/env python3
"""
fetch_images.py — James Cook portfolio image fetcher
=====================================================
Run this from inside the jamesliamcook-site/ folder:

    cd jamesliamcook-site
    python3 fetch_images.py

What it does:
1. Fetches the og:image from every article URL in writing.html and ledzepnews.html
2. Downloads and smart-crops each image to 16:9 at 900x506px into images/
3. Rewrites writing.html and ledzepnews.html replacing the text list
   with a 3-column editorial card grid (image + headline + description)
4. Prints a summary of what worked and what needs manual attention

Requirements (install once):
    pip install requests beautifulsoup4 Pillow

Run time: roughly 3-5 minutes. Re-running is safe — cached images are skipped.
"""

import os, re, sys, time, hashlib, json
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
    from PIL import Image
    import io
except ImportError:
    print("Installing dependencies...")
    os.system(f"{sys.executable} -m pip install requests beautifulsoup4 Pillow -q")
    import requests
    from bs4 import BeautifulSoup
    from PIL import Image
    import io

# ── Config ────────────────────────────────────────────────────
IMAGES_DIR   = Path("images")
IMAGES_DIR.mkdir(exist_ok=True)
CACHE_FILE   = IMAGES_DIR / ".cache.json"

TARGET_W     = 900
TARGET_H     = 506    # 16:9
JPEG_QUALITY = 83
DELAY        = 1.2    # seconds between requests

SESSION_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer":         "https://www.google.com/",
}

# Inline SVG logos — same as in the site HTML
TELEGRAPH_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 28" height="16" aria-label="The Telegraph">'
    '<text x="0" y="21" font-family="Georgia,\'Times New Roman\',serif" font-size="20" '
    'font-weight="400" fill="currentColor" letter-spacing="0.5">The Telegraph</text></svg>'
)
BI_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 230 28" height="14" aria-label="Business Insider">'
    '<text x="0" y="21" font-family="\'Arial Black\',\'Franklin Gothic Medium\',Arial,sans-serif" '
    'font-size="18" font-weight="900" fill="currentColor" letter-spacing="-0.2">Business Insider</text></svg>'
)

# ── HTTP session ──────────────────────────────────────────────
S = requests.Session()
S.headers.update(SESSION_HEADERS)


def url_slug(url: str) -> str:
    path  = urlparse(url).path.strip("/")
    parts = [p for p in path.split("/") if p and not re.match(r"^\d{1,4}$", p)]
    name  = re.sub(r"[^a-z0-9\-]", "", "-".join(parts[-2:]).lower())[:55]
    return f"{name}-{hashlib.md5(url.encode()).hexdigest()[:6]}"


def fetch_og_image(url: str):
    try:
        r = S.get(url, timeout=15, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup.find_all("meta"):
            prop = tag.get("property", "") or tag.get("name", "")
            if prop in ("og:image", "og:image:url", "twitter:image", "twitter:image:src"):
                content = tag.get("content", "")
                if content.startswith("http"):
                    return content
    except Exception:
        pass
    return None


def download_and_crop(img_url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        r   = S.get(img_url, timeout=20, stream=True)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        w, h = img.size
        ratio = TARGET_W / TARGET_H
        if w / h > ratio:
            nw = int(h * ratio)
            img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        elif w / h < ratio:
            nh = int(w / ratio)
            img = img.crop((0, 0, w, nh))
        img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
        img.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)
        print(f"    ✓ saved {dest.name} ({dest.stat().st_size // 1024} KB)")
        return True
    except Exception as e:
        print(f"    ✗ {e}")
        return False


# ── Parse existing clip-rows ──────────────────────────────────

def parse_clips(html_path: Path):
    with open(html_path) as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    clips = []
    for a in soup.select("a.clip-row"):
        href = a.get("href", "")
        if not href.startswith("http"):
            continue

        pub_span  = a.select_one(".clip-pub")
        pub_html  = str(pub_span) if pub_span else ""
        pub_class = " ".join(
            c for c in (pub_span.get("class", []) if pub_span else [])
            if c != "clip-pub"
        )

        title_span = a.select_one(".clip-title")
        desc_text  = ""
        title_text = ""
        if title_span:
            desc_el = title_span.select_one(".clip-desc")
            if desc_el:
                desc_text = desc_el.get_text(strip=True)
                desc_el.decompose()
            title_text = title_span.get_text(strip=True)

        date_span = a.select_one(".clip-date")
        date_text = date_span.get_text(strip=True) if date_span else ""

        clips.append({
            "url":       href,
            "pub_html":  pub_html,
            "pub_class": pub_class,
            "title":     title_text,
            "desc":      desc_text,
            "date":      date_text,
        })
    return clips


# ── Build card HTML ───────────────────────────────────────────

def build_card(clip: dict, img_path) -> str:
    if img_path:
        media = (
            f'<img class="clip-thumb" src="{img_path}" '
            f'alt="" loading="lazy" decoding="async">'
        )
    else:
        label = (
            "The Telegraph" if "telegraph" in clip["pub_class"] else
            "Business Insider" if "bi" in clip["pub_class"] else
            "LedZepNews"
        )
        media = f'<div class="clip-thumb-placeholder">{label}</div>'

    desc = f'<p class="clip-card-desc">{clip["desc"]}</p>' if clip["desc"] else ""

    return (
        f'      <a href="{clip["url"]}" target="_blank" class="clip-card">\n'
        f'        {media}\n'
        f'        <div class="clip-card-body">\n'
        f'          <div class="clip-card-meta">\n'
        f'            {clip["pub_html"]}\n'
        f'            <span class="clip-card-date">{clip["date"]}</span>\n'
        f'          </div>\n'
        f'          <p class="clip-card-title">{clip["title"]}</p>\n'
        f'          {desc}\n'
        f'          <span class="clip-card-read">Read →</span>\n'
        f'        </div>\n'
        f'      </a>'
    )


# ── Rewrite HTML ──────────────────────────────────────────────

def rewrite_html(html_path: Path, clips: list, url_to_img: dict):
    with open(html_path) as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".clips-list")
    if not container:
        print(f"  ✗ .clips-list not found in {html_path.name}")
        return

    # Switch container class to visual grid
    container["class"] = ["clips-list", "clips-list--visual"]

    # Clear existing children and insert cards
    container.clear()
    for clip in clips:
        card_html = build_card(clip, url_to_img.get(clip["url"]))
        container.append(BeautifulSoup(card_html, "html.parser"))

    with open(html_path, "w") as f:
        f.write(str(soup))

    n_img = sum(1 for c in clips if url_to_img.get(c["url"]))
    print(f"  ✓ {html_path.name}: {len(clips)} cards ({n_img} with images, {len(clips)-n_img} placeholders)")


# ── Main ──────────────────────────────────────────────────────

def main():
    files = [Path("writing.html"), Path("ledzepnews.html")]
    for f in files:
        if not f.exists():
            sys.exit(f"ERROR: {f} not found — run from inside jamesliamcook-site/")

    cache = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}

    all_clips = {}
    for f in files:
        clips = parse_clips(f)
        all_clips[f] = clips
        print(f"{f.name}: {len(clips)} articles")

    total = sum(len(v) for v in all_clips.values())
    print(f"\nFetching images for {total} articles "
          f"({len([u for u in [c['url'] for cl in all_clips.values() for c in cl] if u in cache])} cached)...\n")

    url_to_img: dict = {}
    failed      = []
    i           = 0

    for f, clips in all_clips.items():
        for clip in clips:
            url = clip["url"]
            i  += 1
            print(f"[{i}/{total}] {url[:75]}")

            # Cached
            if url in cache:
                print("    → cached")
                url_to_img[url] = cache[url]
                continue

            # Fetch og:image
            og_url = fetch_og_image(url)
            if not og_url:
                print("    ✗ no og:image found — placeholder will be used")
                url_to_img[url] = None
                failed.append(url)
                time.sleep(DELAY)
                continue

            # Download
            dest = IMAGES_DIR / f"{url_slug(url)}.jpg"
            if download_and_crop(og_url, dest):
                rel             = f"images/{dest.name}"
                url_to_img[url] = rel
                cache[url]      = rel
            else:
                url_to_img[url] = None
                failed.append(url)

            time.sleep(DELAY)

    CACHE_FILE.write_text(json.dumps(cache, indent=2))

    print(f"\n── Rewriting HTML ───────────────────────")
    for f, clips in all_clips.items():
        rewrite_html(f, clips, url_to_img)

    n_ok = sum(1 for v in url_to_img.values() if v)
    print(f"\n── Done ─────────────────────────────────")
    print(f"  Images fetched: {n_ok} / {total}")
    if failed:
        print(f"  Placeholders ({len(failed)}):")
        for u in failed:
            print(f"    {u}")
    print("""
Next steps:
  1. Open writing.html in your browser to preview the card grid
  2. For placeholder cards: find a suitable image online, save it to images/,
     then in the HTML replace:
       <div class="clip-thumb-placeholder">...</div>
     with:
       <img class="clip-thumb" src="images/yourfile.jpg" alt="" loading="lazy">
  3. Upload to GitHub: writing.html, ledzepnews.html, style.css + the images/ folder
""")


if __name__ == "__main__":
    main()
