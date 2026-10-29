#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三轮修补：壳页（HTML 只有附件链接）下载附件 PDF + OCR 补全正文，再重测措施/事由。

处理的是 doc_type 为「纪律处分决定书 / 复核决定书」但正文过短（<1000 字）的壳页。
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SRC = DATA / "amac_penalty_cases.json"
RAW_DOCS = DATA / "raw" / "docs"

sys.path.insert(0, str(ROOT / "scripts"))
from ocr_vision import ocr_pdf  # noqa: E402
from build_json import (normalize, reflow, decision_section, PENALTY_RULES,
                        VIOLATION_RULES, EXCLUSIVE, penalty_sentences)  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def download(url: str, dst: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            dst.write_bytes(r.read())
        return dst.stat().st_size > 5000
    except Exception as e:  # noqa: BLE001
        print(f"  下载失败 {url[-50:]}: {e}")
        return False


def detect_all(norm: str):
    """重测处罚措施与违规事由。"""
    sec = decision_section(norm)
    scope = sec + "\n" + norm[:1500]
    penalties = []
    for label, pat in PENALTY_RULES:
        if re.search(pat, scope):
            penalties.append(label)
    for high, low in EXCLUSIVE:
        if high in penalties and low in penalties:
            penalties.remove(low)
    violations = [l for l, pat in VIOLATION_RULES if re.search(pat, norm)]
    sents = penalty_sentences(norm)
    penalty_text = "；".join(sents)[:600]
    return penalties, violations, penalty_text


def main():
    cases = json.load(open(SRC, encoding="utf-8"))
    by_id = {c["id"]: c for c in cases}

    # 找出需要补正文的壳页
    need = [c for c in cases
            if c["doc_type"] in ("纪律处分决定书", "纪律处分复核决定书")
            and c["text_length"] < 1000]
    print(f"壳页(正文<1000字)决定书类: {len(need)} 条")

    fixed = 0
    for c in need:
        # 从本地 HTML 提取附件 PDF 相对路径
        hpath = ROOT / c["local_file"]
        if not hpath.exists():
            print(f"  [skip] {c['org_primary'][:18]} 本地HTML不存在")
            continue
        h = hpath.read_text(encoding="utf-8", errors="ignore")
        attach = h.find("附件下载")
        m = re.search(r'<li><a href="([^"]+\.pdf)"', h[attach:attach + 4000]) if attach > 0 else None
        if not m:
            print(f"  [skip] {c['org_primary'][:18]} 未找到附件PDF链接")
            continue

        rel = m.group(1).lstrip("./")
        base = c["source_url"].rsplit("/", 1)[0]
        url = f"{base}/{rel}"
        fname = f"{c['id']:04d}_{Path(rel).name}"
        dst = RAW_DOCS / fname
        if not dst.exists():
            ok = download(url, dst)
            if not ok:
                print(f"  [fail] {c['org_primary'][:18]} 附件下载失败")
                continue

        try:
            text = ocr_pdf(dst)
        except Exception as e:  # noqa: BLE001
            print(f"  [ocrfail] {c['org_primary'][:18]}: {e}")
            continue

        norm = normalize(reflow(text))
        if len(norm) < 300:
            print(f"  [short] {c['org_primary'][:18]} OCR 过短({len(norm)})")
            continue

        c["text"] = text
        c["text_length"] = len(text)
        c["local_file"] = f"data/raw/docs/{fname}"
        p, v, pt = detect_all(norm)
        c["penalties"] = p
        c["penalty_text"] = pt
        c["decision_text"] = decision_section(norm)[:1200]
        c["violation_tags"] = v
        c["text_source"] = "附件PDF-OCR"
        fixed += 1
        print(f"  [ok] {c['org_primary'][:20]:22s} 正文{len(text):5d}字 "
              f"措施{p} 事由{v}")

    SRC.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n补全 {fixed} 条壳页正文")
    # 重新统计
    none_pen = sum(1 for c in cases if not c["penalties"]
                   and c["doc_type"] in ("纪律处分决定书", "纪律处分复核决定书"))
    none_v = sum(1 for c in cases if not c["violation_tags"]
                 and c["doc_type"] in ("纪律处分决定书", "纪律处分复核决定书"))
    print(f"决定书无措施: {none_pen} | 无违规事由: {none_v}")


if __name__ == "__main__":
    main()
