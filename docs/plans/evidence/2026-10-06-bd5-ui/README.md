# bd5_ui（Task 5 前端）真机验收证据

日期：2026-10-06 · 提交：`0faf106 feat: viral breakdown and creator report UI`

**环境**：隔离实例（临时 SQLite + 已知密码，seed 12 条内容 / 6 条拆解各状态），
真实 Chrome 149 headless，CDP `Input` 域真实鼠标事件驱动，`Network` 域核对真实 API 调用，
`Runtime`/`Log` 域收割报错（全程 0 报错）。

| 截图 | 场景 | 关键断言 |
|---|---|---|
| 01-asset-full-breakdown.png | 素材详情·完整拆解 | 评分 86%、结论、10 个板块（钩子/结构/节奏/文案/心理触发/CTA/评论洞察/数据上下文/复刻蓝图/落地建议）、按钮「重新拆解」 |
| 02-asset-degraded.png | 无 L3 的降级报告 | 显示「无视频理解（降级报告）」标签 |
| 03-asset-empty.png | 从未生成 | 显示「尚无拆解报告」，**不**误显示「拆解中」 |
| 04-asset-pending-after-request.png | 点「生成爆款拆解」后 | 真实 `POST /api/assets/4/breakdown {"force":false}`，UI 进入「拆解中」轮询 |
| 05-asset-error.png | 拆解失败 | 显示「失败」标签 + 错误文案 `LLM 调用失败：connection timeout` |
| 06-creator-report.png | 数据看板·对标账号 | 行点击打开弹层，7 板块齐全，爆款阈值「自身中位数 × 3」 |

**真实 API 断言**（同一会话内从浏览器 Network 域读取）：
- `POST /api/assets/4/breakdown {"force":false}`（首次生成）
- `POST /api/assets/1/breakdown {"force":true}`（重新拆解）

**说明**：作者行 `row-click` 曾因 CDP 仅改 hash、未重载文档导致旧 bundle 假阴性；强制整页重载后通过。
