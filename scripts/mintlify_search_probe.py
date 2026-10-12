"""Compare Mintlify's two search paths for the same queries.

1. The site search bar: POST https://leaves.mintlify.com/api/search/<subdomain> (what a visitor's browser sends;
   found in the docs site's main JS bundle, captured with scripts/rea_capture.sh).
2. The MCP search tool: POST https://<site>/mcp, tools/call <search tool>.

Usage: python scripts/mintlify_search_probe.py [subdomain] [mcp_url] [mcp_tool]
Defaults probe Mintlify's own docs. Sends a handful of requests, one second apart.
"""
import json
import sys
import time
import urllib.request

SUB = sys.argv[1] if len(sys.argv) > 1 else "mintlify"
MCP = sys.argv[2] if len(sys.argv) > 2 else "https://www.mintlify.com/docs/mcp"
TOOL = sys.argv[3] if len(sys.argv) > 3 else "search_mintlify"
QUERIES = ["mcp server", "mpc sever", "let claude read my documentation", "make docs available to ai coding tools"]
UA = {"User-Agent": "curl/8.5.0", "Content-Type": "application/json"}


def post(url, body, headers):
    req = urllib.request.Request(url, method="POST", data=json.dumps(body).encode(), headers=headers)
    t0 = time.monotonic()
    raw = urllib.request.urlopen(req, timeout=60).read().decode()
    return raw, time.monotonic() - t0


def search_bar(q):
    raw, dt = post(f"https://leaves.mintlify.com/api/search/{SUB}", {"query": q, "filters": {"language": "en"}}, UA)
    return [(r["page"], r["header"], round(r["score"], 2), len(r["content"])) for r in json.loads(raw)["results"]], dt


def mcp_search(q):
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": TOOL, "arguments": {"query": q}}}
    raw, dt = post(MCP, body, {**UA, "Accept": "application/json, text/event-stream"})
    blocks = json.loads(next(l[5:] for l in raw.splitlines() if l.startswith("data:")))["result"]["content"]
    field = lambda t, k: t.split(f"{k}: ")[1].split("\n")[0] if f"{k}: " in t else "?"
    return [(field(b["text"], "Page"), field(b["text"], "Title"), None, len(b["text"])) for b in blocks], dt


for q in QUERIES:
    for name, fn in (("search bar", search_bar), ("MCP search", mcp_search)):
        hits, dt = fn(q)
        print(f"\n## {name}: {q!r} -> {len(hits)} results in {dt:.2f}s")
        for page, header, score, size in hits[:5]:
            print(f"   {'' if score is None else score:>7} {page:<46} {header[:40]!r} ({size} chars)")
        time.sleep(1)
