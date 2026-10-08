# 统一登录态管理后台 · 落地设计（第一版）

> 目标：先做出整个平台的"地基"——一个能**集中查看、录入、加密保存、自动体检**所有平台账号登录态的小后台。
> 原则：能尽快跑起来、能直观管理登录态 > 一次铺满 PRD 全部模块。
> 范围：本文只设计"账号中心"这一块，不含抓取/同步/转录。那些是后续往这块地基上挂的模块。

---

## 0. 给新手的一句话总览

你现在 4 个项目各自存各自的登录信息，方式还都不安全（明文、无过期判断、闭源工具）。
这个后台要做的，就是把它们**收成一张加密的表 + 一个状态看板 + 一个定时体检器**。
做完后，你打开一个页面就能看到"我哪些号还活着、哪些快过期了"，并能一键补登录态。

---

## 1. 现状摸底（已逐项读源码确认，不是猜的）

| 平台来源 | 登录态是什么 | 现在存哪 | 加密? | 过期判断 |
|---|---|---|---|---|
| **B站** (bili-sync) | 5 字段：`sessdata` / `bili_jct` / `buvid3` / `dedeuserid` / `ac_time_value`(=refresh_token) | SQLite `config` 表 id=1 的大 JSON 里 | ❌ 明文 | ✅ 调 `cookie/info` 看 `refresh` 布尔；**自带刷新续期** |
| **抖音** (dysync.net) | 一段 Cookie 字符串 + `SecUserId` + `MyUserId` | SQLite `dy_cookie` 表 `Cookies` 字段 | ❌ 明文 | ✅ 调真实接口看 `StatusCode==0`；靠闭源 `dy.cookie.exe` 抓 Cookie |
| **微信公众号** (wechat-exporter) | `token` + 微信原始 cookie 数组 | 服务端 Nitro KV（`.data/kv` 文件），TTL 4 天 | ❌ 明文 | ⚠️ `isExpired` 是 **TODO，恒返回 false**，仅靠 4 天 TTL 兜底 |
| **小红书/快手** (MediaCrawler) | Cookie 字符串即可（签名已纯算法/无需重签） | Playwright 浏览器 `browser_data/` 目录 | ❌ | ✅ 启动调 `pong()` 探活 |
| **抖音/B站** (MediaCrawler 抓取路径) | Cookie **+ 浏览器 localStorage 里的运行时签名值**（msToken / WBI key） | 同上，活在浏览器进程里 | ❌ | ✅ 同上 |

**两个必须记住的风险点**（接管时要修掉）：
1. 微信导出项目有个 `_debug` 端点，带对密钥就能一次性导出**所有账号的明文 cookie**——接管后必须移除/锁死。
2. 所有项目的凭证现在都是**明文裸存**，统一后台第一要务就是加密。

---

## 2. 核心设计决策

### 决策 A：凭证分两类，表结构要能装下两类

- **`cookie` 类**（B站/抖音/微信/小红书/快手）：保存就是一组键值，注入请求头即可用。
- **`browser` 类**（抖音/B站走 MediaCrawler 抓取）：除 cookie 外，还需要一个"活浏览器"产出运行时签名值。

第一版后台**先把两类都登记进同一张表**，但 `browser` 类的"活浏览器"留到后续"browser_runtime"模块再做。第一版对 `browser` 类只做到"登记 + 状态展示"，不做现算签名。这样你能先把全部账号看全，又不会卡在最难的部分。

### 决策 B：凭证一律加密存储，前端只见脱敏

- 存库前用对称加密（如 AES-GCM），密钥来自环境变量 / 启动时生成的 keyfile（不进库、不进 git）。
- 前端永远只显示脱敏值（如 `SESSDATA: AB****yz`），完整值不下发。
- 这一条同时干掉"明文裸存"和"_debug 全量导出"两个风险。

### 决策 C：登录态获取方式，按平台分级

| 方式 | 适用 | 第一版是否做 |
|---|---|---|
| **浏览器一键导出 Cookie**（本机登录→导出→上传服务器） | 所有 `cookie` 类平台 | ✅ 第一版就做（**首选录入方式**，见第 9 章） |
| 手动粘 Cookie | 所有平台都支持（兜底，最快能跑通） | ✅ 第一版就做 |
| 扫码登录 | B站、微信公众号（原项目已有成熟流程） | 🔶 第二版接入（复用原逻辑） |
| 浏览器自动登录 | 抖音（原靠闭源 exe）、MediaCrawler 系 | 🔶 后续 browser_runtime 再做 |

**第一版做"浏览器一键导出 Cookie / 手动粘 Cookie + 自动体检"**，这是最快能让你"统一看到所有号状态"的路径。扫码/自动登录是体验增强，不是地基。

> 用户核心诉求是"在自己电脑登录后，把 cookie 提取出来传到无头服务器使用"。这条路**已实地验证可行且无需任何破解**，方案与限制详见新增的第 9 章。

---

## 3. 第一版数据模型

只要两张表（PostgreSQL，本地开发可先用 SQLite）：

```text
platform_account            -- 一个账号一行
  id              主键
  platform        枚举: bilibili / douyin / wechat_mp / xhs / kuaishou ...
  display_name    昵称/备注（用户自己填，便于辨认）
  external_id     平台侧用户ID（如 dedeuserid / SecUserId），可空
  credential_kind 枚举: cookie / browser
  status          枚举: active / expired / unchecked / error
  last_checked_at 上次体检时间
  expires_at      已知到期时间（能算出来就填，如微信 4 天）
  created_at / updated_at

account_credential          -- 与账号一对一（或一对多版本，先一对一）
  id              主键
  account_id      外键 -> platform_account
  ciphertext      加密后的凭证 blob（里面是该平台的字段 JSON）
  enc_algo        加密算法标记（便于将来换密钥/算法）
  created_at / updated_at
```

各平台 `ciphertext` 解密后的 JSON 形状（按现状落）：

```jsonc
// bilibili
{ "sessdata": "...", "bili_jct": "...", "buvid3": "...", "dedeuserid": "...", "ac_time_value": "..." }
// douyin
{ "cookie": "原始cookie字符串", "sec_user_id": "...", "my_user_id": "..." }
// wechat_mp
{ "token": "...", "cookies": [ {...}, {...} ] }
// xhs / kuaishou
{ "cookie": "原始cookie字符串" }
```

> 注意命名坑：B站把 refresh_token 叫 `ac_time_value`，照搬即可，别自己改名。

---

## 4. 第一版接口（后台 API）

统一前缀 `/api/accounts`，单管理员鉴权（后续接平台统一认证，第一版可先用一个固定 token）。

```text
GET    /api/accounts              列出所有账号（脱敏，带 status / expires_at / last_checked_at）
POST   /api/accounts              新建账号：平台 + 备注 + 粘贴的凭证 -> 校验 -> 加密入库
GET    /api/accounts/{id}         看单个账号详情（脱敏）
PUT    /api/accounts/{id}/credential   更新某账号的凭证（重新粘 cookie）
POST   /api/accounts/{id}/check   立即体检一次（调该平台真实探活接口）
DELETE /api/accounts/{id}         删除账号
```

每个平台需要一个 **探活适配器**（`checker`），就是把原项目里现成的"我还登着吗"判断抽出来：

| 平台 | 探活方法（直接复用原项目逻辑） |
|---|---|
| bilibili | GET `passport.bilibili.com/.../cookie/info` 看 `refresh`；可顺带跑原刷新逻辑续期 |
| douyin | 调原 `CheckCookie()` 对应的抖音接口，看 `StatusCode==0` |
| wechat_mp | 调一个公众号业务接口，看是否返回 `ret==200003`（未登录码）；**顺便把原项目没做的 `isExpired` 真正实现** |
| xhs/kuaishou | 复用 MediaCrawler 各 client 的 `pong()`（如小红书 `query_self()`） |

---

## 5. 第一版前端（一个页面就够）

**账号列表页**，一张表：

```
平台      备注        状态      到期时间        上次体检     操作
B站       主号        ● 在线    -              2分钟前      [体检] [更新Cookie] [删除]
抖音      运营号      ● 在线    -              5分钟前      [体检] [更新Cookie] [删除]
微信公众号 XX科技      ⚠ 快过期  还剩 6 小时     刚刚         [体检] [更新Cookie] [删除]
小红书    -          ✕ 已掉线   -              1小时前      [体检] [更新Cookie] [删除]
```

- 状态用颜色：绿=在线、黄=快过期、红=掉线/错误、灰=未体检。
- "新建账号"按钮：选平台 → 弹窗粘 Cookie/字段 → 提交即校验。
- 后台一个定时器（如每 15 分钟）跑一遍全部 `check`，前端只管展示结果。

这一个页面跑稳，你就达成了核心诉求："打开一个地方，所有号的死活一目了然，掉线能马上补。"

---

## 6. 技术选型建议（贴合 PRD，但第一版从简）

- **后端**：Python + FastAPI（PRD 已定，且 MediaCrawler/faster-whisper 都在 Python 生态，将来接它们最省事）。
- **数据库**：第一版本地开发可用 SQLite，部署用 PostgreSQL（PRD 已定）。表结构两者通用。
- **加密**：用成熟库（如 `cryptography` 的 Fernet/AES-GCM），密钥放环境变量或独立 keyfile，**绝不进 git、绝不进库**。
- **前端**：第一版可以极简（单页 + 表格），不必先上完整工作台框架。能用就行，后面再统一到工作台导航里。

---

## 7. 落地步骤（建议顺序）

1. 建 `platform-api` 最小骨架（FastAPI + 两张表 + 加密工具）。
2. 实现 `/api/accounts` 的增删查改 + 加密存取。
3. 先接 **2 个最容易的平台**做闭环：**B站**（字段清晰、自带探活）+ **抖音**（一段 cookie，探活接口现成）。
4. 做账号列表页 + "新建/更新 Cookie" 弹窗，跑通"粘 cookie → 入库 → 体检显示在线"。
5. 加定时体检器。
6. 再扩 微信公众号（顺手实现真过期判断）、小红书、快手。
7. 最后才考虑扫码登录、浏览器自动登录、browser_runtime（抖音/B站抓取签名）。

> 第 3~4 步做完，你就已经有一个"能用的统一账号中心"了。后面都是往上加平台。

---

## 8. 明确不做（第一版边界）

- 不做抓取、同步、转录、分析——那是挂在地基上的后续模块。
- 不做抖音/B站的 MediaCrawler 抓取签名（需活浏览器，留到 browser_runtime）。
- 不做多用户/多角色（PRD 已定：单管理员）。
- 不复刻原项目各自的独立前端/CLI/配置。
- 不保留 `_debug` 全量导出、明文 KV 这类不安全设计。

---

## 9. 浏览器 Cookie 提取与传输（已验证 · 首选录入方式）

> 用户场景：服务器是**无头**的，日常在**自己的图形化电脑**上登录各平台，希望"登录后把 cookie 提取出来传到服务器使用"。
> 本章是对该设想的技术验证结论与落地方案，已实地核查环境与浏览器加密现状（2026-06）。

### 9.1 结论先行

**可行，且全程不需要任何"破解"。** 因为我们是从**你正在登录着的活浏览器**里取明文 cookie，不是去解密磁盘上的 cookie 数据库文件。

- ⚠️ 要避开的坑：Chrome 127+ 在 **Windows** 上引入了 **App-Bound Encryption (ABE)**，专门防止程序直接解密磁盘 cookie 文件。网上一堆 "bypass ABE / decrypt v20" 的方案都和信息窃取木马同款手段，又脏又会随 Chrome 升级失效。**我们的方案根本不碰它。**
- ✅ 活浏览器取明文 cookie 是合法、标准、稳定的做法。

### 9.2 两条可行通道

| | 方案 A：浏览器扩展导出 | 方案 B：CDP 调试端口抓取 |
|---|---|---|
| 怎么做 | 本机装开源扩展（如 **Get cookies.txt LOCALLY**），登录后一键导出 cookie 文件，上传服务器 | 本机 Chrome 带 `--remote-debugging-port=9222` 启动，程序通过 CDP `Network.getAllCookies` 拉全部 cookie |
| 明文 | ✅ 不碰加密 | ✅ 不碰加密 |
| 自动化 | 手动点一下（适合"登录后导出"） | 可全自动 |
| 上手难度 | 极低，纯小白可用 | 中等，要改 Chrome 启动方式 |
| 定位 | **第一版首选** | 后续做自动化时上 |

> 佐证：本服务器现就有一个 Chrome 开着 `127.0.0.1:9222` 调试端口，MediaCrawler 用的也是 CDP 这条路——说明方案 B 在本环境是现成验证过能跑的。

### 9.3 第一版端到端流程（走方案 A）

```text
[你的电脑]                                    [无头服务器 platform-api]
正常登录 B站/抖音/微信/小红书
   │
   ├─ 浏览器扩展一键导出当前站点 cookie
   │   （Netscape cookies.txt 或 JSON，兼容 curl/Python）
   │
   └─ 在账号中心页面：选平台 → 上传/粘贴导出内容
                                              │
                                              ├─ 后端解析为该平台标准字段（见 §3 各平台 JSON 形状）
                                              ├─ AES-GCM 加密入库（前端只见脱敏）
                                              ├─ 立即跑一次探活 checker（§4）确认在线
                                              └─ 列表状态变绿 ✅
```

落地要点：
- 后端加一个**导入解析器**：吃 Netscape `cookies.txt` 或浏览器扩展导出的 JSON，按域名挑出该平台需要的字段，组装成 §3 的标准 JSON 再加密入库。
- B站需要的 `sessdata/bili_jct/buvid3/dedeuserid` 都在 cookie 里；`ac_time_value`(refresh_token) 不在 cookie 里——纯导出 cookie 可让账号"能用 + 能体检"，但**自动续期**仍需扫码登录补 refresh_token（二期）。这点要在 UI 上说清楚。
- 上传通道本身要鉴权（管理员 token），且只接受结构化 cookie 文本，不接受任意文件。

### 9.4 一个必须讲清的硬限制（与签名有关）

提取 cookie 能 100% 解决**"账号登录态统一管理"**这个核心目标（看死活、补登录、各平台同步类能力都靠 cookie）。

**但**：抖音、B站走 **MediaCrawler 关键词抓取** 时，每次请求的签名参数（`a_bogus` / `msToken` / WBI key）要在活浏览器的 `localStorage` 里**现算**——这些值不在 cookie 里。所以：

- bili-sync 的 B站同步、dysync 的抖音同步：**纯 cookie 就能跑**，提取传输方案完全够用。
- 抖音/B站的**关键词抓取**：cookie 解决登录态，但解决不了签名，仍需 browser_runtime（常驻浏览器），留到二期。

### 9.5 安全红线

- 上传的 cookie 文本一律加密入库，落库即脱敏，日志不打印明文。
- 扩展只选**开源、本地导出、不外传**的（如 Get cookies.txt LOCALLY 明确声明 never send outside）。
- 不在服务器侧保存导出原始文件，解析入库后即丢弃。
```
