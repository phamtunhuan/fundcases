#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCR 质量体检：以领域词表为锚点，找出 PDF（扫描件 OCR）中只差一个字的写法。

输出两类结果：
  1) 可疑误字：窗口中仅一字符与标准词不同，且该写法在网页版（文字准确）语料中从不出现
  2) 断行/排版异常：行首标点、中文间多余空格、标题与正文粘连等
只做统计，不改数据；修正规则由人工确认后写入 build_json.py。
"""
import json
import re
import collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cases = json.loads((ROOT / "data" / "amac_penalty_cases.json").read_text(encoding="utf-8"))
PDF = [c["text"] for c in cases if c["doc_format"] == "pdf"]
HTML = [c["text"] for c in cases if c["doc_format"] == "html"]

# 领域标准词表（用于锚定上下文；长度≥3，避免短词噪声）
LEX = """
私募基金 私募投资基金 私募基金管理人 基金管理人 基金业协会 中国证券投资基金业协会
暂行办法 试行办法 管理办法 实施细则 自律规则 纪律处分 处分决定 处分措施
公开谴责 暂停受理 暂停办理 撤销登记 注销登记 取消会员资格 责令改正 书面警示 警告
事先告知书 决定书 复核决定书 送达公告 注销公告 备案 登记备案 基金备案 产品备案
募集 募集资金 募集行为 募集机构 募集宣传 推介 宣传推介 投资运作 投资决策 投资管理
管理职责 谨慎勤勉 勤勉尽责 诚实信用 受托责任 信义义务 合规 合规风控 内部控制 内控
风险揭示 风险评级 风险评估 投资者 投资者适当性 适当性管理 合格投资者 风险承受能力
信息披露 定期报告 季度报告 年度报告 重大事项 关联交易 利益冲突 利益输送
托管 托管人 托管协议 基金财产 基金资产 基金份额 份额净值 净值 估值 清算 清盘
申购 赎回 认购 申购赎回 开放日 封闭期 存续期 展期 延期
通道业务 资金池 期限错配 刚性兑付 保本保收益 承诺收益 兜底 差额补足
内幕信息 内幕交易 操纵市场 老鼠仓 利益输送 非法集资 场外配资
挪用基金财产 侵占基金财产 挪用 侵占 欺诈 误导 虚假宣传 夸大宣传
账户 银行账户 证券账户 资金账户 划款 转账 归集
证据 相关证据 事实清楚 证据充分 足以认定 予以确认 予以认定
违反 违规 违约 违规行为 违法行为 涉嫌 存在 构成
规定 基金法 证券投资基金法 监管办法 私募基金监管办法 条例 暂行规定
法定代表人 高级管理人员 从业人员 基金从业资格 从业资格 登记编号
营业执照 公司章程 合伙协议 有限合伙 股份有限公司 有限责任公司
证监局 监管局 中国证监会 证券监管 行政监管措施 监管措施 现场检查 自律检查
整改 限期整改 责令 要求 落实 报送 报告 备案信息 更新 填报
"""

WORDS = sorted({w for w in re.split(r"\s+", LEX) if len(w) >= 3}, key=len, reverse=True)

# 建立「去掉第 i 个字」的索引，用于一字之差检索
INDEX = collections.defaultdict(list)
for w in WORDS:
    for i in range(len(w)):
        INDEX[(len(w), i, w[:i] + w[i + 1:])].append(w)


def scan():
    hits = collections.Counter()
    for text in PDF:
        for w in WORDS:
            n = len(w)
            for m in re.finditer(r"[\u4e00-\u9fa5]{%d}" % n, text):
                seg = m.group(0)
                if seg == w:
                    continue
                for i in range(n):
                    key = (n, i, seg[:i] + seg[i + 1:])
                    if w in INDEX.get(key, ()):
                        hits[(seg, w)] += 1
                        break
    return hits


def html_has(word):
    return sum(t.count(word) for t in HTML)


def layout_issues():
    lead = re.compile(r"^[，。、；：）】”’]", re.M)
    dbl = re.compile(r"(?<=[\u4e00-\u9fa5]) {2,}(?=[\u4e00-\u9fa5])")
    # 标题与正文粘连：一、xxx + 紧接「当事人/经查/根据」
    glued = re.compile(r"^[一二三四五六七八九十]{1,3}、[^\n。，]{2,12}(当事人|经查|根据|上述|协会|申请人)", re.M)
    c = collections.Counter()
    for t in PDF:
        c["行首标点"] += len(lead.findall(t))
        c["中文间多空格"] += len(dbl.findall(t))
        c["标题粘连正文"] += len(glued.findall(t))
    return c


def main():
    hits = scan()
    real = [(seg, w, n) for (seg, w), n in hits.items() if html_has(seg) == 0 and n >= 1]
    real.sort(key=lambda x: -x[2])
    print(f"候选误写 {len(real)} 组（网页版语料中从未出现）\n")
    for seg, w, n in real[:80]:
        print(f"  {seg} → {w}   ×{n}")
    print("\n排版问题：", dict(layout_issues()))


if __name__ == "__main__":
    main()
