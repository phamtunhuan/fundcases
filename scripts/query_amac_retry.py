#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""针对仍未命中的机构，用多种名称变体重查 AMAC（在册+注销）。"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from query_amac_type import DATA, query_active, query_cancelled  # noqa: E402

CACHE = DATA / "manager_types.json"

SUFFIX = [
    "私募基金管理有限公司", "私募基金管理合伙企业（有限合伙）",
    "股权投资基金管理有限公司", "投资基金管理有限公司",
    "基金管理有限公司", "资产管理有限公司", "投资管理有限公司",
    "投资有限公司", "基金管理合伙企业（有限合伙）",
    "资产管理合伙企业（有限合伙）", "有限公司",
]
CITY = ["上海", "北京", "深圳", "珠海", "厦门", "济南", "青岛", "天津",
        "杭州", "宁波", "广州", "南京", "成都", "武汉"]


def variants(name: str):
    """生成候选查询串：去括号、去城市前缀、去公司后缀的核心字号等。"""
    out = [name]
    base = re.sub(r"[（(].*?[)）]", "", name).strip()
    if base and base not in out:
        out.append(base)
    # 去后缀
    core = base
    for suf in SUFFIX:
        if core.endswith(suf):
            core = core[: -len(suf)]
            break
    core = core.rstrip("管理")
    if core and core not in out:
        out.append(core)
    # 去城市前缀
    cityless = core
    for c in CITY:
        if cityless.startswith(c):
            cityless = cityless[len(c):]
            break
    if cityless and cityless != core and cityless not in out:
        out.append(cityless)
    return [x for x in out if len(x) >= 2]


def main():
    cache = json.load(open(CACHE, encoding="utf-8"))
    miss = [k for k, v in cache.items() if not v.get("manager_type")]
    print(f"重查 {len(miss)} 家未命中机构")
    fixed = 0
    for name in miss:
        hit = None
        for q in variants(name):
            r = query_active(q)
            time.sleep(0.35)
            if r and r.get("manager_type"):
                hit = r
                break
            r2 = query_cancelled(q)
            time.sleep(0.35)
            if r2 and r2.get("manager_type"):
                hit = r2
                break
        if hit:
            hit["note"] = f"变体「{q}」命中，原登记名可能已变更"
            cache[name] = hit
            fixed += 1
            print(f"  ✓ {name} -> {hit['matched_name']} ({hit['manager_type']}, {hit.get('status')})")
        else:
            print(f"  ✗ {name} 仍未命中（判定为已更名）")
            cache[name] = {"manager_type": "", "status": "未查到",
                           "source": "not_found",
                           "note": "协会在册/注销两处均无记录，推定管理人已变更名称"}
    json.dump(cache, open(CACHE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    still = sum(1 for v in cache.values() if not v.get("manager_type"))
    print(f"\n新命中 {fixed}，仍缺 {still}/{len(cache)}")


if __name__ == "__main__":
    main()
