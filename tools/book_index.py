# -*- coding: utf-8 -*-
"""书籍关键概念索引：为蒸馏提供「概念 → 章节 → 原话」定位。

用法: python book_index.py --book xiaoao
"""
import json, os, re, argparse, collections

CH_DIR = r"E:\AIProjetct\Nothing\眼哥\books\01-分章"

CONCEPTS = {
    "xiaoao": {
        "四阶段": ["第一阶段", "第二阶段", "第三阶段", "第四阶段", "底部阶段", "上涨阶段", "顶部阶段", "下跌阶段"],
        "均线": ["均线", "移动平均", "周线", "30周"],
        "止损": ["止损", "保护性止损", "卖出止损"],
        "突破": ["突破", "向上突破", "放量突破"],
        "成交量": ["成交量", "量能", "放量", "缩量"],
        "相对强度": ["相对强度", "RS", "表现优于"],
        "买点": ["买入点", "买入时机", "买点", "理想买入"],
        "卖出": ["卖出", "何时卖出", "止盈", "获利了结"],
        "大盘": ["大盘", "市场趋势", "牛熊", "牛市", "熊市"],
        "行业": ["行业", "板块", "集团"],
        "仓位": ["仓位", "头寸", "持股"],
        "风险": ["风险", "回撤", "亏损"],
    },
    "mofa": {
        "SEPA": ["SEPA", "入场点"],
        "趋势": ["趋势", "阶段"],
        "基本面": ["基本面", "净利润", "收益", "成长"],
        "止损": ["止损"],
        "风险": ["风险", "回撤"],
        "仓位": ["仓位", "头寸"],
        "催化剂": ["催化剂"],
        "领头羊": ["领头羊", "龙头"],
        "图表": ["图表", "形态", "基底"],
        "卖出": ["卖出", "止盈"],
    },
    "caibao": {
        "资产负债表": ["资产负债表", "货币资金", "应收账款", "存货"],
        "利润表": ["利润表", "营业收入", "毛利率", "净利润"],
        "现金流量表": ["现金流量表", "经营活动", "自由现金流"],
        "造假": ["造假", "操纵", "舞弊", "反欺诈"],
        "估值": ["估值", "市盈率", "市净率", "安全边际"],
        "排除": ["排除", "证伪", "淘汰"],
    },
}


def main(key):
    path = os.path.join(CH_DIR, f"{key}.json")
    data = json.load(open(path, encoding="utf-8"))
    concepts = CONCEPTS.get(key, {})

    print(f"《{data['title']}》 {data['author']}")
    print(f"  {data['total_chars']:,} 字 | {data['chapter_count']} 章\n")

    for cname, kws in concepts.items():
        hits = collections.Counter()
        examples = []
        for ci, ch in enumerate(data["chapters"], 1):
            body = ch["body"]
            for kw in kws:
                n = body.count(kw)
                if n:
                    hits[f"第{ci}章 {ch['title'][:18]}"] += n
        total = sum(hits.values())
        print(f"【{cname}】共 {total} 次")
        for loc, n in hits.most_common(5):
            print(f"    {n:4d}  {loc}")
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True, choices=list(CONCEPTS))
    main(ap.parse_args().book)
