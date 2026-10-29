#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三轮：对 28 个「未查到」机构做激进名称变体查询，应对管理人更名。"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from query_amac_type import ROOT, DATA, query_active, query_cancelled, pick_best, _post, clean  # noqa: E402

CACHE = DATA / "manager_types.json"

SUFFIX_RE = re.compile(r"(?:股份有限公司|有限责任公司|有限公司|责任公司)$")
CITY_BRACKET = re.compile(r"^[^（(]*[（(]?")


def variants(name: str):
    """为改名机构生成尽量多的查询变体（协会关键词是连续子串匹配）。"""
    out = []
    base = name
    # 全半角统一
    out.append(base.replace("（", "(").replace("）", ")"))
    # 去掉结尾法律形态
    s = SUFFIX_RE.sub("", base)
    if s != base:
        out.append(s)
    # 去掉中间的（北京）等地名括号
    s2 = re.sub(r"[（(][\u4e00-\u9fa5]{2,4}[）)]", "", base)
    if s2 and s2 != base:
        out.append(s2)
        out.append(SUFFIX_RE.sub("", s2))
    # 去掉「投资/资产管理/基金管理/私募基金」等中间词，只留字号核心
    core = re.sub(r"(投资|资产管理|基金管理|私募基金|股权|创业)", "", s2)
    core = SUFFIX_RE.sub("", core)
    if core and len(core) >= 2:
        out.append(core)
    # 去重保序
    seen, res = set(), []
    for v in out:
        v = v.strip()
        if v and v not in seen and len(v) >= 2:
            seen.add(v)
            res.append(v)
    return res


def main():
    cache = json.load(open(CACHE, encoding="utf-8"))
    miss = [k for k, v in cache.items() if not v.get("manager_type")]
    print(f"待修复 {len(miss)}")

    found = 0
    for name in miss:
        done = False
        for v in variants(name):
            if v == name or v in name or name in v:
                continue
            r = query_active(v)
            time.sleep(0.3)
            if r and r.get("manager_type"):
                r["alias_of"] = v
                r["note"] = f"经变体「{v}」命中"
                cache[name] = r
                found += 1
                print(f"  ✓ 在册  {name} -> {v} -> {r['manager_type']}")
                done = True
                break
            r2 = query_cancelled(v)
            time.sleep(0.3)
            if r2 and r2.get("manager_type"):
                r2["alias_of"] = v
                r2["note"] = f"经变体「{v}」命中"
                cache[name] = r2
                found += 1
                print(f"  ✓ 注销  {name} -> {v} -> {r2['manager_type']}")
                done = True
                break
        if not done:
            print(f"  ✗ 仍未命中 {name}")

    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    still = [k for k, v in cache.items() if not v.get("manager_type")]
    print(f"\n本轮新命中 {found}，仍剩 {len(still)}:")
    for k in still:
        print(" -", k)


if __name__ == "__main__":
    main()
