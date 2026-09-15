#!/usr/bin/env python3
"""Render several UI states of a local page and save a PNG of each.

Why this exists: a screenshot of the landing screen does not prove a brand retrofit
landed. Inner screens routinely carry their own hardcoded backgrounds that no token
override reaches. This drives a headless Chromium over CDP, clicks through states via
JS, and captures each one so you can look at the pixels.

Usage:
    python shot_states.py steps.json [--out DIR] [--size 1440,900]
    python shot_states.py '<json array inline>'

steps.json is an array of steps, applied in order. Each step may carry:
    url   navigate here (file:/// is fine), then wait
    js    evaluate this expression in the page, then wait
    wait  seconds to settle (default 3 after url, 1.5 after js)
    shot  filename to save the screenshot as

    [
      {"url": "file:///C:/repo/index.html", "wait": 4, "shot": "menu.png"},
      {"js": "document.querySelector('[data-id=\"1\"]').click()", "shot": "inner.png"},
      {"js": "document.querySelectorAll('.option')[0].click()", "shot": "feedback.png"}
    ]

Then read each PNG with vision_analyze. Requires `websockets` (pip install websockets).
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

BROWSER_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "msedge",
]


def find_browser() -> str:
    for cand in BROWSER_CANDIDATES:
        if os.path.sep in cand or (os.name == "nt" and ":" in cand):
            if os.path.exists(cand):
                return cand
        else:
            found = shutil.which(cand)
            if found:
                return found
    sys.exit("no Chromium-family browser found; edit BROWSER_CANDIDATES")


def devtools(port: int, path: str, tries: int = 60):
    url = f"http://127.0.0.1:{port}{path}"
    for _ in range(tries):
        try:
            return json.loads(urllib.request.urlopen(url, timeout=2).read())
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"devtools endpoint never came up on port {port}")


async def run(ws_url: str, steps: list[dict], out_dir: str) -> None:
    import websockets  # imported late so --help works without it

    async with websockets.connect(ws_url, max_size=200_000_000) as sock:
        counter = 0

        async def cmd(method: str, **params):
            nonlocal counter
            counter += 1
            await sock.send(json.dumps({"id": counter, "method": method, "params": params}))
            while True:
                msg = json.loads(await sock.recv())
                if msg.get("id") == counter:
                    if "error" in msg:
                        raise RuntimeError(f"{method}: {msg['error']}")
                    return msg.get("result", {})

        await cmd("Page.enable")
        await cmd("Runtime.enable")

        for step in steps:
            if "url" in step:
                await cmd("Page.navigate", url=step["url"])
                await asyncio.sleep(step.get("wait", 3))
            if "js" in step:
                res = await cmd(
                    "Runtime.evaluate",
                    expression=step["js"],
                    awaitPromise=True,
                    returnByValue=True,
                )
                if res.get("exceptionDetails"):
                    print(f"  ! js threw: {res['exceptionDetails'].get('text')}", file=sys.stderr)
                await asyncio.sleep(step.get("wait", 1.5))
            if "shot" in step:
                shot = await cmd("Page.captureScreenshot", format="png")
                path = os.path.join(out_dir, step["shot"])
                with open(path, "wb") as fh:
                    fh.write(base64.b64decode(shot["data"]))
                print(f"saved {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("steps", help="path to a JSON file, or an inline JSON array")
    ap.add_argument("--out", default="_shots", help="output directory (default: _shots)")
    ap.add_argument("--size", default="1440,900", help="window size WxH (default: 1440,900)")
    ap.add_argument("--port", type=int, default=9333, help="CDP port (default: 9333)")
    args = ap.parse_args()

    raw = args.steps
    if os.path.exists(raw):
        with open(raw, encoding="utf-8") as fh:
            raw = fh.read()
    steps = json.loads(raw)

    os.makedirs(args.out, exist_ok=True)
    profile = os.path.join(tempfile.gettempdir(), f"shot_states_{os.getpid()}")
    shutil.rmtree(profile, ignore_errors=True)

    browser = find_browser()
    proc = subprocess.Popen(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--remote-debugging-port={args.port}",
            f"--user-data-dir={profile}",
            f"--window-size={args.size}",
            "--allow-file-access-from-files",  # local pages loading sibling assets
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        tabs = devtools(args.port, "/json/list")
        page = next(t for t in tabs if t["type"] == "page")
        asyncio.run(run(page["webSocketDebuggerUrl"], steps, args.out))
    finally:
        proc.terminate()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    main()
