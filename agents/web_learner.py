"""
Web Learner - research any topic, store in memory, no API key.
Sources: Wikipedia REST API, DuckDuckGo HTML, GitHub API, free RSS feeds.
Stores chunks in ChromaDB for RAG retrieval.
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import re
import time
import threading
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip = False
        self._skip_tags = {"script","style","nav","footer","header","aside","form","button"}
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip = True
    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip = False
    def handle_data(self, data):
        if not self._skip:
            t = data.strip()
            if len(t) > 30:
                self.parts.append(t)
    def get_text(self):
        return " ".join(self.parts)


def _fetch(url: str, timeout: int = 8) -> str:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; ASTRA-AI/1.0)"}
        )
        resp = urllib.request.urlopen(req, timeout=timeout)
        html = resp.read().decode("utf-8", errors="replace")
        p = _TextExtractor()
        p.feed(html)
        return p.get_text()[:4000]
    except Exception as e:
        return ""


def _wikipedia(topic: str) -> str:
    try:
        enc  = urllib.parse.quote(topic.replace(" ", "_"))
        url  = f"https://en.wikipedia.org/api/rest_v1/page/summary/{enc}"
        req  = urllib.request.Request(url, headers={"User-Agent": "ASTRA-AI/1.0"})
        resp = urllib.request.urlopen(req, timeout=8)
        d    = json.loads(resp.read())
        return d.get("extract", "")
    except Exception:
        return ""


def _ddg_urls(query: str) -> list:
    try:
        enc  = urllib.parse.quote(query)
        url  = f"https://html.duckduckgo.com/html/?q={enc}"
        req  = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"}
        )
        resp = urllib.request.urlopen(req, timeout=8)
        html = resp.read().decode("utf-8", errors="replace")
        # Extract result URLs
        urls = re.findall(r'uddg=(https?[^&"]+)', html)
        decoded = [urllib.parse.unquote(u) for u in urls]
        # Filter garbage
        skip = {"duckduckgo","google","bing","yahoo","facebook","twitter","instagram"}
        clean = [u for u in decoded if not any(s in u.lower() for s in skip)]
        return list(dict.fromkeys(clean))[:5]
    except Exception:
        return []


def _github_repos(topic: str) -> str:
    try:
        enc  = urllib.parse.quote(topic)
        url  = f"https://api.github.com/search/repositories?q={enc}&sort=stars&per_page=3"
        req  = urllib.request.Request(url, headers={
            "User-Agent": "ASTRA-AI/1.0",
            "Accept": "application/vnd.github.v3+json",
        })
        resp = urllib.request.urlopen(req, timeout=8)
        d    = json.loads(resp.read())
        lines = []
        for item in d.get("items", []):
            lines.append(
                f"{item['full_name']}: {item.get('description','')}"
                f" [Stars:{item['stargazers_count']}]"
            )
        return "\n".join(lines)
    except Exception:
        return ""


def _store_chunks(memory, topic: str, source: str, text: str):
    if not text or len(text) < 50:
        return 0
    size    = 400
    overlap = 80
    chunks  = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i+size])
        i += size - overlap

    count = 0
    for j, chunk in enumerate(chunks[:12]):
        doc_id = f"learn_{re.sub(r'[^a-z0-9]','_',topic.lower())}_{j}_{int(time.time()*1000) % 100000}"
        try:
            memory.knowledge.upsert(
                documents=[chunk],
                metadatas=[{"topic": topic, "source": source}],
                ids=[doc_id],
            )
            count += 1
        except Exception:
            pass
    return count


class WebLearner:
    def __init__(self, memory_store):
        self.memory = memory_store

    def research(self, topic: str,
                 on_progress=None, on_complete=None):
        """
        Research topic from multiple free sources.
        Stores in ChromaDB. Runs in background thread.
        """
        _prog = on_progress or print
        _done = on_complete or print

        def _run():
            total = 0
            _prog(f"Researching {topic}. One moment...")

            # 1. Wikipedia (most reliable, fastest)
            wiki = _wikipedia(topic)
            if wiki:
                n = _store_chunks(self.memory, topic, "wikipedia", wiki)
                total += n
                _prog(f"Wikipedia: {n} facts stored.")

            # 2. DuckDuckGo top pages
            urls = _ddg_urls(topic)
            _prog(f"Found {len(urls)} web sources. Reading...")
            read = 0
            for url in urls[:3]:
                text = _fetch(url)
                if len(text) > 100:
                    n = _store_chunks(self.memory, topic, url, text)
                    total += n
                    read += 1
                time.sleep(0.3)
            _prog(f"Web pages: {read} read, {total} total facts stored.")

            # 3. GitHub if code-related
            code_kw = {"python","go","java","javascript","rust","code","programming",
                       "library","framework","api","algorithm","machine learning",
                       "deep learning","neural","agent","ai","ml"}
            if any(kw in topic.lower() for kw in code_kw):
                gh = _github_repos(topic)
                if gh:
                    n = _store_chunks(self.memory, topic, "github", gh)
                    total += n
                    _prog(f"GitHub repos: {n} references stored.")

            msg = (f"Done. I learned {total} pieces about {topic}. "
                   f"Ask me anything about it now.")
            _done(msg)

        threading.Thread(target=_run, daemon=True).start()
