#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成网站用数据：docs/data/cases.json（索引） + docs/data/texts.json（正文，懒加载）"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "amac_penalty_cases.json"
DOCS = ROOT / "docs" / "data"
DOCS.mkdir(parents=True, exist_ok=True)

cases = json.loads(SRC.read_text(encoding="utf-8"))
index, texts = [], {}
for c in cases:
    texts[str(c["id"])] = c["text"]
    # decision_text 与正文高度重复，不进索引（仍保留在完整 JSON 中）
    index.append({k: v for k, v in c.items()
                  if k not in ("text", "decision_text")})

(DOCS / "cases.json").write_text(
    json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
(DOCS / "texts.json").write_text(
    json.dumps(texts, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"cases.json {len(index)} 条, texts.json {len(texts)} 条 -> {DOCS}")
