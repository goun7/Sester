"""MCP server testleri — Model Context Protocol 2025-06-18 over stdio.

JSON-RPC el sıkışması + 4 aracı (pay/verify_receipt/balance/history) uçtan-uca
subprocess üzerinden çalıştırır. Smithery/Arcade yayın-yüzeyini sabitler."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp" / "server.py"
VENV_PY = str(ROOT / ".venv" / "bin" / "python")
PROTOCOL_VERSION = "2025-06-18"


def _rpc(tmp_db: str, secret="mcp-secret", node_secret="node-secret",
         extra_env=None, lines=None):
    """Server'ı stdio üzerinden besle; yanıt satırlarını dict listesi dön."""
    env = dict(os.environ)
    env.update({
        "SESTER_MCP_DB": str(tmp_db),
        "SESTER_MCP_SECRET": secret,
        "SESTER_MCP_NODE_SECRET": node_secret,
        "SESTER_MCP_QUOTA": "5.00",
    })
    env.pop("SESTER_MCP_ENDPOINT", None)
    if extra_env:
        env.update(extra_env)
    reqs = list(lines or [])
    proc = subprocess.run([VENV_PY, str(SERVER)], input="\n".join(reqs) + "\n",
                          capture_output=True, text=True, env=env, timeout=60,
                          cwd=str(ROOT))
    out = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            out.append(json.loads(line))
    return proc, out


def _pay_line():
    return ('{"jsonrpc":"2.0","id":3,"method":"tools/call",'
            '"params":{"name":"pay","arguments":'
            '{"agent":"mcp-agent","resource":"/weather","amount":0.05}}}')


def test_initialize_negotiates_2025_06_18(tmp_path):
    proc, out = _rpc(tmp_path / "i.sqlite3", lines=[
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":'
        '{"protocolVersion":"2025-06-18","capabilities":{},'
        '"clientInfo":{"name":"t","version":"0"}}}',
    ])
    assert proc.returncode == 0, proc.stderr
    assert len(out) == 1
    r = out[0]
    assert r["id"] == 1
    assert r["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert "tools" in r["result"]["capabilities"]
    si = r["result"]["serverInfo"]
    assert si["name"] == "sester"
    assert si["version"] != "0"  # sester import-edilebilir (path çözümü)


def test_notifications_initialized_no_response(tmp_path):
    proc, out = _rpc(tmp_path / "n.sqlite3", lines=[
        '{"jsonrpc":"2.0","method":"notifications/initialized"}',
    ])
    assert proc.returncode == 0
    assert out == []  # notification'a yanıt YOK (spec)


def test_tools_list_contract(tmp_path):
    proc, out = _rpc(tmp_path / "t.sqlite3", lines=[
        '{"jsonrpc":"2.0","id":2,"method":"tools/list"}',
    ])
    assert proc.returncode == 0, proc.stderr
    tools = out[0]["result"]["tools"]
    names = {t["name"] for t in tools}
    assert names == {"pay", "verify_receipt", "balance", "history"}
    for t in tools:
        assert t["description"]
        assert t["inputSchema"]["type"] == "object"
        # JSON-schema disiplini: ek-alanreddi (katı sözleşme)
        assert t["inputSchema"]["additionalProperties"] is False


def test_pay_returns_cosigned_receipt(tmp_path):
    proc, out = _rpc(tmp_path / "p.sqlite3", lines=[_pay_line()])
    assert proc.returncode == 0, proc.stderr
    res = out[0]["result"]
    assert res["isError"] is False
    r = json.loads(res["content"][0]["text"].splitlines()[0])
    assert r["receipt_version"] == 1
    assert r["sub"] == "mcp-agent"
    assert r["amount"] == "0.050000"
    assert r["node_cosign"]  # cosigned
    assert r["iss"] == "sester:mcp-node"


def test_pay_then_verify_receipt_roundtrip(tmp_path):
    """pay çıktısını verify_receipt'a besle — boru-hattı taklit (iki süreç)."""
    _, out = _rpc(tmp_path / "v.sqlite3", lines=[_pay_line()])
    pay_text = out[0]["result"]["content"][0]["text"].splitlines()[0]
    _, out2 = _rpc(tmp_path / "v.sqlite3", lines=[
        _pay_line(),
        '{"jsonrpc":"2.0","id":7,"method":"tools/call","params":'
        '{"name":"verify_receipt","arguments":{"receipt":'
        + json.dumps(pay_text) + '}}}',
    ])
    assert out2[1]["result"]["isError"] is False
    assert "KABUL" in out2[1]["result"]["content"][0]["text"]


def test_verify_receipt_rejects_bozuk(tmp_path):
    proc, out = _rpc(tmp_path / "b.sqlite3", lines=[
        '{"jsonrpc":"2.0","id":8,"method":"tools/call","params":'
        '{"name":"verify_receipt","arguments":{"receipt":"BOZUK"}}}',
    ])
    assert proc.returncode == 0
    res = out[0]["result"]
    assert res["isError"] is True
    assert "RED" in res["content"][0]["text"]


def test_balance_and_history(tmp_path):
    proc, out = _rpc(tmp_path / "bh.sqlite3", lines=[
        _pay_line(),
        '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":'
        '{"name":"balance","arguments":{"agent":"mcp-agent"}}}',
        '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":'
        '{"name":"history","arguments":{"limit":5}}}',
    ])
    assert proc.returncode == 0, proc.stderr
    bal = json.loads(out[1]["result"]["content"][0]["text"])
    assert bal["agent"] == "mcp-agent"
    assert bal["spent_today"] == 0.05
    assert bal["daily_quota"] == 5.00
    hist = json.loads(out[2]["result"]["content"][0]["text"])
    assert hist["count"] == 1
    assert hist["events"][0]["event_type"] == "charge_receipt"


def test_quota_exceeded_fail_closed(tmp_path):
    proc, out = _rpc(tmp_path / "q.sqlite3",
                     extra_env={"SESTER_MCP_QUOTA": "0.01"},
                     lines=[_pay_line()])
    res = out[0]["result"]
    assert res["isError"] is True
    assert "quota_exceeded" in res["content"][0]["text"]


def test_pay_requires_agent_and_amount(tmp_path):
    proc, out = _rpc(tmp_path / "e.sqlite3", lines=[
        '{"jsonrpc":"2.0","id":9,"method":"tools/call","params":'
        '{"name":"pay","arguments":{"agent":"","amount":0.05}}}',
        '{"jsonrpc":"2.0","id":10,"method":"tools/call","params":'
        '{"name":"pay","arguments":{"agent":"a","amount":-1}}}',
    ])
    assert out[0]["result"]["isError"] is True
    assert out[1]["result"]["isError"] is True


def test_unknown_method_returns_jsonrpc_error(tmp_path):
    proc, out = _rpc(tmp_path / "u.sqlite3", lines=[
        '{"jsonrpc":"2.0","id":11,"method":"tools/nope"}',
    ])
    assert "error" in out[0]
    assert out[0]["error"]["code"] == -32601


def test_unknown_tool_name(tmp_path):
    proc, out = _rpc(tmp_path / "ut.sqlite3", lines=[
        '{"jsonrpc":"2.0","id":12,"method":"tools/call","params":'
        '{"name":"steal_keys","arguments":{}}}',
    ])
    assert out[0]["error"]["code"] == -32602


def test_ping_answers(tmp_path):
    proc, out = _rpc(tmp_path / "pg.sqlite3", lines=[
        '{"jsonrpc":"2.0","id":13,"method":"ping"}',
    ])
    assert out[0]["result"] == {}


def test_missing_secret_warns_but_runs(tmp_path):
    proc, out = _rpc(tmp_path / "ms.sqlite3", secret="", lines=[
        '{"jsonrpc":"2.0","id":14,"method":"tools/call","params":'
        '{"name":"balance","arguments":{"agent":"a"}}}',
    ])
    assert "SESTER-MCP UYARI" in proc.stderr  # gürültülü-uyarı, sessiz-değil
    assert out[0]["result"]["isError"] is False
