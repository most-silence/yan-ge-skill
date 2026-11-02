#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""临时工具：按 (eid, t1, t2) 从清洗稿取逐字行，供 batch-89 批读引用。
只读，不改任何语料。
"""
import io
import sys
from pathlib import Path

ROOT = Path(r"E:\AIProjetct\Nothing\眼哥")
TXT = ROOT / "sources" / "05-播客转写" / "audio_txt"

FILES = {
    "UDn8oYKT8uFb": TXT / "UDn8oYKT8uFb_股票-爱情-大家._clean.txt",
    "A6jPkRdPfPff": TXT / "A6jPkRdPfPff_眼哥股市会 12月8日._clean.txt",
    "MO4APCspVVDc": TXT / "MO4APCspVVDc_韭阴真经之我在大A当股神._clean.txt",
    "BgtrFsWR1Gwo": TXT / "BgtrFsWR1Gwo_眼哥股市会 12月9日._clean.txt",
}

SPECS = [
    ("Q1",  "UDn8oYKT8uFb", "00:01:38", "00:01:54"),
    ("Q2",  "UDn8oYKT8uFb", "00:02:28", "00:02:51"),
    ("Q3",  "UDn8oYKT8uFb", "00:03:09", "00:03:25"),
    ("Q4",  "UDn8oYKT8uFb", "00:07:11", "00:07:22"),
    ("Q5",  "UDn8oYKT8uFb", "00:07:27", "00:07:41"),
    ("Q6",  "UDn8oYKT8uFb", "00:08:02", "00:08:13"),
    ("Q7",  "UDn8oYKT8uFb", "00:08:59", "00:09:36"),
    ("Q8",  "UDn8oYKT8uFb", "00:09:41", "00:10:06"),
    ("Q9",  "UDn8oYKT8uFb", "00:10:31", "00:10:46"),
    ("Q10", "UDn8oYKT8uFb", "00:13:32", "00:13:48"),
    ("Q11", "UDn8oYKT8uFb", "00:16:52", "00:16:58"),
    ("Q12", "UDn8oYKT8uFb", "00:22:26", "00:22:33"),
    ("Q13", "UDn8oYKT8uFb", "00:26:16", "00:26:47"),
    ("Q14", "UDn8oYKT8uFb", "00:26:57", "00:27:10"),
    ("Q15", "UDn8oYKT8uFb", "00:29:40", "00:29:50"),
    ("Q16", "UDn8oYKT8uFb", "00:34:32", "00:34:53"),
    ("Q17", "UDn8oYKT8uFb", "00:39:48", "00:39:55"),
    ("Q18", "UDn8oYKT8uFb", "00:46:11", "00:46:29"),
    ("Q20", "A6jPkRdPfPff", "00:05:45", "00:05:53"),
    ("Q21", "A6jPkRdPfPff", "00:07:04", "00:07:28"),
    ("Q22", "A6jPkRdPfPff", "00:08:42", "00:09:07"),
    ("Q23", "A6jPkRdPfPff", "00:09:54", "00:10:08"),
    ("Q24", "A6jPkRdPfPff", "00:11:18", "00:11:29"),
    ("Q25", "A6jPkRdPfPff", "00:13:17", "00:13:36"),
    ("Q26", "A6jPkRdPfPff", "00:20:16", "00:20:34"),
    ("Q30", "MO4APCspVVDc", "00:06:14", "00:06:47"),
    ("Q31", "MO4APCspVVDc", "00:08:03", "00:08:12"),
    ("Q32", "MO4APCspVVDc", "00:08:29", "00:08:42"),
    ("Q33", "MO4APCspVVDc", "00:22:26", "00:22:41"),
    ("Q34", "MO4APCspVVDc", "00:32:51", "00:33:15"),
    ("Q35", "MO4APCspVVDc", "00:26:14", "00:26:27"),
    ("Q36", "MO4APCspVVDc", "00:21:12", "00:21:28"),
    ("Q37", "MO4APCspVVDc", "00:31:44", "00:31:56"),
    ("Q50", "BgtrFsWR1Gwo", "00:13:09", "00:13:29"),
    ("Q51", "BgtrFsWR1Gwo", "00:13:56", "00:14:08"),
    ("Q52", "BgtrFsWR1Gwo", "00:24:08", "00:24:24"),
    ("Q53", "BgtrFsWR1Gwo", "00:33:08", "00:33:24"),
    ("Q54", "BgtrFsWR1Gwo", "00:22:50", "00:23:08"),
    ("Q55", "BgtrFsWR1Gwo", "00:43:47", "00:44:01"),
    ("Q56", "BgtrFsWR1Gwo", "00:12:05", "00:12:13"),
    ("Q57", "BgtrFsWR1Gwo", "00:37:48", "00:38:00"),
    ("Q58", "BgtrFsWR1Gwo", "00:34:31", "00:34:48"),
    ("Q59", "BgtrFsWR1Gwo", "00:05:46", "00:05:57"),
    ("Q60", "BgtrFsWR1Gwo", "00:22:38", "00:22:48"),
    ("Q61", "BgtrFsWR1Gwo", "00:16:15", "00:16:24"),
    ("Q62", "BgtrFsWR1Gwo", "00:19:22", "00:19:29"),
    ("X1", "MO4APCspVVDc", "00:05:44", "00:06:07"),
    ("X2", "MO4APCspVVDc", "00:07:05", "00:07:15"),
    ("X3", "A6jPkRdPfPff", "00:07:33", "00:07:50"),
    ("X4", "BgtrFsWR1Gwo", "00:10:36", "00:10:50"),
    ("X5", "BgtrFsWR1Gwo", "00:22:28", "00:22:37"),
    ("X6", "BgtrFsWR1Gwo", "00:24:05", "00:24:09"),
    ("X7", "UDn8oYKT8uFb", "00:04:04", "00:04:20"),
    ("X8", "A6jPkRdPfPff", "00:06:44", "00:06:57"),
    ("Y1", "UDn8oYKT8uFb", "00:04:39", "00:04:55"),
    ("Y2", "UDn8oYKT8uFb", "00:39:22", "00:39:37"),
    ("Y3", "BgtrFsWR1Gwo", "00:07:54", "00:08:14"),
    ("Y4", "BgtrFsWR1Gwo", "00:32:37", "00:32:57"),
    ("Y5", "BgtrFsWR1Gwo", "00:36:04", "00:36:17"),
    ("Y6", "BgtrFsWR1Gwo", "00:46:11", "00:46:17"),
    ("Y7", "BgtrFsWR1Gwo", "00:09:26", "00:09:32"),
    ("Y8", "MO4APCspVVDc", "00:33:29", "00:33:41"),
    ("Y9", "MO4APCspVVDc", "00:19:15", "00:19:28"),
    ("Y10", "MO4APCspVVDc", "00:13:40", "00:14:00"),
    ("Y11", "MO4APCspVVDc", "00:07:16", "00:07:26"),
    ("Y12", "A6jPkRdPfPff", "00:08:13", "00:08:38"),
    ("Z1", "MO4APCspVVDc", "00:31:19", "00:31:31"),
    ("Z2", "BgtrFsWR1Gwo", "00:16:06", "00:16:15"),
    ("Z3", "UDn8oYKT8uFb", "00:43:23", "00:43:35"),
]


def load(eid):
    lines = []
    for raw in FILES[eid].read_text(encoding="utf-8", errors="ignore").splitlines():
        s = raw.strip()
        if len(s) > 11 and s[0] == "[" and s[3] == ":" and s[6] == ":" and s[9] == "]":
            lines.append((s[1:9], raw.rstrip()))
    return lines


def take(eid, t1, t2):
    lines = load(eid)
    idx = [i for i, (ts, _) in enumerate(lines) if t1 <= ts <= t2]
    if not idx:
        raise SystemExit(f"未命中: {eid} {t1}~{t2}")
    return [lines[i][1] for i in range(idx[0], idx[-1] + 1)]


def stanza(eid, t1, t2):
    body = take(eid, t1, t2)
    first = body[0][1:9]
    last = body[-1][1:9]
    text = "\n".join("> " + ln for ln in body)
    return f"{text}\n\n—— `{eid}` `[{first}]`~`[{last}]`"


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        keys = {s[0] for s in SPECS}
        assert len(keys) == len(SPECS), "重复 key"
        out = []
        for k, eid, t1, t2 in SPECS:
            body = take(eid, t1, t2)
            out.append(f"=== {k} {eid} {t1}~{t2} ({len(body)} 行)")
            out.extend(stanza(eid, t1, t2).splitlines())
            out.append("")
        p = ROOT / "tools" / "_b89_dump.txt"
        p.write_text("\n".join(out) + "\n", encoding="utf-8")
        print(p)
        sys.exit(0)
