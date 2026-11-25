# -*- coding: utf-8 -*-
"""Collect all aweme IDs from a Douyin user profile via CDP.

Two data sources, merged:
  1. Intercept `aweme/v1/web/aweme/post/` API responses (has desc + id).
  2. DOM links `a[href*="/video/"]` as backup (works on virtualized grids).
Scrolls the profile repeatedly. On a LOGGED-IN browser this reaches all works;
a clean profile typically caps out around 21-29 works (deep pagination needs
login/signature). If `expected` is provided, stops at that count.

Usage:
  python collect_ids.py <sec_uid> <out.json> [--port 9223] [--expected 86] [--rounds 40]
"""
import json, time, urllib.request, urllib.parse, websocket, sys, argparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sec_uid")
    ap.add_argument("out_json")
    ap.add_argument("--port", type=int, default=9223)
    ap.add_argument("--expected", type=int, default=0)
    ap.add_argument("--rounds", type=int, default=40)
    args = ap.parse_args()

    HOME = f"https://www.douyin.com/user/{args.sec_uid}"
    req = urllib.request.Request(
        f"http://127.0.0.1:{args.port}/json/new?" + urllib.parse.quote(HOME, safe=":/?=&"),
        method="PUT",
    )
    tab = json.load(urllib.request.urlopen(req, timeout=10))
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=40)
    i = 0

    def send(method, params=None):
        nonlocal i
        i += 1
        ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
        return i

    def call(method, params=None, wait=8):
        mid = send(method, params)
        t0 = time.time()
        while time.time() - t0 < wait:
            try:
                msg = json.loads(ws.recv())
            except Exception:
                break
            if msg.get("id") == mid:
                return msg
        return None

    def ev(expr, wait=8):
        r = call("Runtime.evaluate", {"expression": expr, "returnByValue": True}, wait=wait)
        try:
            return r["result"]["result"].get("value")
        except Exception:
            return None

    call("Network.enable")
    call("Page.enable")
    call("Page.reload", {"ignoreCache": True})
    works = {}

    def drain(sec):
        ws.settimeout(1)
        t0 = time.time()
        req_ids = []
        while time.time() - t0 < sec:
            try:
                m = json.loads(ws.recv())
                if m.get("method") == "Network.responseReceived":
                    u = m["params"]["response"]["url"]
                    if "aweme/v1/web/aweme/post/" in u:
                        req_ids.append(m["params"]["requestId"])
            except Exception:
                pass
        ws.settimeout(40)
        for rid in req_ids:
            r = call("Network.getResponseBody", {"requestId": rid}, wait=5)
            if r and "result" in r:
                body = r["result"].get("body", "")
                if len(body) < 100:
                    continue
                try:
                    d = json.loads(body)
                    for a in d.get("aweme_list", []):
                        vid = a.get("aweme_id")
                        if vid:
                            works.setdefault(str(vid), {
                                "id": str(vid),
                                "title": (a.get("desc", "") or "").split(" #")[0].strip(),
                                "create_time": a.get("create_time"),
                            })
                except Exception:
                    pass

    drain(10)
    print("init API:", len(works), flush=True)
    for k in range(args.rounds):
        call("Input.synthesizeScrollGesture", {
            "x": 700, "y": 500, "xDistance": 0, "yDistance": -2200,
            "gestureSourceType": "mouse", "speed": 8000,
        })
        time.sleep(0.7)
        drain(2)
        links = ev(
            "Array.from(document.querySelectorAll('a[href*=\"/video/\"]'))"
            ".map(a=>a.href.match(/\\/video\\/(\\d+)/)).filter(Boolean).map(m=>m[1])"
        )
        for vid in (links or []):
            works.setdefault(str(vid), {"id": str(vid), "title": ""})
        if k % 5 == 0:
            print("round", k, "works", len(works), "dom", len(links or []), flush=True)
        if args.expected and len(works) >= args.expected:
            break
    json.dump(list(works.values()), open(args.out_json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("TOTAL:", len(works), flush=True)
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{args.port}/json/close/{tab['id']}", timeout=5)
    except Exception:
        pass
    ws.close()


if __name__ == "__main__":
    main()
