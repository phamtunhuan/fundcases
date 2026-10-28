#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过中国证券投资基金业协会公示系统确认私募基金管理人类型。

查询链路：
  1) 在册机构列表  POST /amac-infodisc/api/pof/manager/query   -> primaryInvestType
  2) 已注销机构列表 POST /amac-infodisc/api/cancelled/manager  -> userTenantId
     2b) 已注销机构详情 GET /res/cancelled/manager/{id}.html   -> 机构类型

输出 data/manager_types.json：机构名 -> 类型/地区/法定代表人/会员类型/登记编号/状态/匹配方式
"""
from __future__ import annotations

import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

BASE = "https://gs.amac.org.cn"
API_ACTIVE = BASE + "/amac-infodisc/api/pof/manager/query?page=0&size=20"
API_CANCEL = BASE + "/amac-infodisc/api/cancelled/manager?page=0&size=20"
DETAIL_CANCEL = BASE + "/amac-infodisc/res/cancelled/manager/{tid}.html"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

HDR_ACTIVE = {
    "User-Agent": UA,
    "Content-Type": "application/json",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE + "/amac-infodisc/res/pof/manager/managerList.html",
    "Origin": BASE,
}
HDR_CANCEL = dict(HDR_ACTIVE,
                  Referer=BASE + "/amac-infodisc/res/cancelled/manager/index.html")

# 协会机构类型的标准取值
VALID_TYPES = {
    "私募证券投资基金管理人",
    "私募股权、创业投资基金管理人",
    "私募股权投资基金管理人",
    "创业投资基金管理人",
    "其他私募投资基金管理人",
    "私募资产配置类管理人",
}
# 页面偶尔出现的旧口径，统一映射到标准取值
TYPE_ALIAS = {
    "私募股权投资基金管理人": "私募股权、创业投资基金管理人",
    "创业投资基金管理人": "私募股权、创业投资基金管理人",
}


def _post(url: str, payload: dict, headers: dict, tries: int = 3, timeout: int = 25):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                return {"__error__": f"{type(e).__name__}: {e}"}
            time.sleep(1.5 * (i + 1) + random.random())
    return {"__error__": "unknown"}


def _get(url: str, tries: int = 3, timeout: int = 25) -> str:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            if i == tries - 1:
                return ""
        except Exception:  # noqa: BLE001
            if i == tries - 1:
                return ""
        time.sleep(1.2 * (i + 1) + random.random())
    return ""


TAG = re.compile(r"</?em>")


def clean(s: str) -> str:
    """去掉高亮标签与空白。"""
    return TAG.sub("", (s or "")).replace(" ", "").replace("\u3000", "").strip()


def norm_name(s: str) -> str:
    """机构名归一化：去高亮、去空白、去常见括号内容差异。"""
    s = clean(s)
    s = s.replace("（", "(").replace("）", ")")
    return s


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_name(a), norm_name(b)).ratio()


def pick_best(query: str, candidates: list[str], threshold: float = 0.82):
    """从候选机构名中挑最匹配的；要求足够相似，避免张冠李戴。"""
    q = norm_name(query)
    best, best_score = None, 0.0
    for c in candidates:
        cn = norm_name(c)
        if not cn:
            continue
        if q == cn:
            return c, 1.0
        score = similarity(q, c)
        # 包含关系加权（"上海高毅" ⊂ "上海高毅资产管理合伙企业（有限合伙）"）
        if q in cn or cn in q:
            score = max(score, 0.90)
        if score > best_score:
            best, best_score = c, score
    if best_score >= threshold:
        return best, best_score
    return None, best_score


# ---------- 在册机构 ----------
def query_active(name: str):
    resp = _post(API_ACTIVE, {"keyword": name, "page": "0", "size": "20"}, HDR_ACTIVE)
    if "__error__" in resp or not resp.get("content"):
        return None
    rows = resp["content"]
    names = [clean(r.get("managerName", "")) for r in rows]
    hit, score = pick_best(name, names)
    if not hit:
        return None
    row = next(r for r in rows if clean(r.get("managerName", "")) == hit)
    ptype = (row.get("primaryInvestType") or "").strip()
    if ptype and ptype not in VALID_TYPES:
        ptype = TYPE_ALIAS.get(ptype, ptype)
    return {
        "matched_name": hit,
        "manager_type": ptype,
        "match_score": round(score, 3),
        "status": "在册",
        "register_no": row.get("registerNo", ""),
        "legal_rep": row.get("artificialPersonName", ""),
        "member_type": row.get("memberType", ""),
        "fund_count": row.get("fundCount"),
        "register_province": row.get("registerProvince", ""),
        "office_province": row.get("officeProvince", ""),
        "office_address": row.get("officeAddress", ""),
        "register_date": row.get("registerDate"),
        "source": "amac_registry_active",
        "detail_url": BASE + "/amac-infodisc/res/pof/manager/" + (row.get("url") or ""),
    }


# ---------- 已注销机构 ----------
DETAIL_TYPE = re.compile(
    r'<td[^>]*class="title"[^>]*>\s*机构类型\s*</td>\s*<td[^>]*>(.*?)</td>', re.S)
DETAIL_ROWS = re.compile(
    r'<td[^>]*class="title"[^>]*>\s*([^<]{2,10}?)\s*</td>\s*<td[^>]*>(.*?)</td>', re.S)


def _strip(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment or "")).strip()


def query_cancelled(name: str):
    resp = _post(API_CANCEL, {"keyword": name, "page": "0", "size": "20"}, HDR_CANCEL)
    if "__error__" in resp or not resp.get("content"):
        return None
    rows = resp["content"]
    names = [clean(r.get("orgName", "")) for r in rows]
    hit, score = pick_best(name, names)
    if not hit:
        return None
    row = next(r for r in rows if clean(r.get("orgName", "")) == hit)
    tid = row.get("userTenantId")
    out = {
        "matched_name": hit,
        "manager_type": "",
        "match_score": round(score, 3),
        "status": "已注销",
        "cancel_date": row.get("cancelDate"),
        "source": "amac_registry_cancelled",
        "detail_url": DETAIL_CANCEL.format(tid=tid) if tid else "",
    }
    if not tid:
        return out
    html = _get(DETAIL_CANCEL.format(tid=tid))
    if not html:
        return out
    m = DETAIL_TYPE.search(html)
    if m:
        t = _strip(m.group(1))
        out["manager_type"] = TYPE_ALIAS.get(t, t) if t in TYPE_ALIAS else t
    for k, v in DETAIL_ROWS.findall(html):
        key, val = _strip(k), _strip(v)
        if not val:
            continue
        if key == "机构类型" and not out["manager_type"]:
            out["manager_type"] = TYPE_ALIAS.get(val, val)
        elif key in ("法定代表人/执行事务合伙人(委派代表)",
                     "法定代表人/执行事务合伙人", "法定代表人") and "legal_rep" not in out:
            out["legal_rep"] = val
        elif key in ("注册地", "注册地址") and "register_province" not in out:
            out["register_province"] = val
        elif key == "注销类型" and "cancel_type" not in out:
            out["cancel_type"] = val
        elif key == "登记编号" and "register_no" not in out:
            out["register_no"] = val
    return out


def lookup(name: str, sleep: float = 0.35):
    r = query_active(name)
    time.sleep(sleep)
    if r and r.get("manager_type"):
        return r
    r2 = query_cancelled(name)
    time.sleep(sleep)
    if r2 and r2.get("manager_type"):
        return r2
    # 两者都命中但类型缺失时，保留状态信息（至少能确认在册/注销）
    return r or r2


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4

    cases = json.load(open(DATA / "amac_penalty_cases.json", encoding="utf-8"))
    names = sorted({c["org_primary"] for c in cases if c.get("org_primary")})
    if limit:
        names = names[:limit]

    cache_path = DATA / "manager_types.json"
    cache = {}
    if cache_path.exists():
        cache = json.load(open(cache_path, encoding="utf-8"))
    todo = [n for n in names if n not in cache]
    print(f"机构 {len(names)} 个，已缓存 {len(cache)}，待查 {len(todo)}")

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for name, res in zip(todo, ex.map(lookup, todo)):
            done += 1
            cache[name] = res or {"manager_type": "", "status": "未查到",
                                  "source": "not_found"}
            if done % 25 == 0 or done == len(todo):
                hit = sum(1 for v in cache.values() if v.get("manager_type"))
                print(f"  {done}/{len(todo)}  类型命中 {hit}", flush=True)
                json.dump(cache, open(cache_path, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)

    json.dump(cache, open(cache_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    ok = sum(1 for v in cache.values() if v.get("manager_type"))
    print(f"\n完成：{len(cache)} 个机构，类型命中 {ok}（{ok/len(cache):.1%}）")


if __name__ == "__main__":
    main()
