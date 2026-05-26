"""
Web Learner - researches any topic from internet, stores in memory.
No API keys. Uses: Wikipedia REST API, DuckDuckGo HTML, GitHub API.
"""
import urllib.request
import urllib.parse
import json
import re
import time
import threading
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts  = []
        self._skip   = False
        self._skip_tags = {"script","style","nav","footer","header","aside","noscript"}

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip = True

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            t = data.strip()
            if len(t) > 25:
                self._parts.append(t)

    @property
    def text(self):
        return " ".join(self._parts)


def _fetch(url: str) -> str:
    try:
        req  = urllib.request.Request(
            url, headers={"User-Agent": "ASTRA-Research/1.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode("utf-8", errors="replace")
        p    = _TextExtractor()
        p.feed(html)
        return p.text[:4000]
    except Exception:
        return ""


def _wikipedia(topic: str) -> str:
    try:
        enc  = urllib.parse.quote(topic.replace(" ", "_"))
        url  = f"https://en.wikipedia.org/api/rest_v1/page/summary/{enc}"
        req  = urllib.request.Request(url, headers={"User-Agent": "ASTRA/1.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return data.get("extract", "")
    except Exception:
        return ""


def _ddg_urls(query: str) -> list:
    try:
        enc  = urllib.parse.quote(query)
        url  = f"https://html.duckduckgo.com/html/?q={enc}"
        req  = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode("utf-8", errors="replace")
        links = re.findall(r'href="(https?://[^"&]+)"', html)
        clean = [l for l in links
                 if "duckduckgo" not in l and "google" not in l
                 and "facebook" not in l and "twitter" not in l]
        return list(dict.fromkeys(clean))[:6]
    except Exception:
        return []


def _github(topic: str) -> str:
    try:
        enc  = urllib.parse.quote(topic)
        url  = f"https://api.github.com/search/repositories?q={enc}+in:readme&sort=stars&per_page=3"
        req  = urllib.request.Request(url, headers={
            "User-Agent": "ASTRA/1.0",
            "Accept": "application/vnd.github.v3+json"})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        rows = []
        for item in data.get("items", []):
            rows.append(
                f"{item['full_name']}: {item.get('description','')[:100]} "
                f"(stars:{item['stargazers_count']})"
            )
        return "\n".join(rows)
    except Exception:
        return ""


def _youtube_titles(topic: str) -> str:
    """Get YouTube video titles for a topic via search page."""
    try:
        enc  = urllib.parse.quote(topic)
        url  = f"https://www.youtube.com/results?search_query={enc}"
        req  = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="replace")
        titles = re.findall(r'"title":{"runs":\[{"text":"([^"]+)"', html)
        return "YouTube resources: " + ", ".join(titles[:5]) if titles else ""
    except Exception:
        return ""


class WebLearner:
    def __init__(self, memory_store):
        self.memory = memory_store

    def learn(self, topic: str, on_progress=None, on_done=None):
        """Run full research pipeline in background thread."""
        progress = on_progress or (lambda m: print(f"[Learn] {m}"))

        def _run():
            all_chunks = []
            progress(f"Starting research on: {topic}")

            # 1 - Wikipedia
            progress("Checking Wikipedia...")
            wiki = _wikipedia(topic)
            if wiki:
                all_chunks.append(("wikipedia.org", wiki))
                progress(f"Wikipedia: {len(wiki)} chars found")
            time.sleep(0.3)

            # 2 - DuckDuckGo + page scrape
            progress("Searching web...")
            urls = _ddg_urls(topic + " tutorial guide explained")
            progress(f"Found {len(urls)} sources")
            for i, url in enumerate(urls[:4]):
                progress(f"Reading source {i+1}/{min(4,len(urls))}...")
                text = _fetch(url)
                if len(text) > 150:
                    all_chunks.append((url, text))
                time.sleep(0.4)

            # 3 - GitHub if code topic
            code_kw = ["python","go","java","rust","code","api","library",
                       "framework","algorithm","programming","agent","ml","ai"]
            if any(k in topic.lower() for k in code_kw):
                progress("Searching GitHub...")
                gh = _github(topic)
                if gh:
                    all_chunks.append(("github.com", gh))

            # 4 - YouTube titles
            yt = _youtube_titles(topic)
            if yt:
                all_chunks.append(("youtube.com", yt))

            # 5 - Store in ChromaDB
            progress("Storing in memory...")
            stored = 0
            for source, text in all_chunks:
                chunk_size = 400
                for j in range(0, min(len(text), 4000), chunk_size):
                    chunk  = text[j:j+chunk_size].strip()
                    if len(chunk) < 50:
                        continue
                    doc_id = (f"learn_{topic.replace(' ','_')[:30]}_"
                              f"{source[:20].replace('/','_').replace(':','_')}_{j}")
                    try:
                        self.memory.knowledge.upsert(
                            documents=[chunk],
                            metadatas=[{"topic": topic, "source": source}],
                            ids=[doc_id],
                        )
                        stored += 1
                    except Exception:
                        pass

            msg = (f"Done. I have learned {stored} pieces of information about "
                   f"{topic} from {len(all_chunks)} sources including Wikipedia, "
                   f"web articles, and GitHub. You can now ask me any questions about it.")
            progress(msg)
            if on_done:
                on_done(msg)

        threading.Thread(target=_run, daemon=True).start()
