#!/usr/bin/env python3
"""诊断剩余无处分措施案例：逐条检查 penalty_sentences / detect_penalties 为何漏判。"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_json import (load_text, reflow, normalize, detect_penalties,
                        penalty_sentences, decision_section, normalize as _norm_fn)  # noqa: E402

items = json.load(open(ROOT / "data" / "cases_raw_list.json", encoding="utf-8"))
cases = json.load(open(ROOT / "data" / "amac_penalty_cases.json", encoding="utf-8"))

names = sys.argv[1:] if len(sys.argv) > 1 else None

for c in cases:
    if not c["penalties"] and c["doc_type"] in ("纪律处分决定书", "纪律处分复核决定书"):
        if names and not any(n in c["org_primary"] for n in names):
            continue
        idx = c["id"] - 1
        raw = load_text(idx, items[idx]["url"])
        text = reflow(raw)
        norm = normalize(text)
        sents = penalty_sentences(norm)
        sec = decision_section(norm)[:150]
        print(f"### {c['org_primary'][:24]}")
        print(f"  sentences: {sents}")
        # 找决策句原始文本
        m = re.search(r'[^。；]{0,40}(?:纪律处分|处分)[：:]\s*([^。；]{4,120})', norm)
        print(f"  候选句: {re.sub(chr(10),'',m.group(0))[:120] if m else '(无)'}")
        print(f"  decision_sec: {re.sub(chr(10),'',sec)[:100]}")
        print(f"  detect: {detect_penalties(norm)}")
        print()
