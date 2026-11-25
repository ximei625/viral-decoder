# -*- coding: utf-8 -*-
"""CDP helper: intercept a Douyin video page's real media (audio) stream URLs.

Why CDP instead of yt-dlp: Douyin serves DASH streams whose URLs are only visible
in the browser's real network requests (signed, expiring). yt-dlp cannot decrypt
modern Edge/Chrome cookie stores (v20 App-Bound Encryption), but CDP sees the
requests the logged-in browser already makes. Public videos work with a clean
profile (no login needed); private/age-gated ones need the logged-in browser.

Requires: pip install websocket-client
Requires a browser running with --remote-debugging-port=<PORT> (see launch_edge.sh).
"""
import json, time, urllib.request, urllib.parse, websocket

PORT = 9223


def set_port(p):
    global PORT
    PORT = int(p)


class CDPNet:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self.i = 0
        self.events = []

    def send(self, method, params=None):
        self.i += 1
        mid = self.i
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        return mid

    def call(self, method, params=None, wait=20):
        mid = self.send(method, params)
        t0 = time.time()
        while time.time() - t0 < wait:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                break
            if msg.get("id") == mid:
                return msg
        return None

    def eval(self, expr):
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        try:
            return r["result"]["result"].get("value")
        except Exception:
            return None

    def pump(self, seconds):
        """Collect CDP events for `seconds` seconds."""
        t0 = time.time()
        self.ws.settimeout(1)
        while time.time() - t0 < seconds:
            try:
                msg = json.loads(self.ws.recv())
                if "method" in msg:
                    self.events.append(msg)
            except Exception:
                pass
        self.ws.settimeout(30)

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def new_tab(url):
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/json/new?{urllib.parse.quote(url, safe=':/?=&')}",
        method="PUT",
    )
    return json.load(urllib.request.urlopen(req, timeout=10))


def close_tab(tab_id):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/close/{tab_id}", timeout=5)
    except Exception:
        pass


def get_video_url(vid, wait=12):
    """Return candidate media stream URLs for a Douyin video id."""
    tab = new_tab(f"https://www.douyin.com/video/{vid}")
    try:
        c = CDPNet(tab["webSocketDebuggerUrl"])
        c.call("Network.enable")
        c.call("Page.enable")
        c.call("Page.reload", {"ignoreCache": True})
        c.pump(wait)
        candidates = []
        for e in c.events:
            if e.get("method") == "Network.requestWillBeSent":
                u = e["params"]["request"]["url"]
                if any(k in u for k in ("douyinvod.com", "video/tos", "mime_type=video", ".mp4", "media-audio", "mp4a")):
                    candidates.append(u)
        cs = c.eval("(function(){var v=document.querySelector('video');return v?(v.currentSrc||''):''})()")
        if cs and "blob:" not in cs:
            candidates.insert(0, cs)
        c.close()
    finally:
        close_tab(tab["id"])
    return list(dict.fromkeys(candidates))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        set_port(sys.argv[2])
    vid = sys.argv[1] if len(sys.argv) > 1 else "7649390417158343955"
    cands = get_video_url(vid, 15)
    print("candidates:", len(cands))
    for u in cands[:6]:
        print(u[:250])
