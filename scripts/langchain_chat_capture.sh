#!/usr/bin/env bash
# Reproduce the Chat LangChain (docs.langchain.com) capture behind docs/langchain_chatbot/REPORT.md.
# Requires Node 22.19+, Python 3, curl, git and a Chromium/Chrome binary.
# Output goes to ./capture/langchain (git-ignored).
set -euo pipefail

URL="${1:-https://docs.langchain.com/oss/python/langchain/middleware/built-in}"
OUT="${OUT:-capture/langchain}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

# 1. REA: page structure, scripts and vendor fingerprints (Mintlify = Next.js + React).
#    The chat iframe is created lazily, so REA sees only the top frame plus the widget script.
OUT="$OUT/rea" bash "$(dirname "$0")/rea_capture.sh" "$URL" || true

# 2. The widget shell: Mintlify ships custom JS inside the RSC payload. Pull ChatLangChainEmbed.js out.
curl -sSL "$URL" -o "$OUT/page.html"
python3 -I - "$OUT/page.html" "$OUT/ChatLangChainEmbed.js" <<'EOF'
import json, re, sys
html = open(sys.argv[1]).read()
parts = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
rsc = "".join(json.loads('"' + p + '"') for p in parts)
ref = re.search(r'"filePath":"ChatLangChainEmbed\.js","__v":0,"content":"\$([0-9a-f]+)"', rsc).group(1)
start = re.search(r'\n' + ref + r':T[0-9a-f]+,', rsc).end()
end = rsc.index("ChatLangChainEmbed({});", start) + len("ChatLangChainEmbed({});\n})();")
open(sys.argv[2], "w").write(rsc[start:end])
EOF
grep -n "CHAT_LC_SET_CONTEXT" "$OUT/ChatLangChainEmbed.js"

# 3. The iframe app: find the ChatLangChainPage chunk and the submit code that appends the page URL.
EMBED=https://ui-patterns.langchain.com/react
ENTRY=$(curl -sS "$EMBED/" | grep -oE 'assets/index-[^"]+\.js' | head -1)
curl -sS "$EMBED/$ENTRY" -o "$OUT/embed-index.js"
CHUNK=$(grep -ohE 'assets/ChatLangChainPage-[^"]+\.js' "$OUT/embed-index.js" | head -1)
curl -sS "$EMBED/$CHUNK" -o "$OUT/ChatLangChainPage.js"
grep -oE '.{0,40}while viewing the following documentation page.{0,40}' "$OUT/ChatLangChainPage.js"

# 4. The retriever: list the tools of the docs MCP server.
curl -sS -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  https://docs.langchain.com/mcp -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | sed -n 's/^data: //p' > "$OUT/mcp_tools.json"
python3 -I -c 'import json,sys; print([t["name"] for t in json.load(open(sys.argv[1]))["result"]["tools"]])' "$OUT/mcp_tools.json"

# 5. The backend source (MIT): agent, middleware, tools, prompt.
[ -d "$OUT/chat-langchain" ] || git clone -q --depth 1 https://github.com/langchain-ai/chat-langchain.git "$OUT/chat-langchain"
git -C "$OUT/chat-langchain" log -1 --format='chat-langchain @ %h %ci'
