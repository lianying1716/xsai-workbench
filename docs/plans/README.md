# 分期计划索引（docs/plans/）

平台按「设计 → 实施计划 → 实施 → 验收」推进，每个特性通常一对文档：
`*-design.md`（怎么设计）+ `*-plan.md`（怎么落地）。文件前缀是启动日期，不是完成日期。

> 状态说明：这些是**历史规划留痕**，多数特性已实现并合入 `main`。
> 代码现状以 `platform-api/` 仓库为准；本文档只回答「当初为什么这么做」。

## 已实现（设计 + 计划）

| 特性 | 设计 | 计划 |
|------|------|------|
| 抖音评论富集 | [design](2026-10-05-douyin-comment-enrichment-design.md) | [plan](2026-10-05-douyin-comment-enrichment-plan.md) |
| 架构地基补全 + kuaishou/zhihu 原生抽离 | [design](2026-10-06-architecture-foundation-and-native-crawlers-design.md) | [plan](2026-10-06-architecture-foundation-and-native-crawlers-plan.md) |
| 关注博主列表（抖音 / B站） | [design](2026-10-06-followed-creators-design.md) | [plan](2026-10-06-followed-creators-plan.md) |
| 快手 / 知乎 扫码登录 | [design](2026-10-06-kuaishou-zhihu-qr-login-design.md) | [plan](2026-10-06-kuaishou-zhihu-qr-login-plan.md) |
| 订阅同步设置丰富化 + 模拟数据 | [design](2026-10-06-rich-sync-settings-and-demo-data.md) | [plan](2026-10-06-rich-sync-settings-plan.md) |
| 订阅打通 + 抓取缓存 + 风控 | [design](2026-10-06-sync-cache-and-risk-control-design.md) | [plan](2026-10-06-sync-cache-and-risk-control-plan.md) |
| 爆款拆解 + 对标账号拆解 | [design](2026-10-06-viral-breakdown-design.md) | [plan](2026-10-06-viral-breakdown-plan.md) |

## 已实现（单项计划）

- [platform-api 收尾加固（Phase A）](2026-10-05-phase-a-hardening.md)
- [单篇公众号文章 URL 导入（Phase B）](2026-10-05-phase-b-article-import.md)

## 调研与决策留痕

- [素材加工分档 · 视频理解实现调研](2026-10-05-video-understanding-tier-research.md)
- [素材加工分档（L1/L2/L3）实施计划](2026-10-05-l3-tiered-processing-plan.md)
- [L3 视频理解 · 按类型区分提示词设计](2026-10-05-l3-type-aware-prompting-design.md)
- [任务：分档从三档简化为两档（删除抽帧档）](2026-10-06-two-tier-simplification-brief.md)
- [微信公众号内容能力调查报告](2026-10-05-wechat-mp-investigation.md) —— 公众号能力边界的依据
- [爆款拆解 + 对标账号拆解 · 成熟方案调研](2026-10-06-viral-breakdown-competitor-research.md)

## 验收证据（docs/plans/evidence/）

各阶段真机/端到端验收的截图与脚本留档，按验收批次归档（`2026-10-05-*`、`2026-10-06-*`）。

> **注意**：`evidence/` 里的 `verify*.py` / `seed.py` 等是一次性验收脚本，路径多为绝对路径，
> 仅作证据留痕，**不是可复用工具**，后续开发不要依赖它们。
