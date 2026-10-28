#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""��合列表元数据 + OCR/HTML 正文，生成结构化案例 JSON。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / "data" / "cases_raw_list.json"
DOCS = ROOT / "data" / "raw" / "docs"
OCR = ROOT / "data" / "ocr"
OUT = ROOT / "data" / "amac_penalty_cases.json"

# ---------- 文书类型 ----------
DOC_TYPES = [
    ("纪律处分复核决定书", "纪律处分复核决定书"),
    ("纪律处分事先告知书送达公告", "纪律处分事先告知书送达公告"),
    ("纪律处分事先告知书", "纪律处分事先告知书"),
    ("纪律处分决定书送达公告", "纪律处分决定书送达公告"),
    ("纪律处分决定书", "纪律处分决定书"),
    ("纪律处分决定", "纪律处分决定"),
]

# ---------- 处分措施 ----------
PENALTY_RULES = [
    ("撤销管理人登记", r"撤销(?:其|该)?(?:私募基金)?管理人登记|撤销登记"),
    ("取消会员资格", r"取消(?:其|该)?(?:协会)?会员资格"),
    ("暂停受理备案", r"暂停(?:受理)?(?:其)?(?:私募基金)?(?:产品)?备案|暂停办理备案"),
    ("公开谴责", r"公开谴责"),
    ("警告", r"(?:给予)?警告"),
    ("通报批评", r"通报批评"),
    ("责令改正", r"责令改正"),
    ("暂停基金从业资格", r"暂停(?:其)?基金从业资格"),
    ("取消基金从业资格", r"取消(?:其)?基金从业资格|认定为不适当人选| unsuitable"),
    ("注销管理人登记", r"注销(?:其)?(?:私募基金)?管理人登记"),
    ("要求限期整改", r"限期整改|要求(?:其)?整改"),
    ("书面警示", r"书面警示"),
    ("约谈高管", r"约见谈话|约谈"),
]

# ---------- 违规事由标签 ----------
VIOLATION_RULES = [
    ("信息报送违规", r"未(?:按|及时|如实)?(?:报送|填报|报告)|信息(?:报送|披露)(?:不(?:及时|真实|准确|完整))|未履行信息报送义务|报送的?信息(?:不|存在)(?:真实|准确|完整)"),
    ("未按规定备案", r"未(?:按规定)?(?:办理)?备案|未(?:及时)?报告(?:重大事项)?变更|重大事项(?:未)?(?:报告|变更)"),
    ("投资者适当性", r"投资者适当性|风险(?:识别|承受)(?:能力)?(?:评估|测评)|适当性管理"),
    ("募集行为违规", r"募集行为|公开(?:宣传|推介)|向不特定对象|承诺(?:保本|保收益|本金|收益)|拆分(?:份额|转让)", ),
    ("未勤勉尽责", r"未(?:履行|尽)(?:勤勉|恪尽职守|诚实信用|谨慎勤勉)|勤勉(?:尽责|义务)|谨慎勤勉义务"),
    ("内控与合规缺失", r"内部控制|内控(?:制度)?|风险管理(?:制度)?|合规(?:管理|风控)(?:负责人)?(?:缺失|未)|风控制度"),
    ("人员与场所不达标", r"无(?:固定)?(?:营业|经营)场所|从业人员(?:不足|少于|缺失)|专职员工|高管(?:缺|未|不在)|法定代表人(?:失联|无法联系)"),
    ("失联或异常经营", r"失联|异常经营|无法(?:取得)?联系|经营(?:异常|场所空置)"),
    ("挪用侵占基金财产", r"挪用(?:基金|募集)?(?:资金|财产|财产)|侵占(?:基金)?财产|占用(?:基金)?财产|资金池"),
    ("利益输送与关联交易", r"利益输送|关联交易|利益冲突|自我交易|关联方(?:交易|资金往来)"),
    ("投资运作违规", r"投资(?:范围|运作|决策)(?:违反|不符合|超出)|违反(?:基金)?合同(?:约定)?投资|高买低卖|约定投资比例"),
    ("杠杆与结构化违规", r"杠杆(?:倍数|比例)|结构化(?:分级|安排)|份额分级|分级(?:基金|资管)"),
    ("信息披露违规", r"信息(?:披露|告知)(?:违规|不(?:及时|真实|完整|充分))|未(?:向)?(?:投资者)?(?:披露|告知)|隐瞒(?:重大)?(?:信息|事项)"),
    ("材料保管不规范", r"未(?:按规定)?妥善保管|材料(?:缺失|未提供|未保存)|未(?:向)?协会提供"),
    ("兼营无关业务", r"兼营|从事(?:与私募基金(?:管理)?(?:无关|冲突)的业务|民间借贷|类金融|融资租赁)"),
    ("登记信息不实", r"登记(?:信息)?(?:不实|虚假|与事实不符)|提供虚假(?:材料|信息)|隐瞒(?:有关)?情况"),
    ("高管与从业人员违规", r"高级管理人(?:员)?(?:违规)?|挂靠|兼职|不具备(?:从业)?资格|未取得基金从业资格"),
    ("基金运作未清算", r"未(?:按[照约定]*|及时|依法)?(?:进行|组织)?清算|未清盘|到期未(?:清算|退出|兑付)|未(?:按)?(?:约定|规定|及时)清算|拒不清算"),
    ("不公平对待投资者", r"不公平(?:对待|处理)(?:投资者)?|区别对待投资者"),
    ("违反量化或程序化交易规定", r"量化|程序化交易|高频交易"),
]

# ---------- 管理人类型 ----------
TYPE_RULES = [
    ("私募证券投资基金管理人", r"私募证券投资基金管理人|证券类(?:私募)?(?:基金)?管理人|私募证券(?:投资)?基金管理人"),
    ("私募股权、创业投资基金管理人", r"私募股权(?:投资)?基金管理人|创业投资基金管理人|私募股权、创业投资|股权类(?:私募)?管理人|私募股权创业投资基金管理人"),
    ("其他私募投资基金管理人", r"其他私募投资基金管理人|其他类(?:私募)?管理人"),
    ("私募资产配置类管理人", r"私募资产配置(?:基金)?管理人"),
]
# 2) 机构名称规则（弱信号）
NAME_TYPE_RULES = [
    ("私募证券投资基金管理人", r"证券投资|证券类|量化|对冲"),
    ("私募股权、创业投资基金管理人", r"股权投资|创业投资|产业投资|并购投资|创投|股权基金"),
]
# 3) 正文词频推断（弱信号）
SEC_SIGNALS = [r"私募证券投资基金", r"证券投资基金", r"证券账户", r"二级市场",
               r"量化", r"期货", r"股票", r"债券", r"可转债", r"沪深",
               r"打新", r"份额净值", r"基金净值", r"证券期货", r"结构化", r"净值披露"]
EQ_SIGNALS = [r"私募股权投资基金", r"创业投资基金", r"未上市企业", r"被投企业",
              r"股权投资", r"股权投资项目", r"实缴出资", r"工商信息", r"投资协议"]


def classify_manager_type(text: str, org_name: str):
    """返回 (类型, 依据)。依据: 正文声明 > 机构名称 > 正文词频 > 未知"""
    for label, pat in TYPE_RULES:
        if re.search(pat, text):
            return label, "正文明确声明"
    if org_name:
        for label, pat in NAME_TYPE_RULES:
            if re.search(pat, org_name):
                return label, "机构名称推断"
    sec = sum(len(re.findall(p, text)) for p in SEC_SIGNALS)
    eq = sum(len(re.findall(p, text)) for p in EQ_SIGNALS)
    if sec - eq >= 3:
        return "私募证券投资基金管理人", "正文词频推断"
    if eq - sec >= 3:
        return "私募股权、创业投资基金管理人", "正文词频推断"
    return "未明确", "证据不足"

CITY_WORDS = [
    "北京", "上海", "天津", "重庆", "深圳", "广州", "珠海", "东莞", "佛山", "汕头",
    "杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "台州", "江苏", "南京",
    "苏州", "无锡", "常州", "南通", "徐州", "山东", "济南", "青岛", "烟台", "潍坊",
    "福建", "福州", "厦门", "泉州", "四川", "成都", "绵阳", "湖北", "武汉", "宜昌",
    "湖南", "长沙", "安徽", "合肥", "芜湖", "河南", "郑州", "洛阳", "河北", "石家庄",
    "唐山", "陕西", "西安", "辽宁", "大连", "沈阳", "吉林", "长春", "黑龙江", "哈尔滨",
    "江西", "南昌", "云南", "昆明", "贵州", "贵阳", "广西", "南宁", "桂林", "海南",
    "海口", "三亚", "甘肃", "兰州", "新疆", "乌鲁木齐", "内蒙古", "呼和浩特", "宁夏",
    "银川", "青海", "西宁", "西藏", "拉萨", "山西", "太原", "香港", "澳门", "台湾",
]

ORG_WORDS = ("公司", "合伙", "基金", "中心", "事务所", "银行", "证券", "资产", "投资",
             "管理", "集团", "研究院", "协会", "信托", "保险", "有限合伙")


def is_org(name: str) -> bool:
    return any(w in name for w in ORG_WORDS) and len(name) >= 4


def local_path(url: str):
    from urllib.parse import unquote
    base = unquote(url.rsplit("/", 1)[-1])
    for f in DOCS.iterdir():
        if f.name.endswith(base):
            return f
    return None


def extract_paren(s: str) -> str:
    """按括号配对提取最外层（）/() 内的内容，兼容嵌套括号与未闭合截断。"""
    start, depth = None, 0
    for i, ch in enumerate(s):
        if ch in "（(":
            if start is None:
                start = i
            depth += 1
        elif ch in "）)":
            if start is not None:
                depth -= 1
                if depth == 0:
                    return s[start + 1:i]
    if start is not None:
        return s[start + 1:]
    m = re.search(r'\[(.*?)\]', s)
    return m.group(1) if m else ""


def parse_title(title: str):
    """从标题解析文书类型与当事人。"""
    t = title.strip()
    doc_type = "其他"
    for kw, label in DOC_TYPES:
        if kw in t:
            doc_type = label
            break
    if "注销" in t and "公告" in t:
        doc_type = "注销登记公告"
    if "送达公告" in t and "告知书" in t:
        doc_type = "纪律处分事先告知书送达公告"

    truncated = t.rstrip().endswith("...") or "…" in t
    raw = extract_paren(t)
    parties = []
    if raw:
        raw = re.sub(r'[,，]', '、', raw)
        for p in raw.split("、"):
            p = p.strip()
            if len(p) >= 2:
                parties.append(p)
    return doc_type, parties, truncated


def pick_text(fname_stem: str) -> str:
    p = OCR / (fname_stem + ".txt")
    if p.exists():
        return p.read_text(encoding="utf-8", errors="ignore")
    return ""


def detect_tags(text: str, rules):
    hits = []
    for label, pat in rules:
        if re.search(pat, text):
            hits.append(label)
    return hits


def guess_region(text: str, parties):
    m = re.search(r'抄送[^。\n]*?(?:证监会|证监局|监管局)?[^。\n]*?([\u4e00-\u9fa5]{2,4})证监局', text)
    if m:
        return m.group(1)
    m = re.search(r'([\u4e00-\u9fa5]{2,4})证监局', text)
    if m:
        return m.group(1)
    for p in parties:
        for c in CITY_WORDS:
            if p.startswith(c):
                return c
    for c in CITY_WORDS:
        if re.search(rf'{c}市?监管局|{c}证监局', text):
            return c
    return ""


def extract_parties_from_text(text):
    """正文「当事人：...」行提取，作为标题解析的补充。"""
    res = []
    for m in re.finditer(r'当事人[：:]([^\n。]{4,200})', text):
        seg = m.group(1)
        seg = re.split(r'[（(]', seg)[0]
        for p in re.split(r'[、,，;；]', seg):
            p = p.strip()
            if 2 <= len(p) <= 40 and re.search(r'[\u4e00-\u9fa5]', p):
                res.append(p)
    return res


def main():
    items = json.loads(LIST.read_text(encoding="utf-8"))
    cases = []
    no_text = 0
    for idx, it in enumerate(items):
        from urllib.parse import unquote
        base = unquote(it["url"].rsplit("/", 1)[-1])
        stem = "".join(c for c in base if c not in ' /\\:*?"<>|')
        stem_noext = Path(stem).stem
        text = pick_text(f"{idx:04d}_{stem_noext}") or pick_text(stem_noext)
        if not text:
            no_text += 1

        doc_type, parties, truncated = parse_title(it["title"])
        orgs = [p for p in parties if is_org(p)]
        persons = [p for p in parties if not is_org(p)]
        if not parties or truncated:
            tp = extract_parties_from_text(text)
            if tp:
                orgs = [p for p in tp if is_org(p)]
                persons = [p for p in tp if not is_org(p)]
                parties = orgs + persons

        manager_type, type_source = classify_manager_type(text, orgs[0] if orgs else "")

        penalties = detect_tags(text, PENALTY_RULES)
        violations = detect_tags(text, VIOLATION_RULES)
        region = guess_region(text, orgs or parties)

        body = re.sub(r'<<<PAGE>>>', '\n', text).strip()
        cases.append({
            "id": idx + 1,
            "title": it["title"].strip(),
            "date": it["date"],
            "year": int(it["date"][:4]),
            "doc_type": doc_type,
            "doc_format": it["doc_type"],
            "parties": parties,
            "organizations": orgs,
            "individuals": persons,
            "org_primary": orgs[0] if orgs else (
                next((p for p in parties if len(p) >= 5), "")),
            "manager_type": manager_type,
            "manager_type_source": type_source,
            "region": region,
            "penalties": penalties,
            "violation_tags": violations,
            "title_truncated": truncated,
            "source_url": it["url"],
            "local_file": f"data/raw/docs/{idx:04d}_{stem}",
            "text_length": len(body),
            "text": body,
        })

    cases.sort(key=lambda c: (c["date"], c["id"]), reverse=True)
    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    # 轻量版（不含正文），供网页加载
    slim = [{k: v for k, v in c.items() if k != "text"} for c in cases]
    (ROOT / "data" / "amac_penalty_cases_slim.json").write_text(
        json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"总案例 {len(cases)}; 缺正文 {no_text}")
    import collections
    print("文书类型:", dict(collections.Counter(c['doc_type'] for c in cases)))
    print("管理人类型:", dict(collections.Counter(c['manager_type'] for c in cases)))
    print("处分措施TOP:", collections.Counter(
        p for c in cases for p in c['penalties']).most_common(10))
    print("违规标签TOP:", collections.Counter(
        p for c in cases for p in c['violation_tags']).most_common(12))
    print("地区TOP:", collections.Counter(
        c['region'] for c in cases if c['region']).most_common(12))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
