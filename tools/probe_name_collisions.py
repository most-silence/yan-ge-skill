#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe_name_collisions.py — 候选框架名撞名体检

判定标准（用户要求：中英适配、无重复、易搜索）：
  · 中文名 + 同名拼音 = 单一 token（中英检索词一致）
  · GitHub 仓库名命中 ≈ 0
  · PyPI / npm 未占用
  · 拼音不是常见英文词/日语词（避免污染搜索结果）

候选池（10 个，均出自带点/格物/炼金之外的路子）：
  desui    得髓    禅宗「汝得吾髓」；闲聊=皮肉，规则=骨，方法=髓
  xuanzhu  玄珠    庄子·天地：黄帝遗玄珠，智/ sight/言皆不得，象罔得之
  pisha    披沙    披沙拣金；从 42% 闲聊和 ASR 沙砾里拣金
  gouchen  钩沉    索隐钩沉；正是数据对账干的事（把沉掉的 2800 钩回来）
  sanmei   三昧    得其三昧；三线+三验（对照：日语污染）
  liuzhen  留真    版本学「留真谱」：仿真本影刻；对应冲突不抹平
  wenhuo   文火    文火慢蒸；对应"慢慢获取、慢慢蒸馏"的节奏
  zhaogu   照骨    照骨镜：B 超式验证，点位对账现原形
  jiangu   见骨    蒸到见骨；话糙但准
  weiyan   微言    微言大义：从随口话里取大义（对照：撞"威严"）
"""
import json
import sys
import time
import urllib.request

CANDS = [
    ("desui", "得髓"), ("xuanzhu", "玄珠"), ("pisha", "披沙"),
    ("gouchen", "钩沉"), ("sanmei", "三昧"), ("liuzhen", "留真"),
    ("wenhuo", "文火"), ("zhaogu", "照骨"), ("jiangu", "见骨"),
    ("weiyan", "微言"),
]

UA = {"User-Agent": "collision-probe/1.0",
      "Accept": "application/vnd.github+json"}


def req(url, t=20):
    r = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(r, timeout=t)


def gh_count(name):
    """GitHub 仓库名含该 token 的数量 + 前三个仓库"""
    try:
        d = json.loads(req(
            f"https://api.github.com/search/repositories?q={name}+in:name&per_page=3"
        ).read())
        items = d.get("items", [])
        tops = [f"{i['full_name']}({i.get('stargazers_count',0)}★)" for i in items[:3]]
        return d.get("total_count", -1), tops
    except Exception as ex:
        return -1, [f"ERR:{type(ex).__name__}"]


def pypi_free(name):
    try:
        req(f"https://pypi.org/pypi/{name}/json")
        return False
    except urllib.error.HTTPError as e:
        return e.code == 404
    except Exception:
        return None


def npm_free(name):
    try:
        req(f"https://registry.npmjs.org/{name}")
        return False
    except urllib.error.HTTPError as e:
        return e.code == 404
    except Exception:
        return None


def main():
    print(f"{'token':<10}{'中文':<6}{'GH仓库名命中':>10}   {'PyPI':>6} {'npm':>6}  前三")
    print("-" * 88)
    for tok, zh in CANDS:
        n, tops = gh_count(tok)
        py = pypi_free(tok)
        np = npm_free(tok)
        py_s = "空" if py else ("占" if py is False else "?")
        np_s = "空" if np else ("占" if np is False else "?")
        print(f"{tok:<10}{zh:<6}{n:>10}   {py_s:>6} {np_s:>6}  {'  '.join(tops)}")
        time.sleep(7)  # GitHub search 未认证限流 10/min
    print("\n注：GH 命中含 fork/镜像；star=0 的小仓库不算真撞车，重点看同名+同领域。")


if __name__ == "__main__":
    sys.exit(main())
