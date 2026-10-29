#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二轮 OCR 修复：对「违現」「遣责」等 OCR 错字击穿的正则做补匹配。
同时识别「行政处罚已实施→免予纪律处分」的特殊情况。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SRC = DATA / "amac_penalty_cases.json"

sys.path.insert(0, str(ROOT / "scripts"))
from build_json import (normalize, load_text, reflow, decision_section,
                        EXCLUSIVE, PENALTY_RULES, VIOLATION_RULES,
                        penalty_sentences)

# 追加 OCR 变体映射（针对当前规则未覆盖的错字）
EXTRA_PENALTY_PATTERNS = [
    # 公开谴责的各种 OCR 变体
    ("公开谴责", r"公开[谁港造遗谴]责|进行[谁港造遗]责|予以[谁港造遗]责|公开?责[任罚贵]|给予公开?谴[贵责]"),
    # 暂停受理备案的各种 OCR 变体
    ("暂停受理备案", r"[街香粉哲督暫][停儜亭仃][受理備案备桉]?[^。；\n]{0,30}备[紫秦]?"),
    # 撤销登记的各种 OCR 变体
    ("撤销管理人登记", r"[撤撇撖撒澈辙摋]*?销[^。\n]{2,10}管理[^。\n]{0,8}登"),
    # 注销登记（已有规则，额外覆盖）
    ("注销管理人登记", r"注[销消]*?销[^。\n]{0,10}管理人"),
    # 取消会员资格
    ("取消会员资格", r"取消[^。\n]{0,20}[会贝貝][员員格]?"),
]

EXTRA_VIOLATION_PATTERNS = [
    # 违规的 OCR 变体（违現、違規）
    ("内控与合规缺失", r"[内内]部[控制][制度]?|内[控控制]"),
    ("未按约定使用基金财产", r"未按[约定协议]使用|挪[用作]用|改变资金用途"),
    ("挪用侵占基金财产", r"挪[用作]用|侵占|挤占挪用"),
    # 信息披露
    ("信息披露违规", r"未[向]?[投投资者]*?披露|未如实[披露路]|隐瞒.*?信息"),
    # 适当性
    ("投资者适当性", r"[风风险][识别承受评估]|适当性[管理]"),
    # 宣传推介
    ("募集行为违规", r"[公开]宣传[推介]|向不特定|承诺保本保收益|拆分份额转让"),
]


def detect_penalties_v2(text: str):
    """在原文 + 错字归一化文本上双重匹配。"""
    norm = normalize(text)
    # 额外错字归一化
    extra = norm
    for pat, rep in EXTRA_PENALTY_PATTERNS[:2]:  # 先归一化高频
        extra = re.sub(pat, rep, extra)
    scope = decision_section(norm) + "\n" + decision_section(extra)
    hits = []
    for label, pat in PENALTY_RULES:
        if re.search(pat, scope):
            hits.append(label)
    for label, pat in EXTRA_PENALTY_PATTERNS:
        if re.search(pat, scope):
            hits.append(label)
    for high, low in EXCLUSIVE:
        if high in hits and low in hits:
            hits.remove(low)
    return hits


def detect_violations_v2(text: str):
    """违规事由双重匹配。"""
    norm = normalize(text)
    # 补充违現等 OCR 错字归一化
    norm_extra = re.sub(r'违現', '违规', norm)
    norm_extra = re.sub(r'现[金金]管理', '现金管理', norm_extra)
    norm_extra = re.sub(r'[违違]规事', '违规事', norm_extra)
    scope = norm + "\n" + norm_extra
    hits = []
    for label, pat in VIOLATION_RULES:
        if re.search(pat, scope):
            hits.append(label)
    for label, pat in EXTRA_VIOLATION_PATTERNS:
        if re.search(pat, scope):
            hits.append(label)
    return hits


def is_行政替代_纪律(c):
    """判断是否属于行政处罚已实施→协会免予纪律处分。"""
    t = c['text']
    # 关键特征
    if ('行政处罚决定书' in t or '行政处罚' in t) and \
       ('协会不应' in t or '不再' in t or '免予处理' in t):
        return True
    if re.search(r'行政处罚决定书.*?协会.*?不再|协会.*?行政处罚.*?免予', t):
        return True
    return False


def main():
    cases = json.load(open(SRC, encoding="utf-8"))
    print(f"总案例 {len(cases)} 条")

    # 需要修补的案例
    need_fix_pen = [c for c in cases
                    if c['doc_type'] in ('纪律处分决定书', '纪律处分复核决定书')
                    and not c['penalties']
                    and not is_行政替代_纪律(c)]
    need_fix_v = [c for c in cases
                  if c['doc_type'] in ('纪律处分决定书', '纪律处分复核决定书')
                  and not c['violation_tags']
                  and not is_行政替代_纪律(c)]

    print(f"需修补处罚措施: {len(need_fix_pen)} 条")
    print(f"需修补违规事由: {len(need_fix_v)} 条")

    fixed_pen = 0
    fixed_v = 0
    skipped_admin = 0
    skipped_none = 0

    for c in cases:
        if c['doc_type'] not in ('纪律处分决定书', '纪律处分复核决定书'):
            continue

        # 处罚措施修复
        if not c['penalties'] and not is_行政替代_纪律(c):
            # 重新从原文提取决策句
            raw = load_text(c['id'] - 1, c['source_url'])
            norm = normalize(reflow(raw))
            new_p = detect_penalties_v2(norm)
            if new_p and new_p != c['penalties']:
                c['penalties'] = new_p
                # 尝试提取 penalty_text
                sents = penalty_sentences(norm)
                c['penalty_text'] = "；".join(sents)[:600] if sents else ""
                fixed_pen += 1
                print(f"  [处罚] {c['title'][:35]} -> {new_p}")
            elif not new_p:
                skipped_none += 1
        elif is_行政替代_纪律(c):
            skipped_admin += 1

        # 违规事由修复
        if not c['violation_tags'] and not is_行政替代_纪律(c):
            raw = load_text(c['id'] - 1, c['source_url'])
            norm = normalize(reflow(raw))
            new_v = detect_violations_v2(norm)
            if new_v and new_v != c['violation_tags']:
                c['violation_tags'] = new_v
                fixed_v += 1
                print(f"  [违规] {c['title'][:35]} -> {new_v}")
            elif not new_v:
                skipped_none += 1

    # 保存
    SRC.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n修补完成:")
    print(f"  处罚措施: +{fixed_pen} 条")
    print(f"  违规事由: +{fixed_v} 条")
    print(f"  豁免（行政处罚已替代）: {skipped_admin} 条")
    print(f"  无法自动修复: {skipped_none} 条")

    # 最终统计
    from collections import Counter
    none_pen = sum(1 for c in cases if not c['penalties']
                   and c['doc_type'] in ('纪律处分决定书', '纪律处分复核决定书'))
    none_v = sum(1 for c in cases if not c['violation_tags']
                 and c['doc_type'] in ('纪律处分决定书', '纪律处分复核决定书'))
    print(f"\n最终状态:")
    print(f"  决定书无处罚措施: {none_pen} 条")
    print(f"  决定书无违规事由: {none_v} 条")


if __name__ == "__main__":
    main()
