# Run from a checkout of langchain-ai/chat-langchain with managed-deepagents==0.3.0 and deepagents installed.
"""Compile Chat LangChain's agent from its own code and record exactly what the model receives."""
import json, os, sys
os.environ.update({"USE_LOCAL_PROMPTS": "true", "LANGSMITH_TRACING": "false", "OPENAI_API_KEY": "sk-dummy",
                   "ANTHROPIC_API_KEY": "dummy", "GOOGLE_API_KEY": "dummy", "PYLON_API_KEY": "dummy", "PYLON_KB_ID": "dummy"})
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.utils.function_calling import convert_to_openai_tool
import langchain.chat_models as lcm

SEEN = {}
class Recorder(GenericFakeChatModel):
    """Stands in for every model: records tools + messages, answers immediately."""
    def bind_tools(self, tools, **kw):
        SEEN["tools"] = [convert_to_openai_tool(t) for t in tools]; return self
    def with_structured_output(self, schema, **kw):   # guardrail classifier -> always ALLOWED
        return RunnableLambda(lambda _: {"decision": "ALLOWED", "explanation": "inspection"})
    def _generate(self, messages, *a, **kw):
        SEEN["messages"] = [(m.type, m.content if isinstance(m.content, str) else json.dumps(m.content)) for m in messages]
        return super()._generate(messages, *a, **kw)

def fake_init(*a, **kw): return Recorder(messages=iter([AIMessage(content="done")] * 50))
lcm.init_chat_model = fake_init
import langchain.chat_models.base as lcmb; lcmb.init_chat_model = fake_init
import deepagents.graph as dg
if hasattr(dg, "init_chat_model"): dg.init_chat_model = fake_init

import agent as clc_agent                              # their agent.py
from connectors.mcp import connector                   # their MCP connector (live docs.langchain.com/mcp)
from managed_deepagents.runtime import compile_managed_agent

compiled = compile_managed_agent(clc_agent.agent, system_prompt=open("instructions.md").read(), connectors=[connector])
print("COMPILED:", type(compiled).__name__)
print("GRAPH NODES:", [n for n in compiled.get_graph().nodes])
import asyncio
out = asyncio.run(compiled.ainvoke({"messages": [{"role": "user", "content": "How do I add middleware?"}]}))
tools = SEEN.get("tools", [])
print(f"\nTOOLS SENT TO THE MODEL ({len(tools)}):")
for t in tools:
    f = t["function"]; props = f.get("parameters", {}).get("properties", {})
    print(f"  - {f['name']}({', '.join(props)})")
json.dump({"tools": tools, "messages": SEEN.get("messages")}, open("captured_request.json", "w"), indent=1)
sysmsg = next((c for r, c in SEEN.get("messages", []) if r == "system"), "")
print(f"\nSYSTEM PROMPT: {len(sysmsg)} chars; starts: {sysmsg[:80]!r}")
print("instructions.md chars:", len(open('instructions.md').read()))
