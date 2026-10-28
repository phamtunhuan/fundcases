#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取中国证券投资基金业协会 纪律处分 -> 受处分机构 栏目列表页。"""
import json
import re
import time
import urllib.request
from pathlib import Path

BASE = "https://www.amac.org.cn/zlgl/jlcf/scfjg/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "list"
RAW.mkdir(parents=True, exist_ok=True)

ITEM_RE = re.compile(
    r'<li>\s*<span></span>\s*<a href="([^"]+)">([^<]+)</a>\s*<i>\s*([0-9-]+)\s*</i>',
    re.S)


def page_url(i: int) -> str:
    return BASE + ("index.html" if i == 1 else f"index_{i}.html")


def fetch(url: str, retries=3) -> str:
    for n in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            if n == retries - 1:
                raise
            time.sleep(2 * (n + 1))
    return ""


def main():
    items = []
    total_pages = None
    for i in range(1, 35):  # 1..34
        html = fetch(page_url(i))
        (RAW / (f"index_{i}.html" if i > 1 else "index.html")).write_text(
            html, encoding="utf-8")
        m = re.search(r'createPageHTML\((\d+),\s*(\d+)', html)
        if m:
            total_pages = int(m.group(1))
        found = ITEM_RE.findall(html)
        print(f"page {i}: {len(found)} items (total_pages={total_pages})")
        for href, title, date in found:
            title = title.strip()
            href = href.strip()
            doc_type = "pdf" if href.lower().endswith(".pdf") else "html"
            items.append({
                "title": title,
                "date": date.strip(),
                "url": urllib.parse.urljoin(BASE, href),
                "doc_type": doc_type,
                "source_page": i,
            })
        time.sleep(0.6)

    # 去重（按 url）
    seen, uniq = set(), []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)

    out = ROOT / "data" / "cases_raw_list.json"
    out.write_text(json.dumps(uniq, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n总条数(去重后): {len(uniq)}  -> {out}")
    years = {}
    for it in uniq:
        years[it["date"][:4]] = years.get(it["date"][:4], 0) + 1
    print("年份分布:", dict(sorted(years.items())))


if __name__ == "__main__":
    import urllib.parse
    main()
