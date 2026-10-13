#!/usr/bin/env python3
"""Retrieve metadata; full-text claims still need independent verification."""

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

S2S_API = "https://api.semanticscholar.org/graph/v1/paper/search"
S2S_FIELDS = "paperId,title,authors,year,abstract,venue,url,citationCount,externalIds"
ARXIV_API = "https://export.arxiv.org/api/query"
USER_AGENT = "paper-search-skill/0.2"


class SearchUnavailable(RuntimeError):
    pass


def validate_request(query, limit, year_from=None):
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must contain search keywords")
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if year_from is not None and (not isinstance(year_from, int) or not 1000 <= year_from <= 9999):
        raise ValueError("year-from must be a four-digit year")


def retry_delay(error, attempt):
    value = error.headers.get("Retry-After") if isinstance(error, urllib.error.HTTPError) and error.headers else None
    try:
        return min(30.0, max(0.0, float(value))) if value is not None else float(2 ** attempt)
    except ValueError:
        return float(2 ** attempt)


def s2s_search(query, limit=8, year_from=None):
    validate_request(query, limit, year_from)
    params = {"query": query, "limit": limit, "fields": S2S_FIELDS}
    if year_from is not None:
        params["year"] = f"{year_from}-"
    headers = {"User-Agent": USER_AGENT}
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    request = urllib.request.Request(S2S_API + "?" + urllib.parse.urlencode(params), headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            papers = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(papers, list) or not all(isinstance(paper, dict) for paper in papers):
                raise ValueError("Semantic Scholar returned an invalid paper list")
            return papers, None
        except urllib.error.HTTPError as error:
            transient = error.code == 429 or 500 <= error.code < 600
            if not transient or attempt == 2:
                return None, error
            time.sleep(retry_delay(error, attempt))
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as error:
            if attempt == 2:
                return None, error
            time.sleep(float(2 ** attempt))
        except (ValueError, UnicodeError) as error:
            return None, error


def arxiv_search(query, limit=8, year_from=None):
    validate_request(query, limit, year_from)
    terms = [term.replace("\\", "\\\\").replace('"', '\\"') for term in query.split()]
    expression = " AND ".join(f'all:"{term}"' for term in terms)
    if year_from is not None:
        expression = f"({expression}) AND submittedDate:[{year_from}01010000 TO 999912312359]"
    params = {"search_query": expression, "start": 0, "max_results": limit,
              "sortBy": "relevance", "sortOrder": "descending"}
    request = urllib.request.Request(ARXIV_API + "?" + urllib.parse.urlencode(params), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            root = ET.fromstring(response.read())
        namespace = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        if root.tag != "{http://www.w3.org/2005/Atom}feed":
            raise ValueError("arXiv returned an invalid Atom feed")
        papers = []
        for entry in root.findall("a:entry", namespace):
            link = entry.findtext("a:id", "", namespace).strip()
            if "/api/errors" in link:
                raise ValueError("arXiv API error: " + entry.findtext("a:summary", "unknown error", namespace).strip())
            published = entry.findtext("a:published", "", namespace)
            year = int(published[:4]) if published[:4].isdigit() else None
            if year_from is not None and (year is None or year < year_from):
                continue
            doi = entry.findtext("arxiv:doi", "", namespace).strip()
            arxiv_id = link.split("/abs/", 1)[-1] if "/abs/" in link else None
            external_ids = {"ArXiv": arxiv_id} if arxiv_id else {}
            if doi:
                external_ids["DOI"] = doi
            papers.append({
                "title": " ".join(entry.findtext("a:title", "", namespace).split()),
                "authors": [{"name": author.findtext("a:name", "", namespace).strip()}
                            for author in entry.findall("a:author", namespace)],
                "year": year, "abstract": " ".join(entry.findtext("a:summary", "", namespace).split()),
                "venue": entry.findtext("arxiv:journal_ref", "", namespace).strip() or None,
                "url": link, "citationCount": None, "externalIds": external_ids,
                "is_preprint": True,
            })
        return papers, None
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException, ET.ParseError, ValueError) as error:
        return None, error


def search(query, limit=8, sort="relevance", year_from=None):
    validate_request(query, limit, year_from)
    if sort not in {"relevance", "citations"}:
        raise ValueError("sort must be relevance or citations")
    papers, error = s2s_search(query, limit, year_from)
    source = "Semantic Scholar"
    if papers is None:
        print(f"Semantic Scholar unavailable ({error}); trying arXiv. Coverage and year semantics differ.", file=sys.stderr)
        papers, fallback_error = arxiv_search(query, limit, year_from)
        source = "arXiv"
        if papers is None:
            raise SearchUnavailable(f"Both sources failed. arXiv: {fallback_error}")
    papers = [paper for paper in papers if paper.get("title") and paper.get("url")]
    if year_from is not None:
        papers = [paper for paper in papers if str(paper.get("year", "")).isdigit() and int(paper["year"]) >= year_from]
    if sort == "citations":
        papers.sort(key=lambda paper: (paper.get("citationCount") is not None, paper.get("citationCount") or 0), reverse=True)
        if source == "arXiv":
            print("arXiv provides no citation counts; keeping its relevance order.", file=sys.stderr)
    return papers[:limit], source


def fmt_authors(authors, max_n=3):
    names = []
    for author in (authors or []):
        name = author.get("name") if isinstance(author, dict) else None
        names.append(name.strip() if isinstance(name, str) and name.strip() else "unknown")
    return ", ".join(names[:max_n]) + (" et al." if len(names) > max_n else "") if names else "unknown"


def fmt_paper(index, paper):
    citations = paper.get("citationCount")
    venue = paper.get("venue") or ("arXiv preprint; journal not provided" if paper.get("is_preprint") else "venue not provided")
    lines = [f"{index}. 《{paper.get('title') or 'title not provided'}》",
             f"   {fmt_authors(paper.get('authors'))} ({paper.get('year') or 'unknown'}) · {venue} · citations {citations if citations is not None else 'unknown'}",
             f"   URL: {paper.get('url') or 'not provided'}"]
    abstract = paper.get("abstract") or ""
    if abstract:
        lines.append("   Abstract excerpt (metadata only): " + abstract[:200].replace("\n", " ") + ("…" if len(abstract) > 200 else ""))
    return "\n".join(lines)


def paper_keys(paper):
    external = paper.get("externalIds") or {}
    keys = set()
    doi = external.get("DOI")
    if doi:
        doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi.strip(), flags=re.IGNORECASE).casefold()
        keys.add("doi:" + doi)
    arxiv = external.get("ArXiv")
    if arxiv:
        keys.add("arxiv:" + re.sub(r"v\d+$", "", arxiv.strip()))
    if paper.get("paperId"):
        keys.add("s2:" + paper["paperId"])
    if paper.get("url"):
        keys.add("url:" + paper["url"].strip().rstrip("/"))
    if not keys:
        title = " ".join((paper.get("title") or "").split()).casefold()
        keys.add(f"title:{title}|year:{paper.get('year') or 'unknown'}")
    return keys


def save_to_list(papers, path, topic):
    path = Path(path).expanduser()
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    key_lines = {}
    line_keys = {}
    legacy = {}
    for index, line in enumerate(lines):
        marker = re.search(r"<!-- paper-search-id: (.*?) -->", line)
        if marker:
            keys = {urllib.parse.unquote(key) for key in marker.group(1).split(",")}
            line_keys[index] = keys
            key_lines.update((key, index) for key in keys)
        else:
            match = re.match(r"^- 《(.*?)》\(([^)]*)\)\s*(https?://\S+)?", line)
            if match:
                legacy[(" ".join(match[1].split()).casefold(), match[2])] = index
                if match[3]:
                    key_lines["url:" + match[3].rstrip("/")] = index
    additions = 0
    changed = False
    for paper in papers:
        title = " ".join((paper.get("title") or "").split())
        if not title:
            continue
        keys = paper_keys(paper)
        year = str(paper.get("year") or "unknown")
        matches = [key_lines[key] for key in keys if key in key_lines]
        index = min(matches) if matches else legacy.get((title.casefold(), year))
        if index is not None:
            keys = line_keys.get(index, set()) | keys
        encoded = ",".join(urllib.parse.quote(key, safe="") for key in sorted(keys))
        marker = f"<!-- paper-search-id: {encoded} -->"
        if index is None:
            if additions == 0:
                lines.extend(["", "## " + " ".join(topic.split())])
            index = len(lines)
            lines.append(f"- 《{title}》({year}) {paper.get('url') or ''} {marker}")
            additions += 1
            changed = True
        else:
            original = lines[index]
            lines[index] = re.sub(r"<!-- paper-search-id: .*? -->", marker, original) if "<!-- paper-search-id:" in original else original + " " + marker
            changed = changed or lines[index] != original
        line_keys[index] = keys
        key_lines.update((key, index) for key in keys)
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, prefix=".paper-search-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write("\n".join(lines) + "\n")
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    print(f"Saved {additions} new papers to {path}")
    return additions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True, help="Plain search keywords; no provider-specific query language")
    parser.add_argument("--limit", type=int, default=8, help="Maximum returned candidates, 1–100")
    parser.add_argument("--sort", choices=["relevance", "citations"], default="relevance")
    parser.add_argument("--year-from", type=int)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--save-path", default="reading_list.md", help="Project file, relative to the current working directory")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()
    try:
        papers, source = search(args.query, args.limit, args.sort, args.year_from)
        if args.save:
            with redirect_stdout(sys.stderr):
                save_to_list(papers, args.save_path, args.query)
        if args.format == "json":
            payload = {"query": args.query, "source": source,
                       "retrieved_at": datetime.now(timezone.utc).isoformat(),
                       "year_from": args.year_from, "sort": args.sort,
                       "ranking_scope": "returned_candidates", "verification_status": "metadata_only",
                       "year_definition": "first_arxiv_submission" if source == "arXiv" else "publication_metadata",
                       "papers": papers}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"Query: {args.query}; candidates: {len(papers)}; source: {source}; status: metadata only")
            if args.sort == "citations":
                print("Citation ranking applies only to the returned candidates, not the whole field.")
            if not papers:
                print("No matching candidates. Refine the query or use an appropriate alternative source.")
            for index, paper in enumerate(papers, 1):
                print(fmt_paper(index, paper) + "\n")
    except (ValueError, SearchUnavailable, OSError) as error:
        print(f"Search failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
