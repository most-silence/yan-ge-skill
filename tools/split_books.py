# -*- coding: utf-8 -*-
"""书籍分章：把长文本按章节标题切成 JSON，供蒸馏用。

用法:
  python split_books.py --book xiaoao    # 笑傲牛熊
  python split_books.py --book mofa      # 股票魔法师
  python split_books.py --book caibao    # 手把手教你读财报
  python split_books.py --book caolian   # 股市操练大全4
  python split_books.py --all
"""
import re, os, json, argparse

BASE = r"E:\AIProjetct\Nothing\眼哥\books\00-原始"
OUT = r"E:\AIProjetct\Nothing\眼哥\books\01-分章"

BOOKS = {
    "xiaoao": {
        "file": "《笑傲牛熊》史丹•温斯坦.txt",
        "title": "笑傲牛熊（Secrets for Profiting in Bull and Bear Markets）",
        "author": "史丹·温斯坦 Stan Weinstein",
    },
    "mofa": {
        "file": "股票魔法师.txt",
        "title": "股票魔法师（Trade Like a Stock Market Wizard）· 共读笔记",
        "author": "马克·米勒维尼 Mark Minervini（A股训练营 共读整理）",
        "note": "⚠️ 非原书全文，是 54 页共读节选笔记，每章只保留部分",
    },
    "caibao": {
        "file": "手把手教你读财报－唐朝.txt",
        "title": "手把手教你读财报",
        "author": "唐朝",
    },
    "caolian": {
        "file": "【股市操练大全4(第四册)】.txt",
        "title": "股市操练大全（第四册）· 股市操作特别提醒专辑",
        "author": "黎航 主编",
    },
}


def clean_pagemarks(text):
    """去掉 OCR 页标记，保留内容。"""
    return re.sub(r"<!--\s*page\s*\d+\s*-->", "\n", text)


def split_xiaoao(text):
    """笑傲牛熊：章节标记被拆成四行 —— 「第」「1」「章」「标题」。

    目录区（前 ~280 行）也有同样结构，但正文第一章从「一切从这里开始」开始。
    策略：找到所有「第/数字/章」三元组，取正文起点 = 最后一个出现在目录后的那组。
    实际做法：取标题行落在已知 10 个正文标题里的那组。
    """
    BODY_TITLES = {
        "一切从这里开始", "读千份盈利预测不如看一眼股票", "理想的买入时机",
        "优化买入过程", "寻找非凡大牛股", "何时卖出", "卖空：获利捷径",
        "运用最佳长期指标判断牛市和熊", "胜算、结局与获利", "总结",
    }
    lines = [l.strip() for l in text.split("\n")]

    # 目录与正文都是「第/数字/章/标题」四行结构，各出现一次 1..10。
    # 正文起点 = 章号「1」第二次出现的位置。
    all_starts = []
    for i in range(len(lines) - 3):
        if lines[i] == "第" and lines[i + 2] == "章":
            for j in (i + 3, i + 4, i + 5):
                if j < len(lines) and lines[j] in BODY_TITLES:
                    all_starts.append((i, lines[i + 1], lines[j]))
                    break
    all_starts.sort()

    ones = [k for k, s in enumerate(all_starts) if s[1] == "1"]
    body_start_idx = ones[1] if len(ones) >= 2 else 0
    body = all_starts[body_start_idx:]

    chapters = []
    for k, (idx, num, title) in enumerate(body):
        end = body[k + 1][0] if k + 1 < len(body) else len(lines)
        chapters.append({
            "title": f"第{num}章 {title}",
            "body": "\n".join(lines[idx + 4:end]),
        })

    # 过滤空壳：目录残留的章标题后面没正文
    chapters = [c for c in chapters if len(c["body"].strip()) > 500]
    return chapters


def split_caibao(text):
    """手把手教你读财报：OCR 后每页页眉都重复「第N章 XXX」，必须去重。

    难点：页眉在每页顶部重复出现，所以同一章号会出现几十次。
    但正文里该章真正开始的位置 = 该章号**出现序列中间隔最大**的那个位置，
    因为页眉间隔是「一页」，而跨章的那次间隔是「一整章」。
    """
    lines = [l.strip() for l in text.split("\n")]
    pat = re.compile(r"^第([一二三四五六七八九十]+)章\s*([^\s].{0,30})$")

    occ = {}   # num -> [(idx, title)]
    for i, s in enumerate(lines):
        m = pat.match(s)
        if not m:
            continue
        num, title = m.group(1), m.group(2).strip()
        if len(s) > 40 or ".." in s or "/" in s:
            continue
        occ.setdefault(num, []).append((i, title))

    NUM_ORDER = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

    starts = []
    for num in NUM_ORDER:
        if num not in occ:
            continue
        positions = [i for i, _ in occ[num]]
        # 取最大间隔处的「后一个」位置作为该章正文起点
        if len(positions) == 1:
            start = positions[0]
        else:
            gaps = [(positions[k + 1] - positions[k], positions[k + 1])
                    for k in range(len(positions) - 1)]
            start = max(gaps)[1]
        best_title = max((t for _, t in occ[num]), key=len)
        starts.append((start, num, best_title))

    starts.sort()
    chapters = []
    for k, (idx, num, title) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        chapters.append({
            "title": f"第{num}章 {title}",
            "body": "\n".join(lines[idx + 1:end]),
        })
    return chapters


def split_mofa(text):
    """股票魔法师（共读笔记）：章标题形如「第 2 章 你需要事先知道的」，
    章号两侧可能有空格。注意正文里还有「第 2 章的一部分。」这类批注，
    必须排除（不能以「部分」结尾、必须带标题）。"""
    lines = [l.strip() for l in text.split("\n")]
    pat = re.compile(r"^第\s*(\d+)\s*章\s*(\S.*)$")
    starts = []
    for i, s in enumerate(lines):
        m = pat.match(s)
        if not m:
            continue
        title = m.group(2).strip()
        if "部分" in title or len(s) > 40:
            continue
        starts.append((i, m.group(1), title))

    chapters = []
    for k, (idx, num, title) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        chapters.append({
            "title": f"第{num}章 {title}",
            "body": "\n".join(lines[idx + 1:end]),
        })
    return chapters


CN_NUM = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
}


def cn2int(s):
    """中文数字转整数，支持 1–999（一百二十一 → 121）。"""
    s = s.strip()
    if not s:
        return None
    total = 0
    section = 0
    for ch in s:
        if ch == "百":
            total += (section or 1) * 100
            section = 0
        elif ch == "十":
            total += (section or 1) * 10
            section = 0
        elif ch in CN_NUM:
            section = CN_NUM[ch]
        else:
            return None
    return total + section


def split_caolian(text):
    """股市操练大全4：全书 10 章，共 121 条「股市操作特别提醒」。

    OCR 后目录与正文混排，条目名格式混乱（有点线、有缺字）。
    但正文里每条都有**唯一且格式稳定的锚点**：

        “股市操作特别提醒之N”的解析与操作建议：...

    实测该锚点出现 121 次，与全书 121 条完全一致 → 用它切分。
    每条正文起点 = 上一条的「要点」行（含安全系数评定），
    终点 = 本条锚点行。
    """
    lines = [l.strip() for l in text.split("\n")]
    anchor = re.compile(r"[“\"']?股市操作特别提醒之([一二三四五六七八九十百零]+)[”\"']?的解析与操作建议")
    ch_pat = re.compile(r"^第([一二三四五六七八九十]+)章(.+)$")

    # 章标题（正文里的，行号 > 260 避开目录）
    chapters = []
    for i, s in enumerate(lines):
        m = ch_pat.match(s)
        if m and len(s) < 45 and i > 260 and "特别提醒" not in s:
            chapters.append((i, f"第{m.group(1)}章{m.group(2).strip()}"))

    # 找所有锚点（目录里也会出现同名锚点，后面去重）
    anchors = []
    for i, s in enumerate(lines):
        m = anchor.search(s)
        if m:
            num = cn2int(m.group(1))
            if num:
                anchors.append((i, num))

    raw = []
    for k, (ai, num) in enumerate(anchors):
        start = anchors[k - 1][0] + 1 if k > 0 else max(0, ai - 120)
        body = "\n".join(lines[start:ai])
        if len(body.strip()) < 120:
            continue
        raw.append({"num": num, "body": body, "anchor_line": ai})

    # 同一编号可能出现两次（目录锚点 + 正文锚点）：
    # 正文那次的 body 更长（含「要点」+「安全系数评定」+ 解析），保留最长的。
    best = {}
    for it in raw:
        if it["num"] not in best or len(it["body"]) > len(best[it["num"]]["body"]):
            best[it["num"]] = it

    items = []
    for num, it in best.items():
        chap = "未归章"
        for ci, cname in chapters:
            if ci < it["anchor_line"]:
                chap = cname
        items.append({"num": num, "chapter": chap, "body": it["body"]})

    items.sort(key=lambda x: x["num"])
    return [{"title": f"特别提醒之{it['num']:03d}｜{it['chapter']}", "body": it["body"]}
            for it in items]


def process(key):
    cfg = BOOKS[key]
    path = os.path.join(BASE, cfg["file"])
    if not os.path.exists(path):
        print(f"!! 缺失 {cfg['file']}")
        return None
    raw = open(path, encoding="utf-8", errors="ignore").read()
    text = clean_pagemarks(raw)

    if key == "xiaoao":
        chs = split_xiaoao(text)
    elif key == "mofa":
        chs = split_mofa(text)
    elif key == "caibao":
        chs = split_caibao(text)
    elif key == "caolian":
        chs = split_caolian(text)
    else:
        chs = split_by_pattern(text, r"^第[一二三四五六七八九十]+[章节]\s*\S*")

    # 过滤空壳
    chs = [c for c in chs if len(c["body"].strip()) > 100]

    os.makedirs(OUT, exist_ok=True)
    outp = os.path.join(OUT, f"{key}.json")
    data = {
        "key": key,
        "title": cfg["title"],
        "author": cfg["author"],
        "source": cfg["file"],
        "total_chars": len(text),
        "chapter_count": len(chs),
        "chapters": chs,
    }
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print(f"{key:10s} {len(chs):3d} 章 | {len(text):7,} 字 -> {outp}")
    for i, c in enumerate(chs[:12], 1):
        print(f"    {i:2d}. [{len(c['body']):6,}字] {c['title'][:40]}")
    if len(chs) > 12:
        print(f"    ... 还有 {len(chs)-12} 章")
    return data


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", choices=list(BOOKS) + ["all"], default="all")
    a = ap.parse_args()
    keys = list(BOOKS) if a.book == "all" else [a.book]
    for k in keys:
        process(k)
        print()
