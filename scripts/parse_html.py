#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抽取网页版（非扫描）纪律处分决定书正文，输出到 data/ocr/<stem>.txt。"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "data" / "raw" / "docs"
OUT = ROOT / "data" / "ocr"
OUT.mkdir(parents=True, exist_ok=True)


def clean(frag: str) -> str:
    frag = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', frag, flags=re.S | re.I)
    frag = re.sub(r'<br\s*/?>', '\n', frag, flags=re.I)
    frag = re.sub(r'</p>', '\n', frag, flags=re.I)
    frag = re.sub(r'<[^>]+>', '', frag)
    frag = (frag.replace('&nbsp;', ' ')
                .replace('&amp;', '&')
                .replace('&ldquo;', '“').replace('&rdquo;', '”')
                .replace('&mdash;', '—').replace('&quot;', '"'))
    frag = re.sub(r'[ \t\u3000]+', ' ', frag)
    frag = re.sub(r'\n\s*\n+', '\n', frag)
    return frag.strip()


def extract(path: Path):
    raw = path.read_bytes()
    for enc in ("utf-8", "gb18030"):
        try:
            h = raw.decode(enc)
            break
        except Exception:
            continue
    else:
        h = raw.decode("utf-8", "ignore")

    m = re.search(r'<div class="content">(.*?)(?:</body>|<div class="(?:share|foot|page))',
                  h, re.S)
    if not m:
        m = re.search(r'<div class="job-tit".*?</div>(.*?)</body>', h, re.S)
    if not m:
        return None, None
    body = clean(m.group(1))
    title = None
    tm = re.search(r'<div class="job-tit"[^>]*>(.*?)</div>', h, re.S)
    if tm:
        title = clean(tm.group(1))
    return title, body


def main():
    files = sorted(DOCS.glob("*.html"))
    ok = empty = 0
    for f in files:
        title, body = extract(f)
        if body and len(body) > 100:
            (OUT / (f.stem + ".txt")).write_text(body, encoding="utf-8")
            ok += 1
        else:
            empty += 1
            print(f"  空/失败: {f.name}")
    print(f"HTML 正文抽取完成: ok={ok} empty={empty} / {len(files)}")


if __name__ == "__main__":
    main()
