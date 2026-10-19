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
# CI checkout'unda .venv YOKTUR (.gitignore'lu) — sabit-yol FileNotFoundError
# verip 13 MCP testini DÜŞÜRÜYORDU (CI #101+, 2026-10-03'te teşhis-edildi).
# Bu yüzden önce yerel dev-venv'i dene; yoksa testi zaten koşturan
# yorumlayıcıya dön — CI'da `pip install -e .[dev]` sester'i sys.executable'a
# kurar. Suit'in diğer tüm subprocess-testleri aynı kalıbı kullanır
# (sys.executable); bu-tek-dosya ondan-sapmıştı.
_VENV_PY = ROOT / ".venv" / "bin" / "python"
PY = str(_VENV_PY) if _VENV_PY.is_file() else sys.executable
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
    proc = subprocess.run([PY, str(SERVER)], input="\n".join(reqs) + "\n",
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
# ------------------------------------------------------- G22-dagitim-notu

def test_readme_documents_mcp_packaging_limit():
    """G22-pini: README mcp/server.py'i tanitiyorsa, pip-ile-gelen kullanicinin
    onu BULAMAYACAGINI da soylemelidir — aksi halde wheel'de olmayan bir
    giris-noktasi oldugu izlenimi olur ( dagitim-grayhole / over-imply).
    Hatch sdist only-include bilinçle mcp/'yi disarda birakir ( divergence-
    truth karari); README bu gercegi tasiyor olmali."""
    readme = (Path(__file__).resolve().parents[1]
              / "README.md").read_text(encoding="utf-8")
    assert "mcp/server.py" in readme, "README mcp sunucu-yolunu vermiyor"
    assert "Packaging note" in readme, (
        "README MCP dagitim-sinirini belirtmiyor ( over-imply-riski)")


# ------------------------------------------------------- G23-ascii-saflik

def test_head_commit_message_is_ascii_safe():
    """G23-pini: commit-mesajlari ASCII-saf olmalidir ( makine-metin-uyari-
    kurali). Bu oturumda Turkce-karakterler iki-kez mesaja sizdi ve amend
    ile geri alinmak zorunda kaldi. Pin, HEAD'in mesajini olcer; yeni bir
    Turkce-karakterli commit mesaji bu testi DUSURUR - sessiz-gecmesin."""
    import subprocess
    msg = subprocess.run(
        ["git", "log", "-1", "--format=%B"], capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parents[1]), check=True).stdout
    non_ascii = [c for c in msg if ord(c) > 127]
    assert not non_ascii, (
        "HEAD commit-mesajinda ASCII-disi-karakterler var: %r" % non_ascii)


# -------------------------------------------------- G27-README-test-sayisi

def test_readme_test_count_is_not_stale():
    """G27-pini: README'nin test-sayisi-iddiasi gercek-collect'e-esit.
    G24-fleksa-olgusu-ayni-sinifta: yeni-test-eklenince-README-sayisi-stale-
    kaldi. Pin, iddia-ile-gercek-arasindaki-farki-olcer; yeni-test-bu-testi
    DUSURUR - sessiz-gecmesin."""
    import re as _re
    import subprocess as _sub
    import sys as _sys
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    m = _re.search(r"([\d.,]+)\s*tests\s*\((\d+)\s*passed", readme)
    assert m, "README test-sayisi-satiri-bulunamadi"
    # binlik-ayraci ( 2.957 / 2,957) - kaldir
    claimed_total = int(m.group(1).replace(".", "").replace(",", ""))
    claimed_passed = int(m.group(2))
    res = _sub.run(
        [_sys.executable, "-m", "pytest", "tests/", "--collect-only"],
        capture_output=True, text=True, cwd=str(root), timeout=600)
    assert res.returncode == 0, res.stderr[-400:]
    num = None
    for ln in res.stdout.splitlines():
        mm = _re.search(r"(\d+)\s*tests?\s*collected", ln)
        if mm:
            num = int(mm.group(1))
    assert num is not None, "collect-total-ayristirilamadi: %r" % res.stdout[-300:]
    assert num == claimed_total, (
        "README-stale-test-sayisi: iddia=%d gercek=%d" % (claimed_total, num))
    assert claimed_passed <= claimed_total, (
        "passed>total-imkansiz: %d>%d" % (claimed_passed, claimed_total))
