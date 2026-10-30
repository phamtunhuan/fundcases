#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对账：重新抓取协会「受处分机构」全部列表页，与既有 cases_raw_list.json 比对。

用途：检查是否存在遗漏条目（如分页数增长、条目改期、URL 变更）。
只读，不覆盖既有数据；结果写入 data/audit_list_diff.json。
"""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.amac.org.cn/zlgl/jlcf/scfjg/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "audit_list_diff.json"

# 官方站列表项结构：<li><span></span><a href="...">标题</a><i>日期</i>
ITEM_RE = re.compile(
    r'<li>\s*<span></span>\s*<a href="([^"]+)"[^>]*>([^<]+)</a>\s*<i>\s*([0-9-]+)\s*</i>',
    re.S)
# 兜底：任意 <a href="....shtml|pdf"> 配 <i>日期</i>
ITEM_LOOSE = re.compile(
    r'<a href="([^"]+)"[^>]*>([^<]{4,})</a>\s*<i>\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\s*</i>',
    re.S)


def fetch(url, retries=3, timeout=40):
    for n in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            if n == retries - 1:
                print(f"  ! 抓取失败 {url}: {type(e).__name__}")
                return ""
            time.sleep(2 * (n + 1))
    return ""


def page_url(i):
    return BASE + ("index.html" if i == 1 else f"index_{i}.html")


def main():
    first = fetch(page_url(1))
    m = re.search(r"createPageHTML\((\d+)", first)
    total = int(m.group(1)) if m else 1
    print(f"协会列表总页数（createPageHTML）: {total}")

    items, per_page = [], {}
    for i in range(1, total + 1):
        html = first if i == 1 else fetch(page_url(i))
        got = ITEM_RE.findall(html)
        if not got:
            got = ITEM_LOOSE.findall(html)
        per_page[i] = len(got)
        for href, title, date in got:
            items.append({
                "title": re.sub(r"\s+", " ", title).strip(),
                "date": date.strip(),
                "url": urllib.parse.urljoin(BASE, href.strip()),
                "source_page": i,
            })
        print(f"  page {i:>2}: {len(got)} 条")
        if i > 1:
            time.sleep(0.5)

    # 去重
    seen, uniq = set(), []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)
    print(f"\n本次抓到 {len(items)} 条，去重后 {len(uniq)} 条")

    old = json.loads((ROOT / "data" / "cases_raw_list.json").read_text(encoding="utf-8"))
    old_urls = {it["url"] for it in old}
    new_urls = {it["url"] for it in uniq}
    print(f"既有数据 {len(old)} 条")

    added = [it for it in uniq if it["url"] not in old_urls]
    removed = [it for it in old if it["url"] not in new_urls]
    print(f"\n新增（站上有、库里无）: {len(added)}")
    for it in added[:50]:
        print(f"  + [{it['date']}] p{it['source_page']:>2} {it['title'][:60]}")
    print(f"消失（库里有、站上无）: {len(removed)}")
    for it in removed[:20]:
        print(f"  - [{it['date']}] {it['title'][:60]}")

    OUT.write_text(json.dumps({
        "total_pages": total, "per_page": per_page,
        "crawled": len(uniq), "existing": len(old),
        "added": added, "removed": removed,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n差异清单 -> {OUT}")


if __name__ == "__main__":
    main()
