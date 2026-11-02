#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe_names2.py — 第二轮：精确仓库名 + 真实英文单词

第一轮教训：GitHub `in:name` 是子串匹配，命中数虚高
  "pisha" 匹到 PiSharp(70★)，"liuzhen" 匹到 liuzhengyang(15★) —— 都不算撞车
所以这一轮改用：
  1. 精确仓库名探测：GET /repos/{owner}/{repo} 无法穷举，
     改用搜索后本地过滤 —— 只保留 name 段与 token 完全相等的
  2. 英文名必须是**真词**（能默写、能念、拼写唯一），
     不生造拼音，否则用户搜不到
  3. 中文名 2 字，拼音 token 唯一

候选（英文都是真正的英文单词，检索友好）：
  alambic  蒸馏器/明炉   炼金与蒸馏的核心器物，软件开发领域极罕见
  crucible 坩埚         强热熔炼，词短好拼
  sift     筛            从粗料筛出细料
  quench   淬火          骤冷定型（对应"立刻验证"）
  refine   精炼          提炼提纯
  temper   炮制/回火     中医药炮制 = 处理素材，词冷门但好拼
"""
import json
import re
import sys
import time
import urllib.request

CANDS = [
    ("alambic", "明炉"), ("crucible", "坩埚"), ("sift", "筛"),
    ("quench", "淬火"), ("refine", "精炼"), ("temper", "炮制"),
    ("gangui", "坩埚"), ("taoxi", "淘洗"), ("chengming", "澄明"),
]

UA = {"User-Agent": "name-probe2/1.0", "Accept": "application/vnd.github+json"}


def req(url, t=25):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=t
    )


def gh_exact(token):
    """只保留 name 段 == token 的仓库（真撞车才算）"""
    try:
        d = json.loads(req(
            "https://api.github.com/search/repositories?q=%s+in:name&per_page=50" % token
        ).read())
    except Exception as ex:
        return None, [f"ERR:{type(ex).__name__}"]
    items = d.get("items", [])
    exact = [
        f"{i['full_name']}({i.get('stargazers_count',0)}★)"
        for i in items
        if i["name"].lower() == token.lower()
    ]
    return d.get("total_count", -1), exact


def registry_free(name, host):
    try:
        req(f"https://{host}/{name}", t=15)
        return "占"
    except urllib.error.HTTPError as e:
        return "空" if e.code == 404 else f"?{e.code}"
    except Exception as ex:
        return f"?{type(ex).__name__}"


def main():
    print(f"{'token':<11}{'中文':<6}{'GH子串':>7}{'GH精确':>8}{'PyPI':>5}{'npm':>5}   精确同名仓库")
    print("-" * 92)
    for tok, zh in CANDS:
        n, exact = gh_exact(tok)
        py = registry_free(tok, "pypi.org/pypi")
        np = registry_free(tok, "registry.npmjs.org")
        print(f"{tok:<11}{zh:<6}{n:>7}{len(exact):>8}{py:>5}{np:>5}   {'  '.join(exact[:3])}")
        time.sleep(7)
    print("\nGH精确=0 表示没有任何仓库**就叫**这个名字；GH子串只是参考。")


if __name__ == "__main__":
    sys.exit(main())
