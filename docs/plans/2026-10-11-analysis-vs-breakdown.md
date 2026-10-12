# 分析速览 / 爆款拆解：职责切分

## 背景

用户在界面上发现「AI 分析」和「爆款拆解」看起来有重复。核对代码后确认：

- AI 分析（`app/modules/analysis.py`）产出 `summary` + `tags` + `structured`。
- 爆款拆解（`app/modules/breakdown.py`）产出结论、评分、钩子、结构、节奏、复刻蓝图等完整报告。

真正的重复是 `analysis_result.structured` 里的 `{hook, structure, selling_point}` ——
它是拆解 `hook` / `structure` 的迷你重复版，而且**前端从未渲染**（全站零引用）。
等于为同一批信息付了两次模型费用，其中一次还白付。

## 结论

两者定位本来就不同（速览 vs 深度报告），保留两个能力，只去掉重复字段：

1. **删除 `analysis_result.structured`**（迁移 0019）。AI 分析回归纯「摘要 + 标签」速览。
2. **前端讲清区别**，避免用户再混淆。

## 改动清单

| 位置 | 改动 |
|------|------|
| `app/models.py` | `AnalysisResult` 去掉 `structured` 列，docstring 指明深度报告在 `ViralBreakdown` |
| `app/modules/analysis.py` | 提示词只要求 `summary` + `tags`；解析不再返回 `structured` |
| `app/workers/handlers.py` | 落库不再写 `structured` |
| `app/api/assets.py` | 详情响应去掉 `structured` |
| `alembic/versions/0019_*.py` | 删列迁移（SQLite 走 batch 模式） |
| `web/src/pages/Assets.vue` | tab 改名「分析速览」/「爆款拆解 · 深度」；两个面板顶部各加一句区别说明；卡片按钮改「速览」/「重新速览」，状态徽标改「速览」 |
| `Settings.vue` / `FollowedCreators.vue` | 「自动分析」改「自动生成速览」，说明深度拆解仍需手动触发 |
| `ModelAccess.vue` | 文字分析槽位说明：速览与拆解都走这里 |

## 用户能看到的区别

- **分析速览**：转录后自动可跑，只有一段摘要 + 几个标签，快、便宜，用于扫一眼和导出。
- **爆款拆解 · 深度**：手动触发，综合转录 / 视频理解 / 评论 / 互动数据，产出「为什么火 + 怎么复刻」，慢、费 token，但结论完整。

两个面板顶部都用一句话写明，且互相指路。
