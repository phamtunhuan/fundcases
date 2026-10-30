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
    # —— 第三轮：处分决定句高频 OCR 变体 ——
    (r'街[儜停]|香[停亭]|粉[停亭]|哲[傅傅]|督[停亭]|准[督]', '暂停'),
    (r'备[紫秦]', '备案'),
    (r'[谁港造遗][责贵费]', '谴责'),
    (r'[撇撖撒澈辙摋][销消]', '撤销'),
    (r'黑名[単单]', '黑名单'),
    (r'撇销|擞销|撒销|撖销|澈销|辙销|摋销|徹销|撤消', '撤销'),
    (r'洪定', '决定'),
    (r'黑名單|黑名単', '黑名单'),
    (r'加入黑名[単单]', '加入黑名单'),
    (r'職責', '职责'),
    # —— 第四轮：违规事由段高频 OCR 变体 ——
    (r'拔露|撥露', '披露'),
    (r'未各察', '未备案'),
    (r'本舍', '本金'),
    (r'职[费費]', '职责'),
    (r'宙议', '审议'),
    (r'审镇|審镇', '审慎'),
    (r'蓮慎|莲慎', '审慎'),
    (r'厦行', '履行'),
    (r'造当', '适当'),
    (r'備察|备察|应备紫', '备案'),
    (r'证絭|证绾', '证监'),
    (r'私慕投咨蒸金|蒸金', '基金'),
    (r'共舍', '合伙'),
    (r'秘蜜', '秘密'),
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

# 复核决定书的申请人（不参与 org 提取，仅作地区线索）
APPLICANT_BLOCK = re.compile(r'申请人[：:]\s*(.{2,120})')


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
# ============================================================
# 地区归一：一律按证监局设立地归类
# 36 个证监局：4 直辖市 + 22 省 + 5 自治区 + 5 计划单列市
# ============================================================
BUREAU_REGIONS = [
    # 直辖市
    "北京", "天津", "上海", "重庆",
    # 省
    "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽",
    "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "海南",
    "四川", "贵州", "云南", "陕西", "甘肃", "青海",
    # 自治区
    "内蒙古", "广西", "西藏", "宁夏", "新疆",
    # 计划单列市（独立设证监局，不并入所在省）
    "大连", "宁波", "厦门", "青岛", "深圳",
]
BUREAU_SET = set(BUREAU_REGIONS)

# 地级市 -> 所属证监局
CITY_TO_REGION = {
    # 广东（深圳、珠海除外单列/珠海归广东）
    "广州": "广东", "珠海": "广东", "东莞": "广东", "佛山": "广东", "汕头": "广东",
    "中山": "广东", "惠州": "广东", "湛江": "广东", "江门": "广东", "肇庆": "广东",
    "茂名": "广东", "梅州": "广东", "汕尾": "广东", "河源": "广东", "阳江": "广东",
    "清远": "广东", "潮州": "广东", "揭阳": "广东", "云浮": "广东", "韶关": "广东",
    # 浙江（宁波单列）
    "杭州": "浙江", "温州": "浙江", "嘉兴": "浙江", "湖州": "浙江", "绍兴": "浙江",
    "金华": "浙江", "台州": "浙江", "衢州": "浙江", "丽水": "浙江", "舟山": "浙江",
    # 江苏
    "南京": "江苏", "苏州": "江苏", "无锡": "江苏", "常州": "江苏", "南通": "江苏",
    "徐州": "江苏", "扬州": "江苏", "盐城": "江苏", "泰州": "江苏", "镇江": "江苏",
    "连云港": "江苏", "淮安": "江苏", "宿迁": "江苏",
    # 山东（青岛单列）
    "济南": "山东", "烟台": "山东", "潍坊": "山东", "临沂": "山东", "淄博": "山东",
    "济宁": "山东", "威海": "山东", "东营": "山东", "泰安": "山东", "日照": "山东",
    "德州": "山东", "聊城": "山东", "滨州": "山东", "菏泽": "山东", "枣庄": "山东",
    # 福建（厦门单列）
    "福州": "福建", "泉州": "福建", "漳州": "福建", "莆田": "福建", "宁德": "福建",
    "龙岩": "福建", "三明": "福建", "南平": "福建",
    # 四川
    "成都": "四川", "绵阳": "四川", "德阳": "四川", "宜宾": "四川", "泸州": "四川",
    "南充": "四川", "乐山": "四川", "自贡": "四川", "攀枝花": "四川", "内江": "四川",
    # 湖北
    "武汉": "湖北", "宜昌": "湖北", "襄阳": "湖北", "荆州": "湖北", "黄石": "湖北",
    "十堰": "湖北", "孝感": "湖北", "荆门": "湖北", "黄冈": "湖北", "咸宁": "湖北",
    # 湖南
    "长沙": "湖南", "株洲": "湖南", "湘潭": "湖南", "岳阳": "湖南", "衡阳": "湖南",
    "常德": "湖南", "郴州": "湖南", "邵阳": "湖南", "益阳": "湖南",
    # 安徽
    "合肥": "安徽", "芜湖": "安徽", "蚌埠": "安徽", "安庆": "安徽", "马鞍山": "安徽",
    "阜阳": "安徽", "滁州": "安徽", "六安": "安徽",
    # 江西
    "南昌": "江西", "赣州": "江西", "九江": "江西", "上饶": "江西", "宜春": "江西",
    "吉安": "江西", "抚州": "江西",
    # 河南
    "郑州": "河南", "洛阳": "河南", "开封": "河南", "南阳": "河南", "新乡": "河南",
    "许昌": "河南", "安阳": "河南", "商丘": "河南", "信阳": "河南",
    # 河北
    "石家庄": "河北", "唐山": "河北", "保定": "河北", "廊坊": "河北", "邯郸": "河北",
    "沧州": "河北", "秦皇岛": "河北", "邢台": "河北", "张家口": "河北", "承德": "河北",
    # 陕西
    "西安": "陕西", "咸阳": "陕西", "宝鸡": "陕西", "渭南": "陕西", "延安": "陕西",
    "榆林": "陕西", "汉中": "陕西",
    # 辽宁（大连单列）
    "沈阳": "辽宁", "鞍山": "辽宁", "营口": "辽宁", "锦州": "辽宁", "抚顺": "辽宁",
    "本溪": "辽宁", "丹东": "辽宁", "盘锦": "辽宁", "葫芦岛": "辽宁",
    # 吉林 / 黑龙江
    "长春": "吉林", "吉林市": "吉林", "四平": "吉林", "延边": "吉林",
    "哈尔滨": "黑龙江", "大庆": "黑龙江", "齐齐哈尔": "黑龙江", "牡丹江": "黑龙江",
    # 云南 / 贵州
    "昆明": "云南", "曲靖": "云南", "玉溪": "云南", "大理": "云南",
    "贵阳": "贵州", "遵义": "贵州", "六盘水": "贵州",
    # 广西 / 海南
    "南宁": "广西", "桂林": "广西", "柳州": "广西", "北海": "广西", "梧州": "广西",
    "海口": "海南", "三亚": "海南",
    # 西北 / 边疆
    "兰州": "甘肃", "西宁": "青海", "银川": "宁夏", "乌鲁木齐": "新疆",
    "拉萨": "西藏", "呼和浩特": "内蒙古", "包头": "内蒙古", "鄂尔多斯": "内蒙古",
    "太原": "山西", "大同": "山西", "临汾": "山西", "运城": "山西",
    # 计划单列市自身
    "深圳": "深圳", "厦门": "厦门", "宁波": "��波", "青岛": "青岛", "大连": "大连",
}


def to_bureau_region(place: str) -> str:
    """把任意城市/省份名归一为证监局设立地；无法识别返回空串。"""
    if not place:
        return ""
    p = place.strip()
    # 去掉「市/省/自治区」等后缀
    for suf in ("特别行政区", "自治区", "省", "市"):
        if p.endswith(suf) and len(p) > len(suf):
            p = p[:-len(suf)]
            break
    p = PROVINCE_SHORT.get(place.strip(), p)
    if p in BUREAU_SET:
        return p
    return CITY_TO_REGION.get(p, "")


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
    # 复核决定书用「申请人」而不是「当事人」
    if not org:
        am = APPLICANT_BLOCK.search(text[:1500])
        if am:
            aname = re.split(r'[、。]|申请人不服', am.group(1))[0].strip()
            if aname and len(aname) >= 5:
                return to_bureau_region(aname)
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
    # 复核决定书的机构全称在「申请人：」后，且常以简称作为 org，
    # 这里退一步在正文首段找带括号地名的机构全称
    head = text[:1500]
    m2 = re.search(r'(?:申请人|当事人)[：:]\s*[^\n。]{0,40}?'
                   r'[（(]([\u4e00-\u9fa5]{2,4})[)）]', head)
    if not m2:
        m2 = re.search(r'([\u4e00-\u9fa5]{2,20}(?:公司|企业|中心|合伙))'
                       r'[（(]([\u4e00-\u9fa5]{2,4})[)）]', head)
    if m2:
        cand = m2.group(2) if m2.lastindex and m2.lastindex >= 2 else m2.group(1)
        got = to_bureau_region(cand)
        if got:
            return got
    for p in ALL_PLACES:
        if re.search(rf'{p}(?:市|省)?(?:证监局|监管局)', text):
            return p
    return ""


# ============================================================
# 五、处分措施
# ============================================================
# NAME 用于跳过「撤销XX管理人登记」中夹着的机构简称
_NAME = r"[\u4e00-\u9fa5、，,和及与]{0,30}?"
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
    r'(?:协会|本会|我会|基金业协会|中国证券投资基金业协会)'
    r'(?:拟|决定)?(?:作出)?(?:以下|如下)?(?:纪律)?处分[：:]\s*'
    r'([^。；]{2,200})'
    r'|(?:协会|本会|我会|基金业协会)决定[：:]?\s*'
    r'(?:自\d{4}年?\d{1,2}?月?\d{1,2}?日?(?:起)?[，,]?\s*)?'
    r'(?=(?:一、|二、|（一）|撤销|暂停|取消|警告|谴责|责令|通报|限期|加入黑名单|要求))'
    r'([^。；]{2,200})')

def penalty_sentences(text: str):
    """提取处分决定的原文短句，作为措施标注的唯一依据。"""
    out = []
    for m in DECISION_SENT.finditer(text):
        seg = re.sub(r'\s+', '', (m.group(1) or m.group(2) or "").strip())
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


def _numbered_after(text: str, m) -> str:
    """决策句后若为编号列表（一、…；二、…），继续收集直到「（本页无正文）/抄送/复核」。"""
    rest = text[m.end():]
    stop = re.search(
        r'根据《(?:实施办法|纪律处分办法|会员管理办法)|如对(?:以上|本)?(?:以上)?纪律处分决定有异议'
        r'|本纪律处分决定继续执行|复核期|抄送|（本页无正文）', rest)
    if stop:
        return rest[:stop.start()]
    return rest[:300]


def detect_penalties(text: str):
    sents = penalty_sentences(text)
    if sents:
        m = DECISION_SENT.search(text)
        extra = _numbered_after(text, m) if m else ""
        scope = "。".join(sents) + "。" + re.sub(r"\s+", "", extra)
    else:
        scope = decision_section(text)
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
    ("信息报送违规", r"未.{0,8}(?:报送|填报|报告|更新).{0,10}(?:信息|材料|数据)|信息(?:报送|填报)(?:不(?:及时|真实|准确|完整))|报送.{0,6}信息.{0,6}不(?:真实|准确|完整|及时)|未履行信息报送义务|报送的?信息(?:存在)?(?:虚假|不实|不准确)"),
    ("未按规定备案", r"未(?:按[照规定]*|及时)?(?:办理|申请)?备[案桉]|未办理.{0,12}备案|未及时申请.{0,15}备案|未(?:及时)?申请.{0,10}备案|管理未备案产品|重大事项.{0,6}未(?:及时)?(?:报告|报送)"),
    ("投资者适当性", r"投资者适当性|风险(?:识别|承受)(?:能力)?(?:评估|测评|问卷)|适当性(?:管理|义务|程序)|未(?:对)?投资者(?:进行)?风险(?:评估|测评)"),
    ("募集行为违规", r"募集行为|公开(?:宣传|推介|募集)|向不特定(?:对象|社会公众)|承诺(?:保本|保收益|本金|最低收益|不受损失)|拆分(?:份额|转让)|委托不具有基金销售"),
    ("未勤勉尽责", r"未.{0,8}(?:恪尽|尽职守|勤勉)|未尽.{0,10}(?:勤勉|尽职|审慎)|玩忽职守|未玩忽职守|未(?:履行|尽)(?:勤勉|恪尽职守|诚实信用|谨慎勤勉|忠实)|勤勉(?:尽责|义务)|谨慎勤勉义务|未(?:审慎)?(?:履行)?管理人职责|未尽.{0,6}管理职[责]"),
    ("内控与合规缺失", r"内部(?:控制|管理制度?)|内控(?:制度)?(?:不|缺失|未|存在)?|风险管理(?:制度)?(?:不|缺失|未)?|合规(?:管理|风控)?(?:制度)?(?:不健全|缺失|未|兼任)|风控制度|未建立(?:关联交易|内控|合规)"),
    ("人员与场所不达标", r"无(?:固定|独立)?(?:营业|经营|办公)(?:场所|场地)|(?:从业|专职|员工)(?:人员)?(?:不足|少于|缺失|不符合)|人员配置不符合|专职员工|高管(?:缺|未|不(?:在|符合))|法定代表人(?:失联|无法联系)|办公场所(?:不符合|不独立)"),
    ("失联或异常经营", r"失联|异常经营|无法(?:取得)?联系|经营(?:异常|场所空置)|列入(?:失联|异常)"),
    ("挪用侵占基金财产", r"挪[用](?:基金|募集)?(?:资金|财产)|挪用.{0,15}(?:资金|财产|款项|资产|万元)|侵占(?:基金)?财产|占用(?:基金)?财产|资金池|挤占挪用"),
    ("利益输送与关联交易", r"利益输送|关联交易|利益冲突|自我交易|关联方(?:交易|资金往来)|为(?:自己或)?他人牟[取]?利"),
    ("投资运作违规", r"投资(?:范围|运作|决策|比例)(?:违反|不符合|超出)|违反.{0,10}合同.{0,10}(?:进行)?投资|高买低卖|超(?:出|过)约定(?:投资)?(?:范围|比例)"),
    ("杠杆与结构化违规", r"杠杆(?:倍数|比例)|结构化(?:分级|安排|产品)|份额分级|分级(?:基金|资管计划|集合|资产)|定增分级|杠杆运作(?:情况)?未.{0,6}披露"),
    ("信息披露违规", r"信息(?:披露|告知)(?:违规|不(?:及时|真实|完整|充分))|未(?:向)?(?:投资者)?(?:披[露漏路]|告知)(?:重大)?(?:信息|事项)|未.{0,14}(?:披[露漏路]|���知).{0,16}(?:信息|事项|情况|义务)|未如实披露|信息披露.{0,4}存在.{0,4}(?:缺陷|违规|不及时)|未按(?:合同)?约定.{0,12}(?:进行)?披露|隐瞒(?:重大)?(?:信息|事项)|虚假(?:披[露]|记载)|未[^\n]{0,25}向.{0,30}提供.{0,35}重大.{0,10}(?:信息|事项|情况)"),
    ("材料保管不规范", r"未(?:按[照规定]*)?(?:妥善)?(?:保管|保存)|未妥善(?:保存|保管)|材料(?:缺失|未提供|未保存|不予提供)|档案(?:丢失|缺失)"),
    ("兼营无关业务", r"兼营|从事与私募基金(?:管理)?(?:业务)?(?:无关|冲突)的业务|民间借贷|类金融|融资租赁|房地产开发"),
    ("登记信息不实", r"登记(?:信息)?(?:不实|虚假|与事实不符)|提供.{0,15}与事实不符|提供虚假(?:材料|信息)|隐瞒.{0,10}情况|虚假记载|未(?:对)?(?:拟成立|拟管理).{0,10}(?:如实)?说明"),
    ("高管与从业人员违规", r"高级管理人[员](?:违规|不符合|未)?|挂靠|兼职(?:于|其他)?|不具备(?:从业)?资格|未取得基金从业资格|合规风控(?:负责人)?(?:缺|未|兼任)"),
    ("基金运作未清算", r"未(?:按[照约定]*|及时|依法|组织)?(?:进行)?清算|未清盘|到期未(?:清算|退出|兑付)|拒不清算"),
    ("不公平对待投资者", r"不公平(?:对待|处理)(?:投资者)?|区别对待投资者"),
    ("量化交易违规", r"量化(?:交易|策略|产品)|程序化交易|高频交易"),
    ("向不特定对象或不合格投资者募集", r"向不(?:合���|特定)(?:投资者|对象|社会公众)|非合格投资者|(?:单笔)?投资(?:金额)?小?于?1(?:0)?0?万"),
    ("人员办公场所混同", r"人员、办公场地混同|混同办公|人员.*混同|办公.*混同|工作人员.*不一致|同在一处办公|工作人员.{0,6}完全相同"),
    ("登记备案信息不实", r"虚假(?:填报|报送|登记|提供)(?:基金)?(?:备案|登记)?信息|备案信息不符|登记信息.{0,10}不实|实际(?:发行|募集).{0,15}(?:与)?备案信息"),
    ("不配合监管检查", r"不(?:配合|按要求|及时|履行)(?:协会)?(?:自律)?(?:检查|监管)?(?:工作)?|配合不到位|未能充分配合(?:协会)?(?:自律)?检查|未(?:按要求|及时|按要求提交)(?:提交|提供|报送)|未(?:按|要求)(?:提交|提供|报送)(?:相关)?(?:材料|证据|文件)|拒不提供|致使检查.{0,10}(?:无法|障碍|困难)|阻碍检查|多次.{0,6}(?:未|不).{0,6}(?:提交|提供)|一直未提交|不配合.{0,6}检查|配合.{0,4}检查.{0,4}(?:不|欠)|未配合(?:行政)?(?:监管)?(?:及)?协会"),
    ("委托非员工/非机构行使管理职责", r"将(?:投资)?管理.{0,6}职责.{0,8}(?:交由|委托)|非.{0,6}(?:员工|机构).{0,10}(?:交易决策|下单)|未实际履行.{0,10}管理人职[责费]"),
    ("挪用基金财产", r"挪作他用|改变资金用途|资金(?:应该|应当).{0,15}被(?:用于|转移)|未按(?:协议|约定)使用基金财产"),
    ("未恪尽职守勤勉审慎", r"未(?:恪尽|格尽|格格)职守|蓮[慎慎][勤務]|未(?:恪尽)?尽职守|未(恪尽)?尽职守|未尽.{0,8}(?:勤勉|尽职|审慎)"),
    # —— 第四轮：27 条漏判案例专项规则 ——
    ("操纵证券市场", r"操纵(?:证券)?(?:市场|股价|收盘价|行情)|尾盘(?:拉升|拉抬|大量买入)|对倒交易|集中资金优势.{0,10}(?:连续|连续买卖)|日内回转交易"),
    ("场外配资与通道业务", r"场外配资|为(?:买卖)?(?:股票|期货)提供融资|删除.{0,8}(?:子)?账户.{0,12}交易记录|通道业务"),
    ("承诺保本保收益", r"承诺(?:保本|保收益|本金|最低收益|不受损失)|保证.{0,15}(?:本金|本息).{0,10}不受损失|收益补足|保底(?:收益|回报)"),
    ("尽职调查违规", r"尽职调查.{0,12}未(?:履行|尽责|尽职)|未(?:进行|开展|充分)?尽职调查|未履职尽责"),
    ("越权或违规担保", r"擅[自白].{0,15}担保|未经.{0,12}(?:批准|授权|同意).{0,10}(?:担保|承诺)"),
    ("从业人员管理违规", r"未.{0,10}签署.{0,8}(?:劳动|劳务)合同|注册.{0,15}从业资格.{0,30}未(?:实际|安排)|未安排其实际履行"),
    ("备案前投资运作", r"备案(?:成立|生效)?前.{0,14}(?:开展|进行)?投资运作|名单.{0,12}与实际缴款.{0,10}不符"),
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


# ============================================================
# 管理人类型：统一收敛为 5 个固定取值
# ============================================================
MANAGER_TYPES = [
    "私募证券投资基金管理人",
    "私募股权、创业投资基金管理人",
    "其他私募投资基金管理人",
    "私募资产配置类管理人",
    "未填报管理人类型",
]
# 协会旧口径 / 启发式 / 非私募标注 -> 标准五类
_TYPE_NORMALIZE = {
    "私募股权投资基金管理人": "私募股权、创业投资基金管理人",
    "创业投资基金管理人": "私募股权、创业投资基金管理人",
    "未明确": "未填报管理人类型",
    "证据不足": "未填报管理人类型",
}


def normalize_manager_type(raw: str) -> str:
    """把任意类型值收敛到 5 个固定取值。非私募对象（公募/券商/销售机构）
    不在私募名录内，归入「未填报管理人类型」。"""
    t = (raw or "").strip()
    if t in MANAGER_TYPES:
        return t
    t = _TYPE_NORMALIZE.get(t, t)
    if t in MANAGER_TYPES:
        return t
    # 「非私募管理人（...）」等带括号的标注
    if t.startswith("非私募") or t.startswith("未填报"):
        return "未填报管理人类型"
    return "未填报管理人类型"


def classify_with_registry(text: str, org_name: str):
    """优先采用协会公示的登记类型，未命中再回退到正文启发式。

    返回 (manager_type, source, reg, reg_status_raw)。
    reg_status_raw 保留协会原始状态（在册/已注销/未查到/不适用/空）。
    """
    r = registry_lookup(org_name)
    raw_status = (r or {}).get("status", "") if r else ""
    if r and r.get("manager_type"):
        src = f"协会公示（{raw_status}）" if raw_status else "协会公示"
        return normalize_manager_type(r["manager_type"]), src, r, raw_status
    label, src = classify_manager_type(text, org_name)
    return normalize_manager_type(label), src, r, raw_status


def local_path(url: str, idx: int):
    from urllib.parse import unquote
    base = unquote(url.rsplit("/", 1)[-1])
    base = "".join(c for c in base if c not in ' /\\:*?"<>|')
    return f"data/raw/docs/{idx:04d}_{base}"


SHELL_PATCH = {}
_sp = ROOT / "data" / "shell_patch.json"
if _sp.exists():
    try:
        SHELL_PATCH = json.loads(_sp.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        SHELL_PATCH = {}


def load_text(idx: int, url: str) -> str:
    """正文加载：壳页附件 PDF 正文优先（shell_patch.json），其次 OCR 缓存。"""
    from urllib.parse import unquote
    fn = SHELL_PATCH.get(str(idx))
    if fn:
        p = OCR / (fn + ".txt")
        if p.exists():
            return p.read_text(encoding="utf-8", errors="ignore")
    base = unquote(url.rsplit("/", 1)[-1])
    stem = "".join(c for c in base if c not in ' /\\:*?"<>|')
    stem_noext = Path(stem).stem
    for cand in (f"{idx:04d}_{stem_noext}", stem_noext):
        p = OCR / (cand + ".txt")
        if p.exists():
            return p.read_text(encoding="utf-8", errors="ignore")
    return ""


TITLE_ORG_RE = re.compile(r"关于注销(.+?)私募基金管理人登记的公告")
TITLE_ORG_RE2 = re.compile(r"关于注销(.+?)基金管理人登记的公告")
TITLE_REVIEW_RE = re.compile(r"复核决定书[-—－_\s]*(.+)$")
TEXT_APPLICANT_RE = re.compile(
    r"申请人[：:]\s*([\u4e00-\u9fa5A-Za-z（）()·]{4,40}?"
    r"(?:股份有限公司|有限责任公司|有限公司|合伙企业（有限合伙）|合伙企业\(有限合伙\)|中心))")
BATCH_WORDS = re.compile(r"期间届满|未提交|专项法律意见书|失联|异常经营|第[一二三四五六七八九十]+批")


def _fix_org_ocr(name: str) -> str:
    """机构名常见 OCR 混淆修正。"""
    for bad, good in (("投咨管理", "投资管理"), ("咨格", "资格"),
                      ("管埋", "管理"), ("资产菅理", "资产管理")):
        name = name.replace(bad, good)
    return name


def org_from_title(title: str) -> str:
    """从「关于注销X私募基金管理人登记的公告」等标题中取机构名。"""
    t = (title or "").strip()
    for pat in (TITLE_ORG_RE, TITLE_ORG_RE2):
        m = pat.search(t)
        if m:
            name = m.group(1).strip()
            if len(name) >= 6 and not BATCH_WORDS.search(name):
                return _fix_org_ocr(name)
    m = TITLE_REVIEW_RE.search(t)
    if m:
        name = m.group(1).strip()
        if 4 <= len(name) <= 30 and not BATCH_WORDS.search(name):
            return _fix_org_ocr(name)
    return ""


def org_from_text(text: str) -> str:
    """从正文首段「申请人：XXX」取机构全称。"""
    m = TEXT_APPLICANT_RE.search(text or "")
    return _fix_org_ocr(m.group(1)) if m else ""


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
        # 兜底：注销登记公告 / 复核决定书的机构名常只出现在标题或首句
        batch_notice = False
        if not org:
            if "复核" in doc_type:
                org = org_from_text(norm) or org_from_title(it["title"])
            else:
                org = org_from_title(it["title"])
            if not org and doc_type == "注销登记公告":
                batch_notice = True           # 批量注销公告，无单一机构
            if org:
                orgs = [org]
                parties = [org] + [p for p in parties if p != org]

        manager_type, type_source, reg, reg_status_raw = classify_with_registry(norm, org)
        if batch_notice:                     # 批量公告：多家机构合并，不归属单一管理人
            manager_type, type_source, reg, reg_status_raw = (
                "未填报管理人类型", "批量公告（无单一机构）", None, "已注销")
        # 登记状态只保留两类：在册 / 已注销
        #   在册   ← 协会在册名录命中，或实体存在但非私募（不适用）
        #   已注销 ← 已注销名录命中；协会两处均查不到，说明管理人已变更名称
        name_changed = reg_status_raw == "未查到"
        registry_status = "在册" if reg_status_raw in ("在册", "不适用") else "已注销"
        penalties = detect_penalties(norm)
        scope = norm + "\n" + re.sub(r'违規|违現', '违规', norm)
        scope_flat = re.sub(r'\s+', '', scope)   # 去掉换行，让跨段表述可匹配
        violations = [l for l, pat in VIOLATION_RULES
                      if re.search(pat, scope) or re.search(pat, scope_flat)]
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
        # 统一归一为证监局设立地（杭州→浙江、珠海→广东…）
        region = to_bureau_region(region) or region

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
            "batch_notice": batch_notice,
            "manager_type": manager_type,
            "manager_type_source": type_source,
            "registry_status": registry_status,
            "name_changed": name_changed,
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
