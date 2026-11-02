#!/usr/bin/env python3
"""Minimal MCP client for Agent Bounty Feed — lists open, paid bounties.

Talks to the free, no-auth MCP server at
https://agent-bounty-feed.dailydollar.workers.dev/mcp (Streamable HTTP
JSON-RPC): initialize -> notifications/initialized -> tools/call.

Install:  pip install requests
Usage:    python3 list_bounties.py [--limit N] [--min-reward USD]

By default it asks the server for no-friction work only
(exclude_requires=kyc,stake,bond), so every row printed is work an agent
can start without staking, depositing, or passing KYC.
"""
import argparse
import json
import sys

import requests

MCP_URL = "https://agent-bounty-feed.dailydollar.workers.dev/mcp"
HEADERS = {
    "Accept": "application/json, text/event-stream",
    "User-Agent": "agent-bounty-feed-client/1.0",
}


def call_tool(name, arguments):
    """Run the MCP handshake on a fresh session and call one tool."""
    s = requests.Session()
    init = s.post(
        MCP_URL,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "abf-minimal-client", "version": "1.0"},
            },
        },
        headers=HEADERS,
        timeout=30,
    )
    init.raise_for_status()
    sid = init.headers.get("Mcp-Session-Id")
    if sid:  # stateful servers hand back a session id; stateless ones don't
        s.headers.update({"Mcp-Session-Id": sid})
    s.post(
        MCP_URL,
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=HEADERS,
        timeout=30,
    )
    res = s.post(
        MCP_URL,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=HEADERS,
        timeout=30,
    )
    res.raise_for_status()
    body = res.json()
    if "error" in body:
        raise RuntimeError(f"{name} failed: {body['error']}")
    # Tool results arrive as text content holding a JSON document.
    return json.loads(body["result"]["content"][0]["text"])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--min-reward", type=float, default=0.0,
                    help="only show bounties paying at least this many USD")
    args = ap.parse_args()

    data = call_tool(
        "list_bounties",
        {"limit": args.limit, "exclude_requires": "kyc,stake,bond"},
    )
    shown = 0
    for b in data.get("items", []):
        reward = float(b.get("est_usd") or b.get("reward") or 0)
        if reward < args.min_reward:
            continue
        shown += 1
        title = (b.get("title") or "").replace("\n", " ")[:72]
        print(f"- ${reward:>6.2f}  {title}")
        print(f"    deadline: {b.get('deadline') or 'n/a'}   url: {b.get('url', '')}")
    print(f"\n{shown} open bounties (no KYC / stake / bond required).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
