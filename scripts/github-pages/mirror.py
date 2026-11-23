#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
آینه‌برداری سایت اصلی (Netlify) برای انتشار روی GitHub Pages
- همهٔ صفحه‌ها، فایل‌های استاتیک، فونت‌ها و تصاویر عیناً در ./site ذخیره می‌شوند
- آدرس‌های نسخهٔ اصلی به آدرس گیت‌هاب بازنویسی می‌شوند (canonical، sitemap، og و ...)
"""
import os
import re
import time
import urllib.request
import urllib.error

BASE = "https://aghaei-vakil.netlify.app"
DEST = "ehsanaghaeilaw.github.io"
OUT = "site"
MAX_FILES = 400

TEXT_EXT = ('.html', '.xml', '.txt', '.js', '.mjs', '.css', '.json', '.webmanifest', '.svg')


def fetch(path):
    """دریافت BASE+path؛ خطاهای HTTP هم بدنه دارند (برای صفحه ۴۰۴)"""
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                BASE + path, headers={"User-Agent": "Mozilla/5.0 (site-mirror)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            body = e.read() if e.fp else b""
            return e.code, body
        except Exception as e:
            if attempt == 2:
                print("fetch error:", path, repr(e))
                return 0, b""
            time.sleep(1)


def is_html(body):
    """تشخیص سند HTML از روی ۶۰۰ بایت اول"""
    head = body[:600].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def save(path, data):
    rel = path.lstrip("/")
    if rel == "":
        rel = "index.html"
    elif is_html(data) and not rel.endswith(".html"):
        # صفحهٔ HTML بدون پسوند → شکل دایرکتوری تا GitHub Pages درست سروش کند
        rel = rel.rstrip("/") + "/index.html"
    fp = os.path.join(OUT, rel)
    d = os.path.dirname(fp)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(fp, "wb") as f:
        f.write(data)


REF_PATTERNS = [
    re.compile(r'(?:href|src|poster|content|data-src)\s*=\s*["\']([^"\']+)["\']'),
    re.compile(r'(?:href|src|poster|content|data-src)\s*=\s*["\']https?://aghaei-vakil\.netlify\.app(/[^"\']+)["\']'),
    re.compile(r'url\(\s*["\']?(/[^"\')\s]+)'),
    re.compile(r'["\'](/_next/[^"\']{4,300}?)["\']'),
]


def scan(text):
    """استخراج مسیرهای داخلی ارجاع‌شده در یک سند"""
    out = set()
    for pat in REF_PATTERNS:
        for r in pat.findall(text):
            r = r.split("#", 1)[0].split("?", 1)[0]
            if not r.startswith("/") or r.startswith("//"):
                continue
            if r.startswith("/api/") or r.startswith("/admin"):
                continue
            if r == "/":
                continue
            out.add(r)
    return out


def is_asset(p):
    return bool(re.search(
        r"\.(js|mjs|css|woff2?|ttf|otf|png|jpe?g|svg|webp|gif|ico|json|webmanifest|txt|xml|map|avif|mp4)$",
        p, re.I))


seen, failed = set(), []
queue = ["/", "/robots.txt", "/sitemap.xml", "/favicon.svg", "/logo.svg",
         "/og-image.jpg", "/__not-found-page__"]

while queue and len(seen) < MAX_FILES:
    p = queue.pop(0)
    if p in seen:
        continue
    seen.add(p)
    status, body = fetch(p)
    if not body:
        failed.append(p)
        continue
    if p == "/__not-found-page__":
        save("404.html", body)
        continue
    save(p, body)
    if status >= 400:
        failed.append(f"{p} ({status})")
    if p == "/" or is_asset(p):
        text = body.decode("utf-8", "ignore")
        for ref in scan(text):
            if ref not in seen:
                queue.append(ref)

# بدون این فایل، پوشهٔ _next توسط GitHub Pages سرو نمی‌شود
with open(os.path.join(OUT, ".nojekyll"), "w") as f:
    f.write("")

# بازنویسی همهٔ دامنه‌های نسخهٔ اصلی به دامنهٔ گیت‌هاب
ORIGINS = ("aghaei-vakil.netlify.app", "aghaeivakil.space-z.ai")
count = 0
for root, dirs, files in os.walk(OUT):
    for f in files:
        if f.endswith(TEXT_EXT):
            fp = os.path.join(root, f)
            s = open(fp, encoding="utf-8", errors="ignore").read()
            n = sum(s.count(o) for o in ORIGINS)
            if n:
                for o in ORIGINS:
                    s = s.replace(o, DEST)
                count += n
                open(fp, "w", encoding="utf-8").write(s)

# نقشهٔ سایت را از همین صفحه‌های برداشته‌شده می‌سازیم
SKIP_SITEMAP = ("/", "/robots.txt", "/sitemap.xml", "/favicon.svg",
                "/logo.svg", "/og-image.jpg", "/__not-found-page__")
pages = ["/"] + sorted(p for p in seen
                       if p not in SKIP_SITEMAP and not is_asset(p))
today = time.strftime("%Y-%m-%d")
urls = "".join(
    f"<url><loc>https://{DEST}{p}</loc><lastmod>{today}</lastmod>"
    f"<changefreq>{'daily' if p == '/' else 'weekly'}</changefreq>"
    f"<priority>{'1.0' if p == '/' else '0.8'}</priority></url>"
    for p in pages)
with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + urls + "\n</urlset>\n")

idx = os.path.join(OUT, "index.html")
size = os.path.getsize(idx) if os.path.exists(idx) else 0
print("mirrored:", len(seen), "files | rewritten refs:", count,
      "| sitemap urls:", len(pages), "| failures:", failed[:10])
print("index.html bytes:", size)
assert size > 10000, "index.html missing or too small - mirror failed"
print("MIRROR OK")
