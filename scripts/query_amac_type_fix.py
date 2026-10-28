#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二轮：对未命中的 45 个机构做变体修复与人工映射后重查。"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from query_amac_type import (ROOT, query_active, query_cancelled,  # noqa: E402
                             DATA)

CACHE = DATA / "manager_types.json"

# 从复核决定书正文确认的简称 -> 登记全称
FULL_NAME = {
    "伟大基金": "湖南伟大股权投资基金管理有限公司",
    "嘉兴投资": "嘉兴菲南斯投资管理有限公司",
    "海南凯什": "海南省凯什私募基金管理有限公司",
    "深圳斯沃普": "深圳市斯沃普资产管理有限公司",  # OCR 亦作「斯洪普」
    "新毅投资": "新毅投资基金管理（北京）有限公司",
    "米多资产": "米多资产管理（北京）有限公司",
}

# 不属于私募管理人公示范围的自律对象（公募基金/券商/基金子公司/销售机构）
NON_PRIVATE = {
    "上银基金管理有限公司": "公募基金管理公司",
    "东海证券股份有限公司": "证券公司",
    "九泰基金管理有限公司": "公募基金管理公司",
    "兴业全球基金管理有限公司": "公募基金管理公司（现兴全基金）",
    "恒泰证券股份有限公司": "证券公司",
    "民生加银资产管理有限公司": "公募基金子公司（专户）",
    "中信信诚资产管理有限公司": "公募基金子公司（专户）",
    "首誉光控资产管理有限公司": "公募基金子公司（专户）",
    "和合资产管理（上海）有限公司": "券商资管/基金子公司",
    "北京格上富信基金销售有限公司": "基金销售机构",
    "国都京融（深圳）投资有限公司": "证券公司子公司",
}


def variants(name: str):
    """生成重查用的名称变体。"""
    out = []
    # 全半角统一
    if "(" in name or ")" in name:
        out.append(name.replace("(", "（").replace(")", "）"))
    # 去掉重复的「公司」
    if name.endswith("公司公司"):
        out.append(name[:-2])
    # 去掉中间的（北京）等地名括号，拼成主词（协会关键词是连续匹配）
    m = re.search(r"^(.{2,12})[（(]([\u4e00-\u9fa5]{2,3})[）)](.+)$", name)
    if m and m.group(3).startswith(("投资", "基金", "资产", "私募", "股权")):
        out.append(m.group(1) + m.group(3))
    return out


def main():
    cache = json.load(open(CACHE, encoding="utf-8"))
    miss = [k for k, v in cache.items() if not v.get("manager_type")]
    print(f"待修复 {len(miss)}")

    # 1) 非私募机构直接标注
    for name in miss:
        if name in NON_PRIVATE:
            cache[name] = {
                "matched_name": name,
                "manager_type": f"非私募管理人（{NON_PRIVATE[name]}）",
                "match_score": 1.0,
                "status": "不适用",
                "source": "manual_classification",
                "note": "自律对象但不在私募管理人公示范围",
            }

    # 2) 简称 -> 全称重查
    for short, full in FULL_NAME.items():
        if short in miss:
            r = query_active(full) or query_cancelled(full)
            time.sleep(0.4)
            if r and r.get("manager_type"):
                r["alias_of"] = full
                cache[short] = r
                print(f"  简称命中 {short} -> {full} ({r['manager_type']})")
            else:
                # 全称也查不到，用全称的核心词再试
                key = re.sub(r"[（(].*?[）)]", "", full)
                r2 = query_active(key) or query_cancelled(key)
                time.sleep(0.4)
                if r2 and r2.get("manager_type"):
                    r2["alias_of"] = full
                    cache[short] = r2
                    print(f"  简称(核心词)命中 {short} -> {key}")

    # 3) 变体重查
    for name in [k for k, v in cache.items() if not v.get("manager_type")]:
        for v in variants(name):
            r = query_active(v) or query_cancelled(v)
            time.sleep(0.4)
            if r and r.get("manager_type"):
                cache[name] = r
                print(f"  变体命中 {name} -> {r['matched_name']}")
                break

    # 4) 最后兜底：去掉括号内容用主词查
    for name in [k for k, v in cache.items() if not v.get("manager_type")]:
        key = re.sub(r"[（(].*?[）)]", "", name).strip()
        if key and key != name:
            r = query_active(key) or query_cancelled(key)
            time.sleep(0.4)
            if r and r.get("manager_type"):
                cache[name] = r
                print(f"  主词命中 {name} -> {r['matched_name']}")

    json.dump(cache, open(CACHE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    still = [k for k, v in cache.items() if not v.get("manager_type")]
    print(f"\n仍未命中 {len(still)}:")
    for k in still:
        print(" -", k)


if __name__ == "__main__":
    main()
