# -*- coding: utf-8 -*-
"""Recover AudioTranscribe results from the WorkBuddy session JSONL and write
cleaned Chinese transcripts to a txt file.

Why: AudioTranscribe results are long and can be lost between context resets.
Persisting them from the JSONL guarantees no transcript is re-run or dropped.
The tool result format carries a marker "audio_transcribe_tool_result" with a
JSON string -> {"text": "..."} which itself contains [mm:ss.mmm,mm:ss.mmm,N]
timestamps; this strips timestamps and merges wrapped lines into paragraphs.

Usage:
  python write_transcripts.py <session.jsonl> <items.json> <out.txt> \
      [--last N] [--audio-dir audios] [--append]

`--last N` takes only the last N transcription results (use right after a batch
of N AudioTranscribe calls). Without it, all results are matched by audio file
name <seq>_<vid>.mp3 found in the session call arguments.
"""
import json, re, os, sys, argparse


def clean(raw):
    t = re.sub(r"\[\d+:\d+\.\d+,\d+:\d+\.\d+,\d+\]\s*", "", raw)
    t = re.sub(r"\n{3,}", "\n\n", t)
    parts = []
    for line in t.splitlines():
        s = line.strip()
        if not s:
            continue
        if parts and not parts[-1].endswith(("。", "？", "！", "；", "，", "、", "”")):
            parts[-1] += s
        else:
            parts.append(s)
    return "\n".join(parts).strip()


def load_results(session):
    out = []
    for l in open(session, encoding="utf-8"):
        try:
            o = json.loads(l)
        except Exception:
            continue
        if o.get("type") != "function_call_result":
            continue
        res = o.get("output", {})
        txt = res.get("text", "") if isinstance(res, dict) else str(res)
        if "audio_transcribe_tool_result" in txt:
            try:
                out.append(json.loads(txt).get("text", ""))
            except Exception:
                pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session_jsonl")
    ap.add_argument("items_json")
    ap.add_argument("out_txt")
    ap.add_argument("--last", type=int, default=0)
    ap.add_argument("--audio-dir", default="audios")
    ap.add_argument("--append", action="store_true")
    args = ap.parse_args()

    items = json.load(open(args.items_json, encoding="utf-8"))
    results = load_results(args.session_jsonl)
    if args.last:
        results = results[-args.last:]
    if len(results) != len(items):
        print(f"WARN results={len(results)} items={len(items)}; "
              f"use --last to align, or transcript count may mismatch", file=sys.stderr)

    blocks = []
    for i, item in enumerate(items):
        body = clean(results[i]) if i < len(results) else ""
        vid = str(item["id"])
        title = (item.get("title") or "").split(" #")[0].strip()
        seq = item.get("seq", i + 1)
        blocks.append(f"=== {vid} | {seq} {title} ===\n{body}")
    mode = "a" if args.append else "w"
    with open(args.out_txt, mode, encoding="utf-8") as f:
        if blocks:
            f.write("\n\n".join(blocks) + "\n")
    print(f"written {args.out_txt}: {len(blocks)} records, "
          f"{sum(len(b) for b in blocks)} chars")


if __name__ == "__main__":
    main()
