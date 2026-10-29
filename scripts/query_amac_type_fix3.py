#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第四轮：核心字号查询，命中即视为管理人更名。"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from query_amac_type import DATA, query_active, query_cancelled, clean  # noqa: E402

CACHE = DATA / "manager_types.json"
CITIES = ["上海", "深圳", "北京", "珠海", "厦门", "晋江", "青岛", "济南",
          "武汉", "横琴", "前海", "中投", "横琴风满楼"]


def core_of(name: str) -> str:
    s = re.sub(r"[（(].*", "", name)
    for pre in CITIES:
        if s.startswith(pre):
            s = s[len(pre):]
            break
    s = re.sub(r"(投资|资产|基金|私募|股权|创业|产业)", "", s)
    s = re.sub(r"(股份有限公司|有限责任公司|有限公司|责任公司|管理中心|中心)$", "", s)
    s = s.rstrip("管理")
    return s


def main():
    cache = json.load(open(CACHE, encoding="utf-8"))
    miss = [k for k, v in cache.items() if not v.get("manager_type")]
    print(f"核心字号查询 {len(miss)} 条")
    found = 0
    for name in miss:
        core = core_of(name)
        if len(core) < 2:
            continue
        r = query_active(core)
        time.sleep(0.3)
        hit = r if (r and r.get("manager_type")) else None
        if not hit:
            r2 = query_cancelled(core)
            time.sleep(0.3)
            if r2 and r2.get("manager_type"):
                hit = r2
        if hit:
            hit["alias_of"] = core
            hit["note"] = f"核心字号「{core}」命中，疑似更名（原登记名 {name}）"
            cache[name] = hit
            found += 1
            print(f"  ✓ {name} -> {hit['matched_name']} ({hit['manager_type']})")
        else:
            print(f"  ✗ {name} (字号 {core}) 仍未命中")
    json.dump(cache, open(CACHE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    still = [k for k, v in cache.items() if not v.get("manager_type")]
    print(f"\n新命中 {found}，仍剩 {len(still)}")


if __name__ == "__main__":
    main()
