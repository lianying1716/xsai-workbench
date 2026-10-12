# 快手 / 知乎 扫码登录 · 设计

> 日期：2026-10-06
> 背景：采集平台账号适配器目前只支持「手动粘 Cookie」。用户要求给**快手、知乎**补扫码登录
> （微博、贴吧不做）。复用既有 `browser_qr.py`（抖音/小红书同款：无头 Chromium 打开登录页 →
> 截二维码 → 轮询 Cookie → 自动入库）。

---

## 1. 现状与可行性（已实测）

| 平台 | 登录页二维码 | 成功标志 | 无头可行性 |
|---|---|---|---|
| 知乎 | `canvas.Qrcode-qrcode`（canvas → 截图） | Cookie `z_c0` | ✅ 无头直接可取 |
| 快手 | 首页点「登录」→ `.qrcode-img img`（data URI PNG） | Cookie `passToken` | ⚠️ 无头必触验证码（`captcha.zt.kuaishou.com` iframe），需**真实显示** |

实测结论：
- 知乎：`https://www.zhihu.com/signin`，`canvas.Qrcode-qrcode` 稳定出现，截图即二维码。
- 快手：`https://www.kuaishou.com/?isHome=1`，点 `text=登录`（精确）后出现
  `.qrcode-img img`（内含 `data:image/png;base64,...`）。**headless / `--headless=new` 均被
  验证码拦截**；在虚拟显示（Xvfb）下以**有头模式**打开则正常出现二维码。

## 2. 方案

### 2.1 快手走「虚拟显示 + 有头」
- `browser_qr` 增加按平台配置：`needs_display: True` 时，若当前无 `DISPLAY`，
  用**进程内 Xvfb** 起一个虚拟显示（`:NN`），以 `headless=False` 启动 Chromium，
  会话结束/超时时**一并回收 Xvfb**。
- 反检测：注入 MediaCrawler 的 `libs/stealth.min.js`（随包携带）到全部扫码会话。
- Xvfb 缺失时给出**明确报错**，引导用户改「手动粘 Cookie」（不阻塞其它功能）。

### 2.2 知乎走无头
- 与抖音/小红书一致，无需虚拟显示；二维码用 canvas 截图。

### 2.3 提取规则
- 快手：Cookie 含 `passToken` → 成功；凭证明细 `{"cookie": "..."}`。
- 知乎：Cookie 含 `z_c0` → 成功；凭证明细 `{"cookie": "..."}`。

### 2.4 接线
- `crawl_platforms.py`：快手/知乎适配器 `supports_qr = True`，`qr_start/qr_poll` 委托
  `browser_qr`（微博、贴吧保持 `False`）。
- 前端无需改动：账号中心已按 `supports_qr` 显示「扫码登录 / 手动粘 Cookie」切换。

## 红线
- 只在 `platform-api/` 内改动/提交；Conventional Commits。
- 不新增 Python 依赖（Xvfb 属系统包，缺失时降级为可读报错 + 手动兜底）。
- 微博、贴吧**不**加扫码。现有 364 测试全绿。
- 浏览器/虚拟显示会话必须可靠回收（成功、超时、清理任务三条路径）。
