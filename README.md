# MD Liner Notes

手工 MiniDisc 封面背后的曲目介绍页。封面上的二维码指向 `albums/<slug>/`。

## 内容类型

### MD 专辑衬页
- `albums/<slug>.json` — 专辑数据（曲目、注解、随笔）
- 生成 `docs/albums/<slug>/index.html`

### 听歌日记（Listening Sessions）
- `listening/<slug>.json` — 听歌记录（时间线、曲目、体会）
- 生成 `docs/listening/<slug>/index.html`
- 封面图自动下载至 `docs/listening/<slug>/covers/`

## 构建

- `tools/build_site.py` — 生成 `docs/`（GitHub Pages 源）
- `private/` — 原始 GPT 对话（git 忽略，不公开）
