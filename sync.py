"""Make one podcast RSS feed from the episodes in a public Spotify playlist.

Usage: python3 sync.py <spotify-playlist-url> [output.xml] [--repo OWNER/NAME]
"""
import argparse
import base64
import difflib
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import formatdate

UA = {"User-Agent": "Mozilla/5.0"}
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def read_playlist(url):
    playlist_id = re.search(r"playlist/([A-Za-z0-9]+)", url).group(1)
    html = fetch(f"https://open.spotify.com/embed/playlist/{playlist_id}").decode()
    data = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    entity = json.loads(data.group(1))["props"]["pageProps"]["state"]["data"]["entity"]
    return entity["name"], entity["coverArt"]["sources"][0]["url"], entity["trackList"]


def clean_show(name):
    # "[Members Only] The Knowledge Project" and "99% Invisible | SiriusXM Podcasts+"
    # are paid feeds of public shows. Search for the public show.
    name = re.sub(r"\[.*?\]", "", name)
    return name.split("|")[0].strip()


def find_feed(show):
    q = urllib.parse.urlencode({"media": "podcast", "term": show, "limit": 5})
    results = json.loads(fetch(f"https://itunes.apple.com/search?{q}"))["results"]
    results = [r for r in results if r.get("feedUrl")]
    if not results:
        return None
    best = max(results, key=lambda r: difflib.SequenceMatcher(None, show.lower(), r["collectionName"].lower()).ratio())
    return best["feedUrl"]


def norm(title):
    title = re.sub(r"^\d+\.\s*", "", title.lower())  # "255. How Leaders..." -> "how leaders..."
    return re.sub(r"[^a-z0-9 ]", "", title).strip()


def parse_duration(text):
    if not text:
        return None
    parts = [int(p) for p in text.strip().split(":") if p.isdigit()]
    secs = 0
    for p in parts:
        secs = secs * 60 + p
    return secs


def match_episode(track, items):
    want = norm(track["title"])
    want_words = set(want.split())
    want_secs = track["duration"] / 1000
    best, best_score = None, 0
    for item in items:
        title = norm(item.findtext("title", ""))
        # Feeds sometimes reorder the title ("Roblox CEO: X" vs "X | Roblox CEO ..."),
        # so also count how many of the wanted words the feed title has.
        overlap = len(want_words & set(title.split())) / len(want_words)
        score = max(difflib.SequenceMatcher(None, want, title).ratio(), 0.9 * overlap)
        secs = parse_duration(item.findtext(f"{{{ITUNES_NS}}}duration"))
        if secs and abs(secs - want_secs) < 120:
            score += 0.1  # same length is a strong hint
        if score > best_score:
            best, best_score = item, score
    return best if best_score >= 0.7 else None


def build_feed(name, cover, episodes):
    ET.register_namespace("itunes", ITUNES_NS)
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = name
    ET.SubElement(channel, "link").text = "https://open.spotify.com"
    ET.SubElement(channel, "description").text = f"Episodes from the Spotify playlist {name}."
    ET.SubElement(channel, "language").text = "en"
    ET.SubElement(channel, f"{{{ITUNES_NS}}}image", href=cover)
    ET.SubElement(channel, f"{{{ITUNES_NS}}}explicit").text = "false"
    # Podcast apps sort by date, newest first. Give the first playlist item the
    # newest date so the app shows the episodes in playlist order.
    now = time.time()
    for i, (show, item) in enumerate(episodes):
        out = ET.SubElement(channel, "item")
        ET.SubElement(out, "title").text = f"{item.findtext('title')} ({show})"
        ET.SubElement(out, "description").text = item.findtext("description", "")
        ET.SubElement(out, "guid", isPermaLink="false").text = item.findtext("guid") or item.find("enclosure").get("url")
        ET.SubElement(out, "pubDate").text = formatdate(now - i * 60)
        out.append(item.find("enclosure"))
        duration = item.findtext(f"{{{ITUNES_NS}}}duration")
        if duration:
            ET.SubElement(out, f"{{{ITUNES_NS}}}duration").text = duration
    ET.indent(rss)
    return ET.tostring(rss, encoding="unicode", xml_declaration=True)


def upload_to_repo(repo, path):
    api = f"repos/{repo}/contents/feed.xml"
    # The GitHub API needs the current file's sha to replace it.
    sha = subprocess.run(["gh", "api", api, "--jq", ".sha"], capture_output=True, text=True).stdout.strip()
    body = {"message": "Update feed", "content": base64.b64encode(open(path, "rb").read()).decode()}
    if sha:
        body["sha"] = sha
    subprocess.run(["gh", "api", "-X", "PUT", api, "--input", "-"], input=json.dumps(body),
                   text=True, check=True, stdout=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("out_path", nargs="?", default="feed.xml")
    parser.add_argument("--repo", help="upload the feed to this GitHub Pages repo (owner/name)")
    args = parser.parse_args()
    out_path = args.out_path
    name, cover, tracks = read_playlist(args.url)
    print(f"{name}: {len(tracks)} episodes")

    feeds = {}
    found, missing = [], []
    for track in tracks:
        show = clean_show(track["subtitle"])
        if show not in feeds:
            feed_url = find_feed(show)
            feeds[show] = ET.fromstring(fetch(feed_url)).findall("./channel/item") if feed_url else []
            print(f"  feed for {show}: {feed_url or 'NOT FOUND'} ({len(feeds[show])} items)")
        item = match_episode(track, feeds[show])
        if item is not None and item.find("enclosure") is not None:
            found.append((show, item))
        else:
            missing.append(f"{track['title']} ({show})")

    with open(out_path, "w") as f:
        f.write(build_feed(name, cover, found))
    print(f"\nFound {len(found)} of {len(tracks)}. Wrote {out_path}.")
    for m in missing:
        print(f"  MISSING: {m}")

    if args.repo:
        upload_to_repo(args.repo, out_path)
        owner, repo = args.repo.split("/")
        print(f"Uploaded. Feed URL: https://{owner}.github.io/{repo}/feed.xml")


if __name__ == "__main__":
    main()
