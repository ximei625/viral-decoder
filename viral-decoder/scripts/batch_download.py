# -*- coding: utf-8 -*-
"""Batch-download audio streams for a list of Douyin video ids.

Usage:
  python batch_download.py <items.json> <out_dir> [--port 9223] [--results results.json]

items.json: list of {"id": "<aweme_id>", "title": "..."} (order = download order)
For each item, intercept the video page's real media URLs via CDP, prefer the
DASH audio-only stream (media-audio / mp4a), fall back to full video stream,
curl it down, and convert to 16k mono mp3 with ffmpeg.

Requires: browser with remote-debugging-port (see launch_edge.sh), ffmpeg, curl.
"""
import json, os, subprocess, sys, argparse
from cdp_net import get_video_url, set_port


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("items_json")
    ap.add_argument("out_dir")
    ap.add_argument("--port", type=int, default=9223)
    ap.add_argument("--results", default=None)
    args = ap.parse_args()

    set_port(args.port)
    DATA = json.load(open(args.items_json, encoding="utf-8"))
    os.makedirs(args.out_dir, exist_ok=True)
    results_file = args.results or os.path.join(args.out_dir, "download_results.json")
    results = []
    for i, item in enumerate(DATA, 1):
        seq = item.get("seq", i)
        vid = str(item["id"])
        afile = os.path.join(args.out_dir, f"{seq:02d}_{vid}.mp3")
        if os.path.exists(afile) and os.path.getsize(afile) > 5000:
            print(f"[{seq}] cached", flush=True)
            results.append({**item, "audio": afile, "status": "cached"})
            continue
        try:
            cands = get_video_url(vid, 10)
        except Exception as e:
            print(f"[{seq}] CDP error {e}", flush=True)
            results.append({**item, "status": "cdp_error", "err": str(e)[:120]})
            continue
        if not cands:
            print(f"[{seq}] NO URL", flush=True)
            results.append({**item, "status": "no_url"})
            continue
        audio_url = next((u for u in cands if "media-audio" in u or "mp4a" in u), None)
        full_url = next((u for u in cands if "mime_type=video" in u and "media-video" not in u), None)
        url = audio_url or full_url or cands[0]
        raw = os.path.join(args.out_dir, f"{seq:02d}_{vid}.raw")
        subprocess.run(
            ["curl", "-s", "-m", "90", "-A", "Mozilla/5.0",
             "-H", "Referer: https://www.douyin.com/", url, "-o", raw],
            check=False,
        )
        if not (os.path.exists(raw) and os.path.getsize(raw) > 3000):
            print(f"[{seq}] raw fail", flush=True)
            results.append({**item, "status": "raw_fail"})
            continue
        r = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-vn",
             "-acodec", "mp3", "-ar", "16000", "-ac", "1", afile],
            capture_output=True, text=True,
        )
        sz = os.path.getsize(afile) if os.path.exists(afile) else 0
        if sz > 3000:
            print(f"[{seq}] OK {sz}", flush=True)
            results.append({**item, "audio": afile, "status": "ok", "size": sz})
        else:
            print(f"[{seq}] convert fail: {r.stderr[:100]}", flush=True)
            results.append({**item, "status": "conv_fail", "err": r.stderr[:120]})
        if os.path.exists(raw):
            os.remove(raw)
        json.dump(results, open(results_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(results, open(results_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    ok = sum(1 for r in results if r["status"] in ("ok", "cached"))
    print(f"DONE total={len(results)} ok={ok}")


if __name__ == "__main__":
    main()
