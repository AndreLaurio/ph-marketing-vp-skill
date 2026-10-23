#!/usr/bin/env python3
"""One-page marketing audit of a business website for the Philippine market.

Fetches the homepage (and the first contact-like page it links to) and reports
what a Filipino buyer and an ad platform need to see:

  mobile viewport, title/description/OG image, HTTPS, page weight,
  chat paths (Messenger m.me, Viber, WhatsApp, Telegram), PH phone numbers,
  email, payment mentions (GCash, Maya, COD, bank), marketplace links
  (Shopee, Lazada, TikTok Shop), socials, tracking (Meta Pixel, GA4/GTM,
  TikTok pixel), Google Maps link, Filipino-language signals.

Meant for auditing the user's own (or a named competitor's) site: two requests,
honest User-Agent, no crawling. Standard library only (Python 3.9+).

Usage:
  audit_site.py https://example.ph
  audit_site.py example.ph --json
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

USER_AGENT = (
    "ph-marketing-vp-skill/1.0 (+https://github.com/AndreLaurio/ph-marketing-vp-skill; "
    "single-page marketing audit)"
)
TIMEOUT = 15
MAX_BYTES = 3_000_000
CONTACT_HINTS = ("contact", "about", "order", "how-to-order", "location", "reach")

CHAT_PATTERNS = {
    "messenger": re.compile(r"(?:https?://)?(?:www\.)?(?:m\.me|messenger\.com/t)/[A-Za-z0-9_.-]+", re.I),
    "viber": re.compile(r"viber://[^\s\"'<>]+|invite\.viber\.com/[^\s\"'<>]+|vb\.me/[^\s\"'<>]+", re.I),
    "whatsapp": re.compile(r"(?:wa\.me|api\.whatsapp\.com/send|chat\.whatsapp\.com)/?[^\s\"'<>]*", re.I),
    "telegram": re.compile(r"(?:https?://)?t\.me/[A-Za-z0-9_]+", re.I),
}
SOCIAL_PATTERNS = {
    "facebook": re.compile(r"https?://(?:www\.|m\.|web\.)?facebook\.com/(?!sharer|share|tr\b|tr\?|plugins|dialog|2008)[^\s\"'<>?#]+", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+", re.I),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@[A-Za-z0-9_.]+", re.I),
    "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/(?:@|c/|channel/|user/)[^\s\"'<>?#]+", re.I),
    "linkedin": re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:company|in)/[^\s\"'<>?#]+", re.I),
}
MARKETPLACE_PATTERNS = {
    "shopee": re.compile(r"https?://(?:www\.)?shopee\.ph/[^\s\"'<>]+|shp\.ee/[^\s\"'<>]+", re.I),
    "lazada": re.compile(r"https?://(?:www\.)?lazada\.com\.ph/[^\s\"'<>]+|s\.lazada\.com\.ph/[^\s\"'<>]+", re.I),
    "tiktok_shop": re.compile(r"https?://(?:shop|vt)\.tiktok\.com/[^\s\"'<>]+", re.I),
    "grabfood_foodpanda": re.compile(r"https?://(?:food\.grab\.com|(?:www\.)?foodpanda\.ph)/[^\s\"'<>]+", re.I),
}
MAPS_RE = re.compile(r"https?://(?:maps\.app\.goo\.gl|goo\.gl/maps|(?:www\.)?google\.[a-z.]+/maps)[^\s\"'<>]*", re.I)
TRACKING = {
    "meta_pixel": ("connect.facebook.net", "fbq("),
    "google_analytics_ga4": ("gtag(", "googletagmanager.com/gtag/js"),
    "google_tag_manager": ("googletagmanager.com/gtm.js", "GTM-"),
    "tiktok_pixel": ("analytics.tiktok.com", "ttq.load"),
    "facebook_chat_plugin": ("xfbml.customerchat", "fb-customerchat"),
}
PAYMENT_WORDS = {
    "gcash": r"\bg-?cash\b",
    "maya": r"\b(?:pay)?maya\b",
    "cod": r"\bcod\b|cash on delivery",
    "bank_transfer": r"\bbdo\b|\bbpi\b|unionbank|instapay|pesonet|bank transfer",
    "card_or_bnpl": r"credit card|installment|home credit|billease|atome|spaylater",
}
# Common Filipino function words; enough hits means the copy speaks to a local audience.
FILIPINO_WORDS = ("po", "namin", "kami", "ninyo", "niyo", "ang", "mga", "para sa", "sa inyo",
                  "salamat", "ngayon", "dito", "tayo", "lang", "na", "ng")
PH_PHONE_RE = re.compile(r"(?:\+?63[\s-]?|0)9\d{2}[\s-]?\d{3}[\s-]?\d{4}|\(0\d{1,2}\)\s?\d{3,4}[\s-]?\d{4}|\+?63[\s-]?\d{1,2}[\s-]?\d{3,4}[\s-]?\d{4}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
JUNK_EMAIL = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", "sentry", "wixpress", "example.com")


class PageParser(HTMLParser):
    """Collects title, metas, links and visible text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.metas: Dict[str, str] = {}
        self.links: List[str] = []
        self.text_parts: List[str] = []
        self.has_h1 = False
        self.img_count = 0
        self.img_without_alt = 0
        self._in_title = False
        self._skip = 0
        self._svg = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "svg":
            self._svg += 1
        elif tag == "title" and not self.title and not self._svg:
            self._in_title = True
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key and a.get("content") and key not in self.metas:
                self.metas[key] = a["content"].strip()
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"].strip())
        elif tag == "h1":
            self.has_h1 = True
        elif tag == "img":
            self.img_count += 1
            if not a.get("alt"):
                self.img_without_alt += 1
        elif tag in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "svg" and self._svg:
            self._svg -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif not self._skip and data.strip():
            self.text_parts.append(data.strip())


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    return raw


HAVE_CURL = shutil.which("curl") is not None


def _fetch_curl(url: str) -> Tuple[Optional[str], Optional[str], Optional[str], int]:
    """Fallback for Pythons linked against old LibreSSL (macOS system python)."""
    cmd = ["curl", "-sS", "-L", "-m", str(TIMEOUT * 2), "-A", USER_AGENT, "--max-filesize", str(MAX_BYTES),
           "-w", "\\n%{url_effective}\\n%{http_code}", "-o", "-", url]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        return None, None, f"curl: {proc.stderr.decode(errors='replace').strip()[:100]}", 0
    raw = proc.stdout
    out = raw.decode("utf-8", errors="replace")
    body, _, code = out.rpartition("\n")
    body, _, final = body.rpartition("\n")
    if not code.startswith("2"):
        return None, None, f"http {code}", 0
    return final, body, None, len(raw)


def fetch(url: str) -> Tuple[Optional[str], Optional[str], Optional[str], int]:
    """Returns (final_url, body, error, bytes)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.5"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(MAX_BYTES)
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.geturl(), body.decode(charset, errors="replace"), None, len(body)
    except urllib.error.HTTPError as e:
        return None, None, f"http {e.code}", 0
    except Exception as e:  # noqa: BLE001 - report any network failure, fall back to curl on TLS issues
        if "SSL" in (str(e) + type(e).__name__).upper() and HAVE_CURL:
            return _fetch_curl(url)
        return None, None, f"{type(e).__name__}: {e}"[:120], 0


def first_matches(pattern: re.Pattern, html: str, limit: int = 3) -> List[str]:
    seen: List[str] = []
    for m in pattern.finditer(html):
        v = m.group(0).rstrip("/.,;)")
        if v not in seen:
            seen.append(v)
        if len(seen) >= limit:
            break
    return seen


def pick_contact_page(base: str, links: List[str]) -> Optional[str]:
    host = urllib.parse.urlsplit(base).netloc
    for href in links:
        full = urllib.parse.urljoin(base, href)
        parts = urllib.parse.urlsplit(full)
        if parts.netloc == host and any(h in parts.path.lower() for h in CONTACT_HINTS):
            return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return None


def audit(url: str) -> Dict:
    url = normalize_url(url)
    start = time.monotonic()
    final, html, err, size = fetch(url)
    elapsed = round(time.monotonic() - start, 2)
    if err or html is None:
        return {"url": url, "error": err or "empty response"}

    parser = PageParser()
    parser.feed(html)
    pages = [final or url]
    combined_html = html
    text = " ".join(parser.text_parts)

    contact = pick_contact_page(final or url, parser.links)
    if contact and contact.rstrip("/") != (final or url).rstrip("/"):
        time.sleep(1)
        _, chtml, cerr, _ = fetch(contact)
        if chtml and not cerr:
            cp = PageParser()
            cp.feed(chtml)
            combined_html += "\n" + chtml
            text += " " + " ".join(cp.text_parts)
            pages.append(contact)

    low_html = combined_html.lower()
    low_text = text.lower()
    words = re.findall(r"[a-zñ']+", low_text)
    fil_hits = sum(1 for w in words if w in FILIPINO_WORDS)
    emails = [e for e in dict.fromkeys(EMAIL_RE.findall(combined_html)) if not e.lower().endswith(JUNK_EMAIL)
              and not any(j in e.lower() for j in JUNK_EMAIL)][:3]

    report = {
        "url": url,
        "final_url": final,
        "pages_checked": pages,
        "https": (final or url).startswith("https://"),
        "load_seconds": elapsed,
        "html_kb": round(size / 1024),
        "title": parser.title.strip(),
        "meta_description": parser.metas.get("description", ""),
        "og_image": bool(parser.metas.get("og:image")),
        "mobile_viewport": "width=device-width" in parser.metas.get("viewport", "").replace(" ", ""),
        "has_h1": parser.has_h1,
        "images_missing_alt": f"{parser.img_without_alt}/{parser.img_count}",
        "chat": {k: first_matches(p, combined_html) for k, p in CHAT_PATTERNS.items()},
        "ph_phones": list(dict.fromkeys(m.strip() for m in PH_PHONE_RE.findall(text)))[:3],
        "emails": emails,
        "payments_mentioned": [k for k, p in PAYMENT_WORDS.items() if re.search(p, low_text)],
        "marketplaces": {k: first_matches(p, combined_html, 1) for k, p in MARKETPLACE_PATTERNS.items()},
        "socials": {k: first_matches(p, combined_html, 1) for k, p in SOCIAL_PATTERNS.items()},
        "google_maps_link": first_matches(MAPS_RE, combined_html, 1),
        "tracking": {k: any(s.lower() in low_html for s in sigs) for k, sigs in TRACKING.items()},
        "filipino_language_share": round(fil_hits / max(len(words), 1), 3),
        "visible_words": len(words),
    }
    report["findings"] = findings(report)
    return report


def findings(r: Dict) -> List[str]:
    """Plain-language issues, most damaging to PH conversion first."""
    out: List[str] = []
    if r["visible_words"] < 80:
        out.append(f"Only {r['visible_words']} words in the raw HTML: the site renders with JavaScript, so "
                   "content checks below may be false negatives; confirm with WebFetch or a phone screenshot")
    has_chat = any(r["chat"].values())
    if not has_chat and not r["ph_phones"]:
        out.append("No Messenger/Viber/WhatsApp link and no PH mobile number: buyers have no fast way to ask 'HM po?'")
    elif not r["chat"]["messenger"]:
        out.append("No m.me Messenger link: most PH buyers expect to order through Messenger")
    if not r["mobile_viewport"]:
        out.append("No mobile viewport meta: the site likely renders badly on phones")
    if not r["payments_mentioned"]:
        out.append("No payment options mentioned (GCash, Maya, COD, bank): a top pre-purchase question")
    if not r["tracking"]["meta_pixel"]:
        if r["tracking"]["google_tag_manager"]:
            out.append("Meta Pixel not in the HTML, but GTM is: it may load through GTM; verify with Meta Pixel Helper")
        else:
            out.append("No Meta Pixel: Facebook/Instagram ads cannot optimize or retarget website visitors")
    if not (r["tracking"]["google_analytics_ga4"] or r["tracking"]["google_tag_manager"]):
        out.append("No GA4/GTM: no way to see which channel sends traffic")
    if not r["socials"]["facebook"]:
        out.append("No link to a Facebook page: PH buyers check the page for legitimacy and feedback")
    if not r["google_maps_link"]:
        out.append("No Google Maps link (fine if online-only; a gap for any location-based business)")
    if r["html_kb"] > 1500 or r["load_seconds"] > 4:
        out.append(f"Heavy/slow homepage ({r['html_kb']} KB HTML, {r['load_seconds']}s): hurts buyers on mobile data")
    if not r["https"]:
        out.append("Not on HTTPS: browsers show 'Not secure', which kills trust")
    if not r["meta_description"]:
        out.append("No meta description: weak Google and link-preview snippet")
    if not r["og_image"]:
        out.append("No og:image: links shared in Messenger/groups show no preview image")
    return out


def to_text(r: Dict) -> str:
    if r.get("error"):
        return f"{r['url']}: could not fetch ({r['error']}). Try WebFetch or ask the user for screenshots."
    yes = lambda b: "yes" if b else "NO"  # noqa: E731
    chat = ", ".join(f"{k}: {v[0]}" for k, v in r["chat"].items() if v) or "none"
    market = ", ".join(f"{k}" for k, v in r["marketplaces"].items() if v) or "none"
    socials = ", ".join(f"{k}" for k, v in r["socials"].items() if v) or "none"
    tracking = ", ".join(f"{k}={yes(v)}" for k, v in r["tracking"].items())
    lines = [
        f"Audit: {r['final_url']}  ({len(r['pages_checked'])} page(s), {r['load_seconds']}s, {r['html_kb']} KB)",
        f"  Title: {r['title'][:90] or '(none)'}",
        f"  Description: {r['meta_description'][:120] or '(none)'}",
        f"  HTTPS {yes(r['https'])} | mobile viewport {yes(r['mobile_viewport'])} | og:image {yes(r['og_image'])} | H1 {yes(r['has_h1'])}",
        f"  Chat paths: {chat}",
        f"  PH phones: {', '.join(r['ph_phones']) or 'none'} | emails: {', '.join(r['emails']) or 'none'}",
        f"  Payments mentioned: {', '.join(r['payments_mentioned']) or 'none'}",
        f"  Marketplaces: {market} | socials: {socials} | maps link: {yes(r['google_maps_link'])}",
        f"  Tracking: {tracking}",
        f"  Filipino-language share of words: {r['filipino_language_share']:.0%}",
        "Findings (most damaging first):",
    ]
    lines += [f"  {i}. {f}" for i, f in enumerate(r["findings"], 1)] or ["  none"]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="+", help="website URL(s) or bare domains")
    ap.add_argument("--json", action="store_true", help="print JSON instead of the text report")
    args = ap.parse_args()
    reports = []
    for i, u in enumerate(args.urls):
        if i:
            time.sleep(1)
        reports.append(audit(u))
    if args.json:
        print(json.dumps(reports if len(reports) > 1 else reports[0], indent=2, ensure_ascii=False))
    else:
        print("\n\n".join(to_text(r) for r in reports))
    return 0 if all(not r.get("error") for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
