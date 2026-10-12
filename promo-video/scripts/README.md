# promo-video/scripts — 制作流程的可执行部分

SOP 讲「怎么做」，这里放「能重跑的东西」。所有脚本只用 system python3 + 已装的
`numpy / scipy / librosa / ffmpeg / ffprobe`，不需要额外安装。

| 脚本 | 作用 |
|---|---|
| `audit_video.py` | 对抗性验收器：不看图，用可复算的量给片子打分，输出 JSON + 退出码 |
| `make_beat_grid.py` | 从 BGM 生成真实脉冲节拍网格（锁定 BPM，解决 4 倍相位歧义） |
| `make_frame_sheets.py` | 把视频切成带时间戳的关键帧板（总览 + 每 6~8s 细节板），供视觉大模型拆解 |
| `mimo_teardown.py` | 用 MiMo-V2.6 对关键帧做 7 视角语义拆解（含 `improve_ours` 对标本片） |
| `teardown_video.py` | 六维量化拆解器（结构/运动/文字/声音/卡点/配色），对标大厂参考片 |

本次 v7 的审计证据：`../evidence/audit-v7.json`（顶层 `evidence/`，不被 .gitignore 排除）。

## 跑验收（在 `videos/stargather-promo/` 里执行）

```bash
python3 ../../scripts/audit_video.py renders/stargather-promo-v7.mp4 \
  --total 59.9 --grid-json assets/beat-grid-v3.json --bgm assets/bgm-v3.mp3 \
  --countup   "6.4:9.6:380:180:260:150" \
  --playback  "35.5:38.5:193:179:285:160:640:300:280:160" \
  --scale-windows "26.0:27.7:38:86:596:335,18.0:19.6:38:86:596:335" \
  --json ../../evidence/audit-v7.json
```

窗口/区域的坐标是 **960×540 分析分辨率**下的像素（脚本内部固定缩放到这个尺寸）。
退出码 `0` = 全部过线，`1` = 有项目未过线。

探针的已知边界（避免误用，见 `SOP.md` §三「指标本身会说谎」）：
- `--countup` / `--typing` / `--playback` 的区域要手工给对；给错区域会得出无意义结论。
- `--scale-windows` 测的是**区域内**推近；整机位推近直接给 `t0:t1` 即可。
- `low-motion` 不等于「死帧」；判断「观众会不会觉得卡住」要结合内容层看。

## 生成节拍网格

```bash
python3 ../../scripts/make_beat_grid.py assets/bgm-v3.mp3 \
  -o assets/beat-grid-v3.json --bpm-range 55 110 --align-to 3.4366
```

自动 BPM 会在真值 / 2 倍 / 无关候选之间飘，所以 `--bpm-range` 用来限定基频区间，
`--align-to` 用来消除「4 个下拍候选差一拍」的固有歧义（给一个已知落在小节头的时刻即可）。
