# 管线脚本索引

全部脚本为项目实战版；通用说明见玟火仓库
[wenhuo-skill/tools/](https://github.com/most-silence/wenhuo-skill/tree/main/tools)。
运行方式：`& tools\.venv\Scripts\python.exe -u -X utf8 tools\<脚本>.py`（Windows）。

## 抽取与校验

| 脚本 | 作用 |
|---|---|
| `verify_quotes.py` | 引文逐字率自验（批读完成后必须跑，<100% 重抄） |
| `triage_quotes.py` | 不匹配引文分类：A 格式 / B 拼接 / C 改写 / E 编造 |
| `repair_quotes.py` | 自动修复 A/B 类 |
| `audit_points.py` | 3,023 点位 vs 真实日 K 对账（区分事实/预测/回顾三角色） |

## 归并链

| 脚本 | 作用 |
|---|---|
| `bucket_rules.py` | 26 主题桶分桶（写池内编号 P####，跨桶追踪的根） |
| `merge_candidates.py` | 字段抽取（`extract_field` 标签到标签切片） |
| `spotcheck_merge.py` | 归并质检六项（对账/要素/引文/边界声明） |
| `cross_bucket_dedup.py` | 文本相似弱信号（只作参考） |
| `candidate_trace.py` | 池内编号跨桶追踪 + 强关联规则对（可靠信号） |
| `rule_digest.py` | 六组规则摘要（喂模型提取） |
| `coverage_audit.py` | Q10 覆盖率审计 |

## 数据

`research/大盘数据.json`：腾讯日 K，437 bars（2025-01-02 → 2026-10-26），对账基准。
