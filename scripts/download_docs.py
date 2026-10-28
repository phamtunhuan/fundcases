#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""并发下载纪律处分原文（PDF / HTML）到本地 data/raw/docs/。"""
import json
import os
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / "data" / "cases_raw_list.json"
DOCS = ROOT / "data" / "raw" / "docs"
DOCS.mkdir(parents=True, exist_ok=True)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def local_name(item, idx):
    base = urllib.parse.unquote(item["url"].rsplit("/", 1)[-1])
    safe = "".join(c for c in base if c not in ' /\\:*?"<>|')
    return f"{idx:04d}_{safe}"


def download(task):
    idx, item = task
    path = DOCS / local_name(item, idx)
    if path.exists() and path.stat().st_size > 1024:
        return idx, "skip", path.name
    for attempt in range(3):
        try:
            req = urllib.request.Request(item["url"], headers={
                "User-Agent": UA,
                "Referer": "https://www.amac.org.cn/zlgl/jlcf/scfjg/index.html",
            })
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if len(data) < 512:
                raise ValueError("too small")
            path.write_bytes(data)
            return idx, "ok", path.name
        except Exception as e:
            if attempt == 2:
                return idx, f"fail:{e}", path.name
            time.sleep(1.5 * (attempt + 1))
    return idx, "fail", path.name


def main():
    items = json.loads(LIST.read_text(encoding="utf-8"))
    tasks = list(enumerate(items))
    ok = skip = fail = 0
    fails = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(download, t) for t in tasks]
        for n, f in enumerate(as_completed(futs), 1):
            idx, status, name = f.result()
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            else:
                fail += 1
                fails.append((idx, name, status))
            if n % 50 == 0:
                print(f"  {n}/{len(tasks)} ok={ok} skip={skip} fail={fail}",
                      flush=True)
    print(f"完成: ok={ok} skip={skip} fail={fail}")
    if fails:
        (ROOT / "data" / "download_fails.json").write_text(
            json.dumps(fails, ensure_ascii=False, indent=2), encoding="utf-8")
        print("失败列表 -> data/download_fails.json")


if __name__ == "__main__":
    main()
