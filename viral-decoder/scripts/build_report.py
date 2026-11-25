# -*- coding: utf-8 -*-
"""Build a standalone HTML teardown report from transcript txt files.

Reads one or more transcript files (format: `=== <id> | <seq> <title> ===` headers
followed by body text), auto-categorizes each entry, and emits a self-contained
HTML report with: overview stats, per-video cards (expandable, full transcript),
title/word-count table, and auto-extracted opening hooks + golden lines.

Usage:
  python build_report.py <out.html> <account_name> <douyin_id> <total_works> \
      <transcript1.txt> [transcript2.txt ...] \
      [--fan-count "≈8888"] [--note "..."]

The analysis framework (title formulas, hook patterns, funnel) is a separate
manual step performed by WorkBuddy and injected via --sections-json (optional).
"""
import re, html, os, sys, argparse, collections, json


def parse_transcripts(paths):
    pat = re.compile(r"^=== (\d+) \| (\d+) (.+?) ===\s*$")
    pat2 = re.compile(r"^=== (\d+) \| (.+?) ===\s*$")
    recs = {}
    for path in paths:
        if not os.path.exists(path):
            continue
        cur = None
        buf = []
        for ln in open(path, encoding="utf-8").read().split("\n"):
            m = pat.match(ln.strip()) or pat2.match(ln.strip())
            if m:
                if cur:
                    recs[cur]["text"] = "\n".join(buf).strip()
                if pat.match(ln.strip()):
                    cur = m.group(1)
                    recs[cur] = {"id": cur, "title": m.group(3).strip()}
                else:
                    cur = m.group(1)
                    recs[cur] = {"id": cur, "title": m.group(2).strip()}
                buf = []
            elif cur is not None:
                buf.append(ln)
        if cur:
            recs[cur]["text"] = "\n".join(buf).strip()
    return recs


def auto_cat(title, text):
    t = title + text[:400]
    rules = [
        (("收租", "二房东", "长租", "包租", "拼缝", "二道贩子"), "收租实战", "#1d4ed8"),
        (("潮汕", "四兄弟", "借鸡生蛋"), "潮汕商道", "#c2410c"),
        (("中产", "返贫", "危机", "陷阱", "下行", "存钱", "现金"), "中产风险", "#b91c1c"),
        (("民宿", "酒店", "客栈"), "民宿经营", "#0f766e"),
        (("穷", "富", "财商", "赚钱", "资产", "钱", "股息", "复利"), "财商认知", "#7c3aed"),
        (("低谷", "人生", "靠山", "相处", "幸福", "家", "孩子", "父母"), "情绪共鸣", "#0f766e"),
    ]
    for kws, name, color in rules:
        if any(k in t for k in kws):
            return name, color
    return "认知清单", "#0f766e"


def first_line(text):
    parts = re.split(r"(?<=[。？！])", text.strip())
    return (parts[0] if parts else "")[:120]


def build(args, recs):
    esc = lambda s: html.escape(str(s or ""))
    cards = []
    rows = []
    counts = collections.Counter()
    order = sorted(recs.items(), key=lambda kv: int(kv[0]))
    for i, (vid, r) in enumerate(order, 1):
        text = r["text"]
        n = len(text.replace(" ", "").replace("\n", ""))
        cat, color = auto_cat(r["title"], text)
        counts[cat] += 1
        hook = first_line(text)
        rows.append(f"<tr><td>{i:02d}</td><td>{esc(r['title'])}</td>"
                    f"<td>{esc(cat)}</td><td>{n}字</td></tr>")
        cards.append(f"""
    <details class="vid">
      <summary>
        <span class="seq">{i:02d}</span>
        <span class="vtitle">{esc(r['title'])}</span>
        <span class="badge" style="background:{color}">{esc(cat)}</span>
        <span class="words">{n}字</span>
      </summary>
      <div class="vbody">
        <div class="an">
          <div class="anrow"><span class="k">开头钩子</span><span class="v">{esc(hook)}</span></div>
        </div>
        <div class="script"><div class="sh">中文口播逐字稿（语音识别）</div>{esc(text).replace(chr(10), '<br>')}</div>
        <div class="vlink">视频链接：https://www.douyin.com/video/{vid}</div>
      </div>
    </details>""")

    total_words = sum(len(r["text"].replace(" ", "").replace("\n", "")) for r in recs.values())
    cat_line = " ｜ ".join(f"{k} {v}条" for k, v in counts.most_common())

    note_html = ""
    if args.note:
        note_html = f'<div class="note">{esc(args.note)}</div>'

    # WorkBuddy injects deeper manual analysis (sections 3+) as raw HTML here.
    extra_sections = ""
    if args.sections_json and os.path.exists(args.sections_json):
        sj = json.load(open(args.sections_json, encoding="utf-8"))
        for title, body_html in sj.get("sections", []):
            extra_sections += f"<h2>{esc(title)}</h2><div class=\"card\">{body_html}</div>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>抖音账号拆解 · {esc(args.account_name)}</title>
<style>
:root{{--bg:#f6f6f3;--card:#fff;--ink:#1d1d1b;--sub:#6b6b66;--line:#e4e4de;--accent:#0f766e}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;line-height:1.75;font-size:14px}}
.wrap{{max-width:1080px;margin:0 auto;padding:44px 22px 90px}}
h1{{font-size:30px;margin:0 0 6px;letter-spacing:-.5px}}
.subtitle{{color:var(--sub);font-size:13px;margin-bottom:34px}}
h2{{font-size:20px;margin:52px 0 18px;padding-left:12px;border-left:4px solid var(--accent)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:22px 24px;margin-bottom:18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px}}
.stat .n{{font-size:26px;font-weight:700;color:var(--accent)}}
.stat .l{{font-size:12px;color:var(--sub);margin-top:2px}}
.note{{background:#fffbeb;border-left:3px solid #f59e0b;padding:13px 17px;border-radius:0 8px 8px 0;font-size:12.5px;color:#78350f;margin:16px 0}}
ul{{padding-left:20px;margin:8px 0}} li{{margin:7px 0}}
.vid{{background:var(--card);border:1px solid var(--line);border-radius:10px;margin-bottom:10px;overflow:hidden}}
.vid summary{{cursor:pointer;padding:13px 16px;display:flex;align-items:center;gap:10px;list-style:none;flex-wrap:wrap}}
.vid summary::-webkit-details-marker{{display:none}}
.vid summary:hover{{background:#fafaf8}}
.seq{{color:#aaa;font-weight:700;font-size:13px;min-width:24px}}
.vtitle{{font-weight:600;font-size:14px;flex:1;min-width:200px}}
.badge{{color:#fff;font-size:10px;padding:2px 9px;border-radius:10px;white-space:nowrap}}
.words{{color:#bbb;font-size:11px;white-space:nowrap}}
.vbody{{padding:4px 18px 18px;border-top:1px solid var(--line)}}
.an{{background:#f7f8f6;border-radius:8px;padding:12px 16px;margin:14px 0}}
.anrow{{display:flex;gap:12px;padding:5px 0;font-size:12.5px}}
.anrow .k{{color:var(--accent);font-weight:600;min-width:66px;flex-shrink:0}}
.anrow .v{{color:#333}}
.script{{background:#fbfbf9;border:1px dashed var(--line);border-radius:8px;padding:14px 16px;color:#3a3a36;font-size:13px;line-height:1.9}}
.sh{{font-size:11px;color:#999;margin-bottom:8px;letter-spacing:.5px}}
.vlink{{font-size:10.5px;color:#aaa;margin-top:9px;word-break:break-all}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{background:#f0f0ec;text-align:left;padding:10px 11px;font-weight:600;color:#444}}
td{{padding:11px;border-top:1px solid var(--line);vertical-align:top}}
.tip{{font-size:11px;color:var(--sub);margin-top:10px}}
</style></head><body>
<div class="wrap">
<h1>抖音账号拆解：{esc(args.account_name)}</h1>
<div class="subtitle">抖音号 {esc(args.douyin_id)} · 拆解范围：账号全部作品中文逐字稿 · 生成日期 {args.date}</div>

<h2>一、账号概览</h2>
<div class="grid">
  <div class="stat"><div class="n">{args.total_works}</div><div class="l">作品总数</div></div>
  <div class="stat"><div class="n">{esc(args.fan_count)}</div><div class="l">粉丝数（观察值）</div></div>
  <div class="stat"><div class="n">{len(recs)}</div><div class="l">已提取逐字稿</div></div>
  <div class="stat"><div class="n">{total_words}</div><div class="l">逐字稿总字数</div></div>
</div>
<div class="card" style="margin-top:18px"><strong>内容分类分布</strong>
<div class="tip" style="font-size:13px;color:#444">{esc(cat_line)}</div></div>
{note_html}

<h2>二、全部中文文案（标题 + 中文口播逐字稿）</h2>
<div class="tip">点击每条展开查看开头钩子与完整逐字稿。文案来自语音识别，个别字词可能有误差。</div>
<div style="margin-top:14px">{''.join(cards)}</div>

<h2>三、标题清单</h2>
<div class="card"><table>
<thead><tr><th>序号</th><th>标题</th><th>分类</th><th>字数</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
{extra_sections}

<div class="note" style="margin-top:26px">
数据说明：账号基础数据与标题来自抖音主页观察；口播逐字稿由视频音频语音识别生成，个别字词可能存在误差；播放/点赞等平台数据实时变动。视频为临时下载，任务完成后已按要求清理，仅保留文案与本报告。
</div>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_html")
    ap.add_argument("account_name")
    ap.add_argument("douyin_id")
    ap.add_argument("total_works", type=int)
    ap.add_argument("transcripts", nargs="+")
    ap.add_argument("--fan-count", default="—")
    ap.add_argument("--note", default="")
    ap.add_argument("--date", default="")
    ap.add_argument("--sections-json", default=None)
    args = ap.parse_args()
    if not args.date:
        import datetime
        args.date = datetime.date.today().isoformat()
    recs = parse_transcripts(args.transcripts)
    doc = build(args, recs)
    open(args.out_html, "w", encoding="utf-8").write(doc)
    print(f"报告生成: {args.out_html}")
    print(f"收录 {len(recs)} 条 | 卡片 {doc.count('<details class=\"vid\"')} | {len(doc)} chars")


if __name__ == "__main__":
    main()
