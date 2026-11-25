---
name: viral-decoder
description: 「爆款解码器」——拆解任意抖音账号，批量提取全账号中文口播逐字稿（语音识别），做爆款内容分析（标题公式/开头钩子/结构/金句/引流漏斗/同类对比），生成自包含HTML报告。当用户要求"拆解/扒/分析某个抖音号""提取抖音视频中文文案/逐字稿""对标账号内容分析""复刻某账号内容""用爆款解码器拆解"时使用。输入通常是抖音号或账号名，输出是文案合集txt + HTML拆解报告。
---

# 爆款解码器（viral-decoder）

> 中文名：**爆款解码器**　|　系统标识：`viral-decoder`　|　前身：`douyin-teardown`

## Overview

把一个抖音账号的口播内容批量扒成中文逐字稿，并做爆款内容分析，产出可直接用于对标/复刻的 HTML 报告。已在 86 条作品的账号上跑通并闭环校验（86=86，无缺无多）。

核心难点不在"抓"，在于：抖音反爬、登录态、DASH 音频流、转录结果易丢。**先读 `references/lessons.md`**，那里是踩坑后的唯一可行路径，能避免走回头路。

## 工作目录约定

在用户当前工作区下建一个以账号命名的目录，例如 `<workspace>/抖音拆解-<账号名>/`，所有中间产物和交付物都放这里。

## 完整工作流（6 阶段）

### 阶段 0 · 定位账号

- 抖音号不是 sec_uid。先拿到目标账号的 `sec_uid`（`MS4wLjABAAAA...`）和主页 `https://www.douyin.com/user/<sec_uid>`。
- 方法：WebFetch 搜账号名 / 第三方数据站反查 / 从任一视频详情页反查。视频 ID 越大越新，用于近似按发布时间排序。
- 记录账号显示的**作品总数**（后面做闭环校验的基准）。

### 阶段 1 · 采集完整作品列表

优先级从高到低：

1. **登录态浏览器扩展**（拿全列表的关键）：接管已登录的抖音主页标签，`dom_cua_get_visible_dom` 读作品链接。**先按 `Control+-` 把页面缩到最小**，一屏约 30 条；再 `PageDown` 逐屏抓取，每段立即存档 ID。
2. **CDP 拦截兜底**（无登录态通常只到 21-29 条）：
   ```bash
   # 先确保 CDP 浏览器常驻（见阶段 2）
   python scripts/collect_ids.py <sec_uid> works.json --port 9223 --expected <作品总数> --rounds 40
   ```
- 合并两路 ID、去重，**过滤推荐流无关视频**（按账号归属/ID连续性/标题主题判断，可疑的用 WebFetch 抽查）。
- 输出 `works.json`：`[{"id": "<aweme_id>", "title": "..."}, ...]`（数组顺序 = 处理顺序）。

### 阶段 2 · 启动 CDP 调试浏览器（必须先做，且要常驻）

```bash
# WorkBuddy Bash 工具，run_in_background=true —— 必须！否则 shell 结束会杀掉端口
bash scripts/launch_edge.sh 9223 ./_edge_profile
# 等端口就绪
curl -s http://127.0.0.1:9223/json/version
```
- 公开视频用干净 profile 即可，无需登录态。
- Edge 启动若 exit 127，见 `references/lessons.md` 第 4 节。

### 阶段 3 · 批量下载音频

```bash
python scripts/batch_download.py works.json audios --port 9223 --results download_results.json
```
- 脚本自动抓 DASH 音频流、转 16k 单声道 mp3，含断点缓存。
- 28 条约需几分钟，用 `run_in_background=true` 跑，期间可并行准备分析。
- 校验：mp3 数量 == works 数量（或查看 results 里的 status）。

### 阶段 4 · 转录 + 写盘（防止丢失）

1. 用 `AudioTranscribe` 工具逐条转录 `audios/NN_<id>.mp3`，中文口播识别质量很好。每 6-10 条一批。
2. **每批立刻写盘**，从会话 JSONL 恢复（转录结果在上下文压缩时会丢）：
   ```bash
   python scripts/write_transcripts.py <session.jsonl> works.json transcripts/batch_a.txt --last 10
   ```
   - `<session.jsonl>` 通常在 `C:/Users/HUAWEI/.workbuddy/projects/<project>/*/<uuid>.jsonl`，取当前会话文件。
   - `--last N` 要等于本批转录条数，且此时 JSONL 末尾 N 条正好是本批结果——**转录完不要穿插大量其它工具调用**，否则对齐会错。
   - 分批写 `batch_a.txt`、`batch_b.txt`…，每批校验条数。
3. 脚本无 `AudioTranscribe` 工具权限时，用 DeferExecuteTool 调（先 ToolSearch）。

### 阶段 5 · 闭环校验 + 生成报告

```bash
# 闭环：账号ID数 == 文案ID数，双向差集为0
python - << 'EOF'
import json,re,glob
done=set()
for p in glob.glob('transcripts/*.txt'):
    done|=set(re.findall(r'\b(7\d{18})\b',open(p,encoding='utf-8').read()))
works=set(str(x['id']) for x in json.load(open('works.json',encoding='utf-8')))
print('works',len(works),'transcripts',len(done))
print('缺',works-done,'多',done-works)
EOF
```

生成报告（脚本产出基础报告 + 标题清单 + 自动分类）：
```bash
python scripts/build_report.py <报告.html> "<账号名>" <抖音号> <作品总数> \
  transcripts/batch_*.txt --fan-count "≈8888" --date 2026-11-24
```

然后 WorkBuddy **手动完成深度分析**（这是 skill 的价值所在，按 `references/analysis-framework.md`）：
- 从全部标题提炼 6 大爆款标题公式；
- 抽代表性文案的开头/结尾，逐条填 4 维拆解（钩子/结构/金句/观察）；
- 找统一引流尾板与钩子词，画引流漏斗；
- 做同类账号五维对比；
- 写"给委托方的可借鉴点"（必须回答"怎么变成钱"）。
- 把这些分析作为 HTML 片段写进 `sections.json`（`{"sections":[["标题", "<div>...</div>"], ...]}`），用 `--sections-json sections.json` 重新生成报告。

### 阶段 6 · 清理 + 交付

- 关闭 CDP 浏览器（按命令行含 `remote-debugging-port`/profile 名筛进程再 Stop）。
- 删除 `audios/`、`_edge_profile/` 等中间产物（profile 用 robocopy 空目录镜像法，见 lessons.md 第 6 节）。
- 只保留：文案 txt、HTML 报告、分析存档。
- 用 `present_files` 打开 HTML 预览 + 文案合集。
- 更新工作日志（`.workbuddy/memory/YYYY-MM-DD.md`）。

## 验收清单（必须全部通过才算完成）

- [ ] 账号总作品数 == 文案条数 == 报告卡片数 == 报告去重视频链接数
- [ ] 文案双向差集为 0（无缺无多）
- [ ] 报告含：概览 / 全部逐字稿 / 标题清单 / 深度分析 / 数据说明
- [ ] 中间音频与临时 profile 已清理
- [ ] 已 present 预览，工作日志已更新

## Resources

### scripts/
- `cdp_net.py` — CDP 拦截视频真实音频流；`get_video_url(vid)` 返回候选 URL。
- `collect_ids.py` — 拦截作品列表 API + 滚动抓全账号作品 ID。
- `launch_edge.sh` — 常驻启动带调试端口的 Edge（用 run_in_background=true）。
- `batch_download.py` — 批量下载音频转 mp3（优先 DASH 音频流，断点续传）。
- `write_transcripts.py` — 从会话 JSONL 恢复 AudioTranscribe 结果并清洗写盘。
- `build_report.py` — 从转录文件生成自包含 HTML 报告（可注入深度分析片段）。

### references/
- `lessons.md` — **必读**：账号定位/登录态/反爬/DASH音频/转录防丢/清理的踩坑与可行路径。
- `analysis-framework.md` — 爆款标题公式、口播骨架、4 维拆解、引流漏斗、同类对比五维法、写作红线。
