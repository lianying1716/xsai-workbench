# 快手 / 知乎 扫码登录 实施计划

> 设计：`docs/plans/2026-10-06-kuaishou-zhihu-qr-login-design.md`

**Goal:** 快手、知乎支持浏览器扫码登录并自动入库 Cookie；微博/贴吧保持不变。

## Global Constraints
- 只在 `platform-api/` 内改动/提交；Conventional Commits。
- 不新增 Python 依赖；微博、贴吧不加扫码；测试全绿。

---

### Task 1: browser_qr 支持快手/知乎（含虚拟显示）
**Files:** Modify `app/modules/browser_qr.py`；Create `app/modules/crawler/libs/stealth.min.js`；Test `tests/test_browser_qr.py`
**Produces:** `_PLATFORM_CONF` 增 `kuaishou`(needs_display)/`zhihu`；Xvfb 生命周期管理；cookie 成功判定
- [ ] 失败测试（配置/判定/回收）→ 实现 → 提交 `feat: browser QR login for kuaishou/zhihu`

### Task 2: 适配器接线
**Files:** Modify `app/modules/crawl_platforms.py`、`tests/test_crawl_platform_adapters.py`
**Produces:** 快手/知乎 `supports_qr=True` 且委托 browser_qr；微博/贴吧仍 False
- [ ] 测试（注册/委托/微博贴吧仍 False）→ 提交 `feat: enable QR login for kuaishou/zhihu adapters`

### Task 3: 真机验收 + 文档
**Files:** 无代码（验收记录入 ledger）
**Produces:** Playwright 打开账号中心 → 选快手/知乎出现「扫码登录」→ 二维码渲染
- [ ] 验收 → 提交（如有修正）

## Self-Review
- 快手/知乎可扫码；微博/贴吧不变；会话可靠回收。
