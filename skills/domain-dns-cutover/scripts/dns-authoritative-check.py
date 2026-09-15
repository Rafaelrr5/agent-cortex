#!/usr/bin/env python3
"""Check a domain's A records at its AUTHORITATIVE nameservers, not at a cache.

Usage:
    python dns-authoritative-check.py example.com [expected-ip]
    python dns-authoritative-check.py example.com 203.0.113.10

Why this exists (two traps it avoids):

1. Windows `nslookup` writes localised output in cp850. Calling
   subprocess.run(..., text=True) raises UnicodeDecodeError, stdout is thrown
   away, and a naive parser then reports "no records" for a domain that is fine.
   We capture bytes and decode cp850 with errors='replace'.

2. The DNS server's OWN address appears in the output header, before any answer.
   Regexing the whole output for an IP therefore yields a confident false
   positive. We slice from the "Name:"/"Nome:" marker before extracting.

Exit code is 0 when every checked name resolves (and matches expected-ip when
given), 1 otherwise -- so it can gate a certbot run.
"""
import re
import subprocess
import sys

MARKERS = ("nome:", "name:")


def _decode(raw: bytes) -> str:
    for enc in ("cp850", "cp1252", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def query_a(host: str, server: str, timeout: int = 30):
    """Return (status, ips) for an A lookup of `host` against `server`."""
    cmd = ["nslookup", "-type=A", host, server]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "TIMEOUT", []
    out = _decode(proc.stdout) + _decode(proc.stderr)
    low = out.lower()

    idx = max(low.find(m) for m in MARKERS)
    tail = out[idx:] if idx > 0 else ""
    ips = re.findall(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", tail)

    if ips:
        return "OK", ips
    if "non-existent" in low or "inexistente" in low:
        return "NXDOMAIN", []
    if idx > 0:
        return "NODATA", []          # name exists, no A record published
    if "refused" in low or "recusad" in low:
        return "REFUSED", []
    return "NO_ANSWER", []


def authoritative_ns(domain: str):
    """Discover the domain's NS names; fall back to public resolvers."""
    try:
        proc = subprocess.run(
            ["nslookup", "-type=NS", domain, "8.8.8.8"],
            capture_output=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return []
    out = _decode(proc.stdout)
    ns = re.findall(r"nameserver\s*=\s*([A-Za-z0-9.\-]+)", out)
    return sorted({n.rstrip(".") for n in ns})


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    domain = sys.argv[1].strip().lower()
    expected = sys.argv[2].strip() if len(sys.argv) > 2 else None

    ns_list = authoritative_ns(domain)
    print(f"  authoritative NS: {', '.join(ns_list) if ns_list else '(none found)'}")

    servers = ns_list + ["8.8.8.8", "1.1.1.1"]
    names = [domain, f"www.{domain}"]

    print(f"\n  {'name':<34} {'server':<22} result")
    print("  " + "-" * 74)

    published = {n: False for n in names}
    for name in names:
        for srv in servers:
            status, ips = query_a(name, srv)
            detail = ", ".join(ips) if ips else status
            flag = ""
            if expected and ips:
                flag = "  <== MATCH" if expected in ips else f"  <== MISMATCH (want {expected})"
            authoritative = srv in ns_list
            if status == "OK" and authoritative and (not expected or expected in ips):
                published[name] = True
            print(f"  {name:<34} {srv:<22} {detail}{flag}")
        print()

    ok = all(published.values())
    if ok:
        print("  VERDICT: published at the authoritative servers.")
        print("  Safe to run: certbot --nginx -d %s -d www.%s" % (domain, domain))
    else:
        missing = [n for n, v in published.items() if not v]
        print("  VERDICT: NOT yet published at the authoritative servers.")
        print("  Missing: " + ", ".join(missing))
        print("  If the registrar panel already shows the records, this is a")
        print("  transition/propagation window -- do NOT re-edit the zone.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
