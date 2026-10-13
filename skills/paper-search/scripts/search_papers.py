#!/usr/bin/env python3
"""论文检索脚本：用 Semantic Scholar API 按主题搜论文。

用法：
    python3 search_papers.py --query "EEG microstate" --limit 8
    python3 search_papers.py --query "phase synchronization" --limit 5 --sort citations
    python3 search_papers.py --query "Riemannian BCI" --limit 5 --save
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

S2S_API = "https://api.semanticscholar.org/graph/v1/paper/search"
S2S_FIELDS = "title,authors,year,abstract,venue,url,citationCount,externalIds"
ARXIV_API = "http://export.arxiv.org/api/query"


def s2s_search(query, limit=8, year_from=None):
    params = {"query": query, "limit": limit, "fields": S2S_FIELDS}
    if year_from:
        params["year"] = f"{year_from}-"
    url = S2S_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "paper-search-skill/0.1"})
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8")).get("data", []), None
        except Exception as e:
            last_err = e
            time.sleep(2 ** attempt + 1)
    return None, last_err


def arxiv_search(query, limit=8):
    """arXiv 兜底：无需 key，几乎不限流；缺点是没有被引数和期刊信息。"""
    import xml.etree.ElementTree as ET
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = ARXIV_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "paper-search-skill/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            root = ET.fromstring(resp.read())
    except Exception as e:
        return None, e
    ns = {"a": "http://www.w3.org/2005/Atom"}
    papers = []
    for entry in root.findall("a:entry", ns):
        title = (entry.findtext("a:title", "", ns) or "").strip().replace("\n", " ")
        authors = [{"name": (a.findtext("a:name", "", ns) or "").strip()}
                   for a in entry.findall("a:author", ns)]
        published = entry.findtext("a:published", "", ns) or ""
        summary = (entry.findtext("a:summary", "", ns) or "").strip().replace("\n", " ")
        link = (entry.findtext("a:id", "", ns) or "").strip()
        papers.append({
            "title": title, "authors": authors,
            "year": published[:4] if published else "?",
            "abstract": summary, "venue": "arXiv",
            "url": link, "citationCount": None,
        })
    return papers, None


def search(query, limit=8, sort="citations", year_from=None):
    papers, err = s2s_search(query, limit, year_from)
    source = "Semantic Scholar"
    if papers is None:
        print(f"Semantic Scholar 限流/不可用（{err}），切换到 arXiv 兜底。", file=sys.stderr)
        papers, err2 = arxiv_search(query, limit)
        source = "arXiv（兜底：无被引数）"
        if papers is None:
            print(f"arXiv 也失败了：{err2}", file=sys.stderr)
            sys.exit(1)
    if sort == "citations":
        papers.sort(key=lambda p: p.get("citationCount") or 0, reverse=True)
    return papers, source


def fmt_authors(authors, max_n=3):
    names = [a.get("name", "?") for a in (authors or [])]
    if len(names) > max_n:
        return ", ".join(names[:max_n]) + " et al."
    return ", ".join(names) if names else "?"


def fmt_paper(i, p):
    title = p.get("title") or "(无标题)"
    year = p.get("year") or "?"
    venue = p.get("venue") or ""
    cites = p.get("citationCount")
    cites_s = f"被引 {cites}" if cites is not None else "被引 ?"
    url = p.get("url") or ""
    venue_s = f" · {venue}" if venue else ""
    lines = [
        f"{i}. 《{title}》",
        f"   {fmt_authors(p.get('authors'))}（{year}）{venue_s} · {cites_s}",
    ]
    if url:
        lines.append(f"   链接：{url}")
    abstract = (p.get("abstract") or "").strip()
    if abstract:
        short = abstract[:200].replace("\n", " ")
        if len(abstract) > 200:
            short += "…"
        lines.append(f"   摘要：{short}")
    return "\n".join(lines)


def save_to_list(papers, path, topic):
    """追加到待读清单，按主题分组，标题去重。"""
    try:
        existing = open(path, encoding="utf-8").read() if __import__("os").path.exists(path) else ""
    except OSError:
        existing = ""
    new_lines = []
    for p in papers:
        title = p.get("title") or ""
        if title and title not in existing:
            url = p.get("url") or ""
            new_lines.append(f"- 《{title}》({p.get('year') or '?'}) {url}".strip())
    if not new_lines:
        print("没有新论文需要保存（可能已存在）。")
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n## {topic}\n")
        f.write("\n".join(new_lines) + "\n")
    print(f"已保存 {len(new_lines)} 篇到 {path}")


def main():
    ap = argparse.ArgumentParser(description="按主题检索学术论文")
    ap.add_argument("--query", required=True, help="英文检索关键词")
    ap.add_argument("--limit", type=int, default=8, help="返回篇数（默认8）")
    ap.add_argument("--sort", choices=["relevance", "citations"], default="relevance",
                    help="relevance=相关度，citations=按被引数排序")
    ap.add_argument("--year-from", type=int, default=None, help="只看某年之后的论文")
    ap.add_argument("--save", action="store_true", help="保存到待读清单 reading_list.md")
    ap.add_argument("--save-path", default="reading_list.md", help="待读清单路径")
    args = ap.parse_args()

    papers, source = search(args.query, args.limit, args.sort, args.year_from)
    if not papers:
        print("没有找到相关论文，换个关键词试试。")
        return
    print(f"主题：{args.query}（共 {len(papers)} 篇，来源：{source}）\n")
    for i, p in enumerate(papers, 1):
        print(fmt_paper(i, p))
        print()
        time.sleep(0.2)  # 打印间隔，避免刷屏

    if args.save:
        save_to_list(papers, args.save_path, args.query)


if __name__ == "__main__":
    main()
