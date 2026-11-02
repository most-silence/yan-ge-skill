# snapshots/ · 版本快照

每次修改 `SKILL.md` **之前**必须先在这里留一份。没有快照不许动手。

## 命名

```
snapshots/YYYY-MM-DD-HHMM/
├── SKILL.md
├── PIPELINE_STATE.md
└── CHANGELOG.md
```

## 回滚方法

```bash
# 正确：用 revert，保留历史
git revert <commit>

# 禁止：reset --hard 会抹掉历史
# git reset --hard <commit>   ❌
```

没有 git 时，直接从这里复制回 `SKILL.md`，并在 `PIPELINE_STATE.md` 记「手动回滚至 YYYY-MM-DD-HHMM」。

## 什么时候必须留

| 场景 | 必须 |
|---|---|
| 任何 SKILL.md 修改 | ✅ |
| 大批素材合并 | ✅ |
| 盲评 revert 之前 | ✅（回滚也要能再回来） |
| 只改错别字 | 可选 |

## 保留策略

- 最近 5 个快照永久保留
- 更早的按「每次大版本留 1 个」精简
- 精简前在 `PIPELINE_STATE.md` 记录删了哪些
