#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""整合列表元数据 + OCR/HTML 正文，生成结构化案例 JSON。

流程：原始 OCR 文本 -> reflow（段落合并，消除断行）-> 错字归一化 -> 字段抽取
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / "data" / "cases_raw_list.json"
DOCS = ROOT / "data" / "raw" / "docs"
OCR = ROOT / "data" / "ocr"
OUT = ROOT / "data" / "amac_penalty_cases.json"

# ============================================================
# 一、排版重排：把 OCR 的逐视觉行合并为连贯段落
# ============================================================
PARA_START = re.compile(
    r'^(?:'
    r'[一二三四五六七八九十]{1,3}[、．.]'          # 一、 二、
    r'|[（(][一二三四五六七八九十]{1,3}[)）]'        # （一）
    r'|\d{1,2}[、．.](?!\d)'                        # 1、 1.
    r'|[（(]\d{1,2}[)）]'                           # （1）
    r'|当事人[：:]|被(?:处分|处罚)?(?:机构|当事人)[：:]'
    r'|抄送|主送|附件|特此(?:通知|公告)'
    r'|中国证券投资基金业协会|中国证券监督管理委员会'
    r'|根据|经查|以上|综上|据此|现(?:将|予)|有关(?:事项|情况)'
    r')')

CJK = re.compile(r'[\u4e00-\u9fa5]')
ASCII_END = re.compile(r'[A-Za-z0-9,;:%]$')


def is_new_para(raw_line: str, cur: str) -> bool:
    indent = len(raw_line) - len(raw_line.lstrip())
    ln = raw_line.strip()
    if indent >= 2 and CJK.match(ln):
        return True
    if PARA_START.match(ln):
        return True
    return False


def reflow(text: str) -> str:
    """合并 OCR 断行，输出连贯段落（段落之间空一行）。"""
    paras, cur = [], ""
    for page in text.split("<<<PAGE>>>"):
        for raw in page.split("\n"):
            ln = raw.strip()
            if not ln:
                if cur:
                    paras.append(cur)
                    cur = ""
                continue
            if not cur:
                cur = ln
                continue
            if is_new_para(raw, cur):
                paras.append(cur)
                cur = ln
            else:
                # 中英混排时在 ASCII 之间补空格，避免单词粘连
                if ASCII_END.search(cur) and re.match(r'^[A-Za-z0-9]', ln):
                    cur += " " + ln
                elif re.search(r'[，、；,;]$', cur) is None and CJK.match(ln) \
                        and re.search(r'[\u4e00-\u9fa5]$', cur):
                    cur += ln
                else:
                    cur += ln
        if cur:
            paras.append(cur)
            cur = ""
    out = "\n\n".join(p.strip() for p in paras if p.strip())
    out = re.sub(r'(?<=[\u4e00-\u9fa5]) +(?=[\u4e00-\u9fa5])', '', out)
    return out


# ============================================================
# 二、OCR 错字归一化（仅用于关键词匹配，不改变存储的原文）
# ============================================================
CONFUSION = [
    (r'[撤撇撖撒徹澈辙摋][销消銷]', '撤销'),
    (r'[注註][销消銷]', '注销'),
    (r'[暂暫皙斩哲][停儜亭仃]', '暂停'),
    (r'[谴遣道][责贵费]', '谴责'),
    (r'警吿|敬告', '警告'),
    (r'资洛|咨格|资恪', '资格'),
    (r'俻案|备桉|备秦', '备案'),
    (r'责今', '责令'),
    (r'丛业', '从业'),
    (r'私慕|私菜|私算|私获|私蒜', '私募'),
    (r'[蒸燕菜蛬荃]金', '基金'),
    (r'管埋|菅理', '管理'),
    (r'凳记', '登记'),
    (r'扱送|报达|报遂', '报送'),
    (r'菜集|募菜', '募集'),
    (r'职费', '职责'),
    (r'选规|违現', '违规'),
    (r'披漏|披路|掲露', '披露'),
    (r'勤免', '勤勉'),
    (r'适营', '适当'),
]

try:
    from opencc import OpenCC
    _CC = OpenCC('t2s')          # 繁体 -> 简体
except Exception:
    _CC = None


def normalize(text: str) -> str:
    """仅用于关键词匹配的归一化：繁简统一 + OCR 错字纠正。"""
    if _CC:
        text = _CC.convert(text)
    for pat, rep in CONFUSION:
        text = re.sub(pat, rep, text)
    return text


# ============================================================
# 三、当事人 / 机构
# ============================================================
OPEN_BR = "（(〔［【["
CLOSE_BR = "）)〕］】]"

ORG_WORDS = ("公司", "合伙", "基金", "中心", "事务所", "银行", "证券", "资产", "投资",
             "管理", "集团", "研究院", "协会", "信托", "保险", "有限合伙", "企业")


def extract_paren(s: str) -> str:
    """按括号配对提取最外层括号内容，兼容 （）〔〕【】[] 及其嵌套/截断。"""
    start, depth = None, 0
    for i, ch in enumerate(s):
        if ch in OPEN_BR:
            if start is None:
                start = i
            depth += 1
        elif ch in CLOSE_BR:
            if start is not None:
                depth -= 1
                if depth == 0:
                    return s[start + 1:i]
    return s[start + 1:] if start is not None else ""


def is_org(name: str) -> bool:
    n = name.strip()
    return len(n) >= 5 and any(w in n for w in ORG_WORDS)


def split_parties(raw: str):
    raw = re.sub(r'[,，;；]', '、', raw)
    return [p.strip() for p in raw.split("、") if len(p.strip()) >= 2]


def parse_title(title: str):
    t = title.strip()
    doc_type = "其他"
    for kw, label in [
        ("纪律处分复核决定书", "纪律处分复核决定书"),
        ("纪律处分事先告知书送达公告", "纪律处分事先告知书送达公告"),
        ("纪律处分事先告知书", "纪律处分事先告知书"),
        ("纪律处分决定书送达公告", "纪律处分决定书送达公告"),
        ("纪律处分决定书", "纪律处分决定书"),
        ("纪律处分决定", "纪律处分决定"),
    ]:
        if kw in t:
            doc_type = label
            break
    if "注销" in t and "公告" in t:
        doc_type = "注销登记公告"
    truncated = t.endswith("...") or "…" in t
    parties = split_parties(extract_paren(t)) if extract_paren(t) else []
    return doc_type, parties, truncated


PARTY_BLOCK = re.compile(
    r'(?:当事人|被(?:处分|处罚)(?:机构|人)|被(?:申请)?复核(?:申请)?人)[：:]\s*(.{2,240})')


def parties_from_text(text: str):
    """从正文「当事人：」块提取，优先取段落内、截止到句号或括号说明之前。"""
    out = []
    for m in PARTY_BLOCK.finditer(text):
        seg = m.group(1)
        # 截断到第一个句号/换行/「根据」
        seg = re.split(r'[。\n]|根据《|协会(?:于|向)', seg)[0]
        # 去掉「（以下简称XXX）」及其后的内容
        seg = re.sub(r'[（(].*?[)）]', '', seg)
        seg = re.sub(r'\[.*?\]', '', seg)
        for p in split_parties(seg):
            p = re.sub(r'(?:等\d+人|等)$', '', p).strip()
            if p and re.search(r'[\u4e00-\u9fa5]', p) and len(p) <= 45:
                out.append(p)
    # 去重保序
    seen, res = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            res.append(p)
    return res


# ============================================================
# 四、地区
# ============================================================
PROVINCES = [
    "北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
    "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "台湾",
    "内蒙古", "广西", "西藏", "宁夏", "新疆", "香港", "澳门",
]
CITIES = [
    "深圳", "广州", "珠海", "东莞", "佛山", "汕头", "中山", "惠州", "湛江", "江门",
    "杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "台州", "衢州", "丽水", "舟山",
    "南京", "苏州", "无锡", "常州", "南通", "徐州", "扬州", "盐城", "泰州", "镇江", "连云港",
    "济南", "青岛", "烟台", "潍坊", "临沂", "淄博", "济宁", "威海", "东营", "泰安",
    "福州", "厦门", "泉州", "漳州", "莆田", "宁德", "龙岩",
    "成都", "绵阳", "德阳", "宜宾", "泸州", "南充", "乐山",
    "武汉", "宜昌", "襄阳", "荆州", "黄石", "长沙", "株洲", "湘潭", "岳阳", "衡阳",
    "合肥", "芜湖", "蚌埠", "安庆", "马鞍山", "南昌", "赣州", "九江", "上饶",
    "郑州", "洛阳", "开封", "南阳", "新乡", "许昌",
    "石家庄", "唐山", "保定", "廊坊", "邯郸", "沧州", "秦皇岛",
    "西安", "咸阳", "宝鸡", "渭南", "沈阳", "大连", "鞍山", "营口", "锦州",
    "长春", "吉林", "哈尔滨", "大庆", "昆明", "曲靖", "贵阳", "遵义",
    "南宁", "桂林", "柳州", "北海", "海口", "三亚", "兰州", "西宁", "银川",
    "乌鲁木齐", "拉萨", "呼和浩特", "包头", "鄂尔多斯", "太原", "大同", "临汾",
]
# 证监局名称 -> 标准地区
BUREAU_MAP = {
    "深圳": "深圳", "上海": "上海", "北京": "北京", "广东": "广东", "江苏": "江苏",
    "浙江": "浙江", "山东": "山东", "福建": "福建", "厦门": "厦门", "四川": "四川",
    "湖北": "湖北", "湖南": "湖南", "安徽": "安徽", "河南": "河南", "河北": "河北",
    "陕西": "陕西", "辽宁": "辽宁", "大连": "大连", "吉林": "吉林", "黑龙江": "黑龙江",
    "江西": "江西", "云南": "云南", "贵州": "贵州", "广西": "广西", "海南": "海南",
    "甘肃": "甘肃", "新疆": "新疆", "内蒙古": "内蒙古", "宁夏": "宁夏", "青海": "青海",
    "西藏": "西藏", "山西": "山西", "天津": "天津", "重庆": "重庆", "宁波": "宁波",
    "青岛": "青岛", "深圳证监局": "深圳",
}
ALL_PLACES = sorted(PROVINCES + CITIES, key=len, reverse=True)


# 协会公示返回的省级全称 -> 案例库使用的简称
PROVINCE_SHORT = {
    "北京市": "北京", "天津市": "天津", "上海市": "上海", "重庆市": "重庆",
    "河北省": "河北", "山西省": "山西", "辽宁省": "辽宁", "吉林省": "吉林",
    "黑龙江省": "黑龙江", "江苏省": "江苏", "浙江省": "浙江", "安徽省": "安徽",
    "福建省": "福建", "江西省": "江西", "山东省": "山东", "河南省": "河南",
    "湖北省": "湖北", "湖南省": "湖南", "广东省": "广东", "海南省": "海南",
    "四川省": "四川", "贵州省": "贵州", "云南省": "云南", "陕西省": "陕西",
    "甘肃省": "甘肃", "青海省": "青海", "台湾省": "台湾",
    "内蒙古自治区": "内蒙古", "广西壮族自治区": "广西", "西藏自治区": "西藏",
    "宁夏回族自治区": "宁夏", "新疆维吾尔自治区": "新疆",
    "香港特别行政区": "香港", "澳门特别行政区": "澳门",
}

def place_from_address(addr: str) -> str:
    """从登记地址提取地区：优先城市（含直辖市），其次省份。"""
    if not addr:
        return ""
    for p in sorted(CITIES, key=len, reverse=True):
        if p in addr:
            return p
    for p in PROVINCES:
        if p in addr:
            return p
    return ""


def guess_region(text: str, parties, org: str) -> str:
    """优先级：监管局抄送 > 正文监管局 > 机构名所在地 > 正文省市"""
    m = re.search(r'抄送[：:]?[^。\n]{0,80}?'
                  r'([\u4e00-\u9fa5]{2,4})(?:证监局|监管局)', text)
    if not m:
        m = re.search(r'([\u4e00-\u9fa5]{2,4})(?:证监局|监管局)', text)
    if m:
        key = m.group(1)
        # 去掉前缀动词/机构名干扰，如「上海证监局」被截成「稽查局上海证监局」
        for k, v in BUREAU_MAP.items():
            if key.endswith(k) or k in key:
                return v
    for name in ([org] if org else []) + list(parties):
        for p in ALL_PLACES:
            if name.startswith(p):
                return p
        # 名称中嵌在括号里的城市，如「中财鼎盛（北京）投资基金管理有限公司」
        pm = re.search(r'[（(]([\u4e00-\u9fa5]{2,4})[)）]', name)
        if pm:
            for p in ALL_PLACES:
                if pm.group(1) == p:
                    return p
    for p in ALL_PLACES:
        if re.search(rf'{p}(?:市|省)?(?:证监局|监管局)', text):
            return p
    return ""


# ============================================================
# 五、处分措施
# ============================================================
# NAME 用于跳过「撤销XX管理人登记」中夹着的机构简称
_NAME = r"[\u4e00-\u9fa5]{0,25}?"
PENALTY_RULES = [
    ("撤销管理人登记", rf"撤销{_NAME}(?:私募基金)?(?:管理人)?登记|取消{_NAME}(?:私募基金)?管理人登记"),
    ("注销管理人登记", rf"注销{_NAME}(?:私募基金)?管理人登记"),
    ("取消会员资格", rf"取消{_NAME}会员资格"),
    ("暂停受理备案", rf"暂停(?:受理|办理)?{_NAME}(?:私募基金)?(?:产品)?备案"),
    ("公开谴责", r"公开?谴责|予以谴责|进行谴责"),
    ("警告", r"警告"),
    ("通报批评", r"通报批评|予以批评"),
    ("责令改正", rf"责令{_NAME}改正"),
    ("要求限期整改", r"限期(?:整改|改正)|要求(?:其|该)?(?:限期)?整改"),
    ("暂停基金从业资格", rf"暂停{_NAME}基金从业资格"),
    ("取消基金从业资格", rf"取消{_NAME}基金从业资格|认定为不适当人选"),
    ("书面警示", r"书面警示|出具警示函"),
    ("约谈高管", r"约见谈话|约谈(?:其)?(?:高级管理|负责|法定代表)"),
    ("要求强制培训", r"强制(?:参加)?培训|要求(?:其)?参加(?:合规)?培训"),
    ("暂停或限制业务", rf"暂停{_NAME}(?:募集|投资|管理)业务|限制(?:其)?业务活动"),
]
# 互斥：命中注销即不再标注撤销
EXCLUSIVE = [("注销管理人登记", "撤销管理人登记")]

# 互斥：命中注销即不再标注撤销
EXCLUSIVE = [("注销管理人登记", "撤销管理人登记")]


# 精准定位：「协会决定作出以下纪律处分：XXX。」中的 XXX
DECISION_SENT = re.compile(
    r'(?:协会|本会|我会|中国证券投资基金业协会)'
    r'(?:拟|决定)?(?:作出)?(?:以下|如下)?(?:纪律)?处分[：:]\s*'
    r'([^。；]{2,200})')


def penalty_sentences(text: str):
    """提取处分决定的原文短句，作为措施标注的唯一依据。"""
    out = []
    for m in DECISION_SENT.finditer(text):
        seg = re.sub(r'\s+', '', m.group(1).strip())
        if len(seg) >= 3:
            out.append(seg)
    return out

# 处分决定章节定位（避免在法规引用��落误命中）
DECISION_HEAD = re.compile(
    r'(?:[一二三四五六七八九十]{1,3}、)?'
    r'(?:纪律)?处分(?:决定|决定如下|意见)[^\n]{0,10}[：:\n]|'
    r'(?:本会|协会)决定(?:作出)?(?:如下)?(?:纪律)?处分|'
    r'决定(?:作出|给予)以下(?:纪律)?处分|'
    r'作出(?:如下|以下)(?:纪律)?处分')
DECISION_TAIL = re.compile(
    r'如(?:对|不服)本?[决处]|复核(?:申请)?期间|抄送|当事人(?:如)?对本|'
    r'本纪律处分决定自|二〇|20\d{2}年\d{1,2}月\d{1,2}日\s*$')


def decision_section(text: str) -> str:
    """抽取「处分决定」章节；定位失败时退回全文。"""
    paras = text.split("\n\n")
    start = None
    for i, p in enumerate(paras):
        if DECISION_HEAD.search(p):
            start = i
    if start is None:
        return text
    buf = []
    for p in paras[start:]:
        if buf and DECISION_TAIL.search(p):
            break
        buf.append(p)
        if len(buf) >= 4:
            break
    return "\n\n".join(buf) if buf else text


def detect_penalties(text: str):
    sents = penalty_sentences(text)
    scope = "。".join(sents) if sents else decision_section(text)
    hits = []
    for label, pat in PENALTY_RULES:
        if re.search(pat, scope):
            hits.append(label)
    for keep, drop in EXCLUSIVE:
        if keep in hits and drop in hits:
            hits.remove(drop)
    return hits


# ============================================================
# 六、违规事由标签
# ============================================================
VIOLATION_RULES = [
    ("信息报送违规", r"未(?:按[照规定]*|及时|如实|真实|准确|完整)?(?:报送|填报|报告|更新)(?:其)?(?:相关)?(?:信息|材料|数据)|信息(?:报送|填报)(?:不(?:及时|真实|准确|完整))|未履行信息报送义务|报送的?信息(?:存在)?(?:虚假|不实|不准确)"),
    ("未按规定备案", r"未(?:按[照规定]*|及时)?(?:办理|申请)?备[案桉]|未(?:及时)?(?:报告|报送)(?:重大事项)?变更|重大事项(?:未)?(?:报告|变更)"),
    ("投资者适当性", r"投资者适当性|风险(?:识别|承受)(?:能力)?(?:评估|测评|问卷)|适当性(?:管理|义务|程序)|未(?:对)?投资者(?:进行)?风险(?:评估|测评)"),
    ("募集行为违规", r"募集行为|公开(?:宣传|推介|募集)|向不特定(?:对象|社会公众)|承诺(?:保本|保收益|本金|最低收益|不受损失)|拆分(?:份额|转让)|委托不具有基金销售"),
    ("未勤勉尽责", r"未(?:履行|尽)(?:勤勉|恪尽职守|诚实信用|谨慎勤勉|忠实)|勤勉(?:尽责|义务)|谨慎勤勉义务|未(?:审慎)?(?:履行)?管理人职责"),
    ("内控与合规缺失", r"内部(?:控制|管理制度?)|内控(?:制度)?(?:不|缺失|未|存在)?|风险管理(?:制度)?(?:不|缺失|未)?|合规(?:管理|风控)?(?:制度)?(?:不健全|缺失|未|兼任)|风控制度|未建立(?:关联交易|内控|合规)"),
    ("人员与场所不达标", r"无(?:固定)?(?:营业|经营|办公)场所|(?:从业|专职|员工)(?:人员)?(?:不足|少于|缺失|不符合)|专职员工|高管(?:缺|未|不(?:在|符合))|法定代表人(?:失联|无法联系)|办公场所不符合"),
    ("失联或异常经营", r"失联|异常经营|无法(?:取得)?联系|经营(?:异常|场所空置)|列入(?:失联|异常)"),
    ("挪用侵占基金财产", r"挪[用](?:基金|募集)?(?:资金|财产|财产)|侵占(?:基金)?财产|占用(?:基金)?财产|资金池|挤占挪用"),
    ("利益输送与关联交易", r"利益输送|关联交易|利益冲突|自我交易|关联方(?:交易|资金往来)|为(?:自己或)?他人牟[取]?利"),
    ("投资运作违规", r"投资(?:范围|运作|决策|比例)(?:违反|不符合|超出)|违反(?:基金)?合同(?:约定)?(?:进行)?投资|高买低卖|超(?:出|过)约定(?:投资)?(?:范围|比例)"),
    ("杠杆与结构化违规", r"杠杆(?:倍数|比例)|结构化(?:分级|安排|产品)|份额分级|分级(?:基金|资管计划)"),
    ("信息披露违规", r"信息(?:披露|告知)(?:违规|不(?:及时|真实|完整|充分))|未(?:向)?(?:投资者)?(?:披[露漏路]|告知)(?:重大)?(?:信息|事项)|隐瞒(?:重大)?(?:信息|事项)|虚假(?:披[露]|记载)"),
    ("材料保管不规范", r"未(?:按[照规定]*)?妥善保管|材料(?:缺失|未提供|未保存|不予提供)|未(?:向)?协会(?:提供|提交)"),
    ("兼营无关业务", r"兼营|从事与私募基金(?:管理)?(?:业务)?(?:无关|冲突)的业务|民间借贷|类金融|融资租赁|房地产开发"),
    ("登记信息不实", r"登记(?:信息)?(?:不实|虚假|与事实不符)|提供虚假(?:材料|信息)|隐瞒(?:有关)?情况|虚假记载"),
    ("高管与从业人员违规", r"高级管理人[员](?:违规|不符合|未)?|挂靠|兼职(?:于|其他)?|不具备(?:从业)?资格|未取得基金从业资格|合规风控(?:负责人)?(?:缺|未|兼任)"),
    ("基金运作未清算", r"未(?:按[照约定]*|及时|依法|组织)?(?:进行)?清算|未清盘|到期未(?:清算|退出|兑付)|拒不清算"),
    ("不公平对待投资者", r"不公平(?:对待|处理)(?:投资者)?|区别对待投资者"),
    ("量化交易违规", r"量化(?:交易|策略|产品)|程序化交易|高频交易"),
]

TYPE_RULES = [
    ("私募证券投资基金管理人", r"私募证券投资基金管理人|证券类(?:私募)?(?:基金)?管理人|私募证券(?:投资)?基金管理人|私募证券投资基金(?:业务)?管理人"),
    ("私募股权、创业投资基金管理人", r"私募股权(?:投资)?基金管理人|创业投资基金管理人|私募股权、创业投资(?:基金)?管理人|股权类(?:私募)?管理人|私募股权创业投资基金管理人"),
    ("其他私募投资基金管理人", r"其他私募投资基金管理人|其他类(?:私募)?管理人"),
    ("私募资产配置类管理人", r"私募资产配置(?:基金)?管理人"),
]
NAME_TYPE_RULES = [
    ("私募证券投资基金管理人", r"证券投资|证券类|量化|对冲|私募证券"),
    ("私募股权、创业投资基金管理人", r"股权投资|创业投资|产业投资|并购投资|创投|股权基金"),
]
SEC_SIGNALS = [r"私募证券投资基金", r"证券投资基金", r"证券账户", r"二级市场",
               r"量化", r"期货", r"股票", r"债券", r"可转债", r"沪深",
               r"打新", r"份额净值", r"基金净值", r"证券期货", r"结构化", r"净值披"]
EQ_SIGNALS = [r"私募股权投资基金", r"创业投资基金", r"未上市企业", r"被投企业",
              r"股权投资", r"股权投资项目", r"实缴出资", r"���商信息", r"投资协议"]


def classify_manager_type(text: str, org_name: str):
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


REGISTRY_PATH = ROOT / "data" / "manager_types.json"
REGISTRY = {}
if REGISTRY_PATH.exists():
    try:
        REGISTRY = json.load(open(REGISTRY_PATH, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        REGISTRY = {}


def registry_lookup(org_name: str):
    """协会公示系统查询结果：机构名 -> 权威登记信息。"""
    if not org_name:
        return None
    r = REGISTRY.get(org_name)
    if r:
        return r
    # 归一化后再试一次（括号/空格差异）
    key = org_name.replace("（", "(").replace("）", ")").replace(" ", "")
    for k, v in REGISTRY.items():
        if k.replace("（", "(").replace("）", ")").replace(" ", "") == key:
            return v
    return None


def classify_with_registry(text: str, org_name: str):
    """优先采用协会公示的登记类型，未命中再回退到正文启发式。"""
    r = registry_lookup(org_name)
    if r and r.get("manager_type"):
        status = r.get("status", "")
        src = f"协会公示（{status}）" if status else "协会公示"
        return r["manager_type"], src, r
    label, src = classify_manager_type(text, org_name)
    return label, src, r


def local_path(url: str, idx: int):
    from urllib.parse import unquote
    base = unquote(url.rsplit("/", 1)[-1])
    base = "".join(c for c in base if c not in ' /\\:*?"<>|')
    return f"data/raw/docs/{idx:04d}_{base}"


def load_text(idx: int, url: str) -> str:
    from urllib.parse import unquote
    base = unquote(url.rsplit("/", 1)[-1])
    stem = "".join(c for c in base if c not in ' /\\:*?"<>|')
    stem_noext = Path(stem).stem
    for cand in (f"{idx:04d}_{stem_noext}", stem_noext):
        p = OCR / (cand + ".txt")
        if p.exists():
            return p.read_text(encoding="utf-8", errors="ignore")
    return ""


def main():
    items = json.loads(LIST.read_text(encoding="utf-8"))
    cases = []
    no_text = 0
    for idx, it in enumerate(items):
        raw = load_text(idx, it["url"])
        if not raw:
            no_text += 1
        text = reflow(raw)
        norm = normalize(text)

        doc_type, parties, truncated = parse_title(it["title"])
        tp = parties_from_text(norm)
        orgs = [p for p in parties if is_org(p)]
        persons = [p for p in parties if not is_org(p)]
        if not parties or truncated or not orgs:
            if tp:
                o2 = [p for p in tp if is_org(p)]
                p2 = [p for p in tp if not is_org(p)]
                if o2:
                    orgs, persons = o2, (p2 or persons)
                    parties = orgs + persons
                elif not parties:
                    parties = tp
        org = orgs[0] if orgs else (
            max(parties, key=len) if parties else "")

        manager_type, type_source, reg = classify_with_registry(norm, org)
        penalties = detect_penalties(norm)
        violations = [l for l, pat in VIOLATION_RULES if re.search(pat, norm)]
        region = guess_region(norm, parties, org)
        if not region and reg:
            for k in ("register_province", "office_province",
                      "register_address", "office_address"):
                v = (reg.get(k) or "").strip()
                if not v:
                    continue
                if len(v) <= 6:                      # 省级全称/简称
                    region = PROVINCE_SHORT.get(v, v)
                else:                                # 完整地址，提取省市
                    region = place_from_address(v)
                if region:
                    break

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
            "org_primary": org,
            "manager_type": manager_type,
            "manager_type_source": type_source,
            "registry_status": (reg or {}).get("status", ""),
            "registry_match_score": (reg or {}).get("match_score"),
            "register_no": (reg or {}).get("register_no", ""),
            "legal_rep": (reg or {}).get("legal_rep", ""),
            "member_type": (reg or {}).get("member_type", ""),
            "fund_count": (reg or {}).get("fund_count"),
            "registry_url": (reg or {}).get("detail_url", ""),
            "region": region,
            "penalties": penalties,
            "penalty_text": "；".join(penalty_sentences(norm))[:600],
            "decision_text": decision_section(norm)[:1200],
            "violation_tags": violations,
            "title_truncated": truncated,
            "source_url": it["url"],
            "local_file": local_path(it["url"], idx),
            "text_length": len(text),
            "text": text,
        })

    cases.sort(key=lambda c: (c["date"], c["id"]), reverse=True)
    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    slim = [{k: v for k, v in c.items() if k != "text"} for c in cases]
    (ROOT / "data" / "amac_penalty_cases_slim.json").write_text(
        json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")

    import collections
    print(f"总案例 {len(cases)}; 缺正文 {no_text}")
    print("文书类型:", dict(collections.Counter(c['doc_type'] for c in cases)))
    print("管理人类型:", dict(collections.Counter(c['manager_type'] for c in cases)))
    print("空机构名:", sum(1 for c in cases if not c['org_primary']),
          "| 空地区:", sum(1 for c in cases if not c['region']),
          "| 无处分措施:", sum(1 for c in cases if not c['penalties']))
    print("处分措施:", collections.Counter(
        p for c in cases for p in c['penalties']).most_common(12))
    print("违规标签TOP:", collections.Counter(
        p for c in cases for p in c['violation_tags']).most_common(8))
    print("地区TOP:", collections.Counter(
        c['region'] for c in cases if c['region']).most_common(12))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
