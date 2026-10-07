"""SESTER — AST-taramasi ile bulunan test-disi fonksiyonlar (derinlesme dalgasi).

Bu dosya mevcut testleri DEGISTIRMEZ; yalnizca YENI eklenmistir. AST taramasi
(scanner: her moduldeki public def'lerin tests/ icinde bare-identifier olarak
gecip gecmedigine bakar) ile bulunan ve dogrudan-birim-testi olmayan
fonksiyonlari sabitler:

  sester/ledger.py         : canonical_line, seal (zincir-cekirdek saf-fonksiyonlari)
  sester/policy_signed.py  : signed_policy_json
  sester/adapters.py       : Ap2Mandate.authorize, AcpSession.authorize,
                             UcpCheckout.authorize (K4 protokol-cevirisi)
  sester/cli.py            : cmd_verify, cmd_receipt, cmd_history, cmd_bundle,
                             cmd_version, build_parser (dogrudan)
  sester/migrate_pg.py     : migrate (hash-koruyan tasiyici; dst duck-type Ledger)
  sester/demo_api.py       : /healthz, /ucp/issue, /agents.json, /weather (402)
  sester/facilitator_svc   : /metrics (Prometheus cikti + auth-guard)

Dis cagri YOK: her fonksiyon kendi mantigi ile test edilir (std-lib + fake
Ledger; FastAPI TestClient ASGI-transport ile ag-izolasyonlu).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os

import pytest

from sester.adapters import (
    AcpSession,
    AdapterError,
    Ap2Mandate,
    ChargeIntent,
    UcpCheckout,
)
from sester.ledger import GENESIS, canonical_line, seal
from sester.ledger import Ledger
from sester.policy_signed import signed_policy_json

S = "wave-secret"


# ================================================================== ledger

def test_canonical_line_exact_format():
    line = canonical_line(1.5, "charge_receipt", "ag-1", "h.io", 0.05,
                          '{"n":1}', GENESIS)
    assert line == "1.500000|charge_receipt|ag-1|h.io|0.050000|{\"n\":1}|" + GENESIS


def test_canonical_line_is_deterministic():
    a = canonical_line(2.0, "refund", "ag", "h", 1.25, "{}", "p0")
    b = canonical_line(2.0, "refund", "ag", "h", 1.25, "{}", "p0")
    assert a == b


def test_canonical_line_field_order_matters():
    """Sira-bagimsiz serilestirmeye karsi: host/agent yer degistirince cikti
    degisir (backend'ler arasi tutarlilik icin sabit-sira sart)."""
    a = canonical_line(1.0, "t", "ag", "host", 0.1, "{}", "p")
    b = canonical_line(1.0, "t", "host", "ag", 0.1, "{}", "p")
    assert a != b


def test_canonical_line_amount_is_six_decimals():
    line = canonical_line(0.0, "settlement", "a", "h", 0.1234567, "{}", "p")
    assert "|0.123457|" in line  # yuvarlama 6-decimal


def test_canonical_line_needs_no_db_or_secret():
    """Saf fonksiyon — SQLite/HMAC olmadan uretilir (backend-bagimsizlik)."""
    assert canonical_line(1, "t", "a", "h", 0, "{}", "p").count("|") == 6


def test_seal_is_sha256_hex_of_hmac_plus_canonical():
    secret = b"k"
    canon = "1.000000|t|a|h|0.000000|{}|" + GENESIS
    mac = hmac.new(secret, canon.encode(), hashlib.sha256).hexdigest()
    expect = hashlib.sha256((mac + canon).encode()).hexdigest()
    assert seal(secret, canon) == expect


def test_seal_is_deterministic():
    canon = "c"
    assert seal(b"s", canon) == seal(b"s", canon)


def test_seal_secret_dependence():
    """Farkli secret → farkli mühür (sahibi-yazabilir ilkesi)."""
    assert seal(b"s1", "c") != seal(b"s2", "c")


def test_seal_canonical_dependence():
    assert seal(b"s", "c1") != seal(b"s", "c2")


def test_seal_output_is_64_hexchars():
    out = seal(b"s", "c")
    assert len(out) == 64
    int(out, 16)  # hex olmali


# ============================================================ policy_signed

def test_signed_policy_json_is_sorted_and_compact():
    env = {"policy": {"wallet_policy": {"id": "b", "rules": [], "defaults": {}}},
           "zeta": 1, "Alpha": 2}
    out = signed_policy_json(env)
    assert out == json.dumps(env, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False)
    # anahtarlar sirali: Alpha < policy < zeta
    assert out.index("Alpha") < out.index("policy") < out.index("zeta")
    assert ", " not in out and ": " not in out


def test_signed_policy_json_preserves_non_ascii():
    """ensure_ascii=False → Türkçe/kiril harfleri kacis-dizisi DEGIL, birebir."""
    env = {"signer": "düzenleyici-İ"}
    out = signed_policy_json(env)
    assert "İ" in out
    assert "\\u" not in out


def test_signed_policy_json_roundtrips():
    env = {"policy_envelope_version": 1, "signed_at": 1.5, "signer": "did:x",
           "signature": "abc.def.ghi", "policy": {"wallet_policy": {"id": "p1"}}}
    assert json.loads(signed_policy_json(env)) == env


# ================================================================ adapters

def _ap2(**scope_and_raw):
    scope = scope_and_raw.pop("scope", None)
    raw = scope_and_raw.pop("raw", None)
    if scope is None:
        scope = {"resource_prefixes": ["/we"],
                 "per_request_max_minor": 1000, "currency": "USDC"}
    if raw is None:
        raw = {}
    # authorize() agent'i oldugu gibi gecirir (lowercase parse() asamasinda;
    # dogrudan kurulumda kucuk-harf veriyoruz)
    return Ap2Mandate(mandate_id="m-1", agent="ag-1", principal="user-1",
                      scope=scope, signature="sig-0123456789abcdef", raw=raw)


def test_ap2_authorize_in_scope_returns_intent():
    intent = _ap2().authorize("/weather", 500, "USDC")
    assert isinstance(intent, ChargeIntent)
    assert intent.agent == "ag-1"
    assert intent.resource == "/weather"
    assert intent.amount_minor == 500
    assert intent.currency == "USDC"
    assert intent.nonce == "m-1"           # replay-korumasi mandate'e bagli
    assert intent.protocol == "ap2"
    assert intent.principal == "user-1"


def test_ap2_authorize_resource_out_of_scope_raises():
    with pytest.raises(AdapterError, match="kapsam"):
        _ap2().authorize("/other", 500, "USDC")


def test_ap2_authorize_prefix_is_case_insensitive():
    assert _ap2().authorize("/WEATHER", 10, "USDC").resource == "/WEATHER"


def test_ap2_authorize_amount_over_per_request_max_raises():
    with pytest.raises(AdapterError, match="üst-sınır"):
        _ap2().authorize("/weather", 1001, "USDC")


def test_ap2_authorize_missing_per_request_max_refuses_any_amount():
    m = _ap2(scope={"resource_prefixes": ["/we"]})  # sinir yok → 0
    with pytest.raises(AdapterError):
        m.authorize("/weather", 1, "USDC")


def test_ap2_authorize_currency_mismatch_raises():
    with pytest.raises(AdapterError, match="para-birimi"):
        _ap2().authorize("/weather", 10, "EUR")


def test_ap2_authorize_window_expired_raises():
    m = _ap2(raw={"valid_to": 1000.0})
    with pytest.raises(AdapterError, match="süresi doldu"):
        m.authorize("/weather", 10, "USDC", now=2000.0)


def test_ap2_authorize_window_not_started_raises():
    m = _ap2(raw={"valid_from": 5000.0})
    with pytest.raises(AdapterError, match="henüz başlamadı"):
        m.authorize("/weather", 10, "USDC", now=1000.0)


def _acp(**kw):
    li = kw.pop("line_item", None)
    raw = kw.pop("raw", None)
    if li is None:
        li = {"resource": "/weather", "amount_minor": 250, "currency": "USDC"}
    if raw is None:
        raw = {}
    return AcpSession(session_id="s-1", buyer="buyer-1", line_item=li,
                      signature="", raw=raw)


def test_acp_authorize_matching_resource_returns_intent():
    intent = _acp().authorize("/weather")
    assert intent.agent == "buyer-1"
    assert intent.amount_minor == 250
    assert intent.currency == "USDC"
    assert intent.nonce == "s-1"
    assert intent.protocol == "acp"


def test_acp_authorize_resource_mismatch_raises():
    with pytest.raises(AdapterError, match="line_item kaynağı"):
        _acp().authorize("/other")


def test_acp_authorize_bad_amount_raises():
    with pytest.raises(AdapterError, match="amount_minor bozuk"):
        _acp(line_item={"resource": "/weather", "amount_minor": "x"}).authorize("/weather")


def test_acp_authorize_zero_amount_raises():
    with pytest.raises(AdapterError, match="pozitif olmalı"):
        _acp(line_item={"resource": "/weather", "amount_minor": 0}).authorize("/weather")


def test_acp_authorize_window_expired_raises():
    with pytest.raises(AdapterError, match="süresi doldu"):
        _acp(raw={"valid_to": 10.0}).authorize("/weather", now=100.0)


def _ucp(**kw):
    li = kw.pop("line_item", None)
    raw = kw.pop("raw", None)
    if li is None:
        li = {"resource": "/weather", "amount_minor": 750, "currency": "USDC"}
    if raw is None:
        raw = {}
    return UcpCheckout(intent_id="i-1", buyer="buyer-2", merchant="merchant-x",
                       line_item=li, signature="", raw=raw)


def test_ucp_authorize_matching_resource_returns_intent():
    intent = _ucp().authorize("/weather")
    assert intent.agent == "buyer-2"
    assert intent.amount_minor == 750
    assert intent.nonce == "i-1"
    assert intent.protocol == "ucp"


def test_ucp_authorize_resource_mismatch_raises():
    with pytest.raises(AdapterError, match="UCP line_item kaynağı"):
        _ucp().authorize("/other")


def test_ucp_authorize_bad_amount_raises():
    with pytest.raises(AdapterError, match="bozuk"):
        _ucp(line_item={"resource": "/weather"}).authorize("/weather")


def test_ucp_authorize_negative_amount_raises():
    with pytest.raises(AdapterError, match="pozitif olmalı"):
        _ucp(line_item={"resource": "/weather", "amount_minor": -5}).authorize("/weather")


# ==================================================================== cli

@pytest.fixture()
def cli_env(tmp_path, monkeypatch):
    """Ledger-secret env'i + dolu bir test-ledger'i."""
    monkeypatch.setenv("SESTER_LEDGER_SECRET", S)
    path = str(tmp_path / "wave.sqlite3")
    led = Ledger(path, secret=S)
    led.append("charge_receipt", "wave-agent", "/weather", 0.05,
               amount_minor=50_000, payload={"nonce": "w1"})
    led.close()
    return path


def test_cmd_version_prints_package_version(capsys):
    from sester.cli import cmd_version
    from sester import __version__
    rc = cmd_version(argparse.Namespace())
    assert rc == 0
    assert __version__ in capsys.readouterr().out


def test_build_parser_defaults_and_dispatch():
    from sester.cli import build_parser, cmd_receipt, cmd_version
    p = build_parser()
    assert p.parse_args(["version"]).func is cmd_version
    assert p.parse_args(["version"]).ledger is None
    a = p.parse_args(["receipt", "7", "--out", "x.json"])
    assert a.func is cmd_receipt
    assert a.seq == 7 and a.out == "x.json"
    assert a.currency == "USDC-sim"  # default


def test_build_parser_requires_subcommand():
    from sester.cli import build_parser
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_cmd_history_empty_ledger_is_reported(tmp_path, monkeypatch, capsys):
    from sester.cli import cmd_history
    monkeypatch.setenv("SESTER_LEDGER_SECRET", S)
    empty = str(tmp_path / "empty.sqlite3")
    Ledger(empty, secret=S).close()
    rc = cmd_history(argparse.Namespace(ledger=empty, agent=None, limit=25))
    assert rc == 0
    assert "boş ledger" in capsys.readouterr().out


def test_cmd_history_agent_filter_matches(cli_env, capsys):
    from sester.cli import cmd_history
    rc = cmd_history(argparse.Namespace(ledger=cli_env, agent="wave-agent",
                                        limit=10))
    out = capsys.readouterr().out
    assert rc == 0
    assert "charge_receipt" in out
    assert "zincir-sağlam: True" in out


def test_cmd_history_agent_filter_no_match_is_empty(cli_env, capsys):
    from sester.cli import cmd_history
    rc = cmd_history(argparse.Namespace(ledger=cli_env, agent="yok-agent",
                                        limit=10))
    assert rc == 0
    assert "boş ledger" in capsys.readouterr().out


def test_cmd_receipt_writes_out_file(cli_env, tmp_path, capsys):
    from sester.cli import cmd_receipt
    out_path = str(tmp_path / "wave-receipt.json")
    rc = cmd_receipt(argparse.Namespace(seq=1, out=out_path, currency="USDC-sim",
                                        ledger=cli_env, node_secret=None))
    assert rc == 0
    written = json.loads((tmp_path / "wave-receipt.json").read_text(encoding="utf-8"))
    assert written["seq"] == 1
    assert written["event_type"] == "charge_receipt"
    assert written["sub"] == "wave-agent"
    assert f"yazıldı: {out_path}" in capsys.readouterr().err


def test_cmd_receipt_missing_seq_is_red(cli_env, capsys):
    from sester.cli import cmd_receipt
    rc = cmd_receipt(argparse.Namespace(seq=999, out=None, currency="USDC-sim",
                                        ledger=cli_env, node_secret=None))
    assert rc == 1
    assert "bulunamadı" in capsys.readouterr().out


def test_cmd_receipt_non_charge_event_refused(tmp_path, monkeypatch, capsys):
    from sester.cli import cmd_receipt
    monkeypatch.setenv("SESTER_LEDGER_SECRET", S)
    path = str(tmp_path / "perm.sqlite3")
    led = Ledger(path, secret=S)
    seq = led.append("permission_decision", "a", "/x", 0.0,
                     payload={"d": 1})["seq"]
    led.close()
    rc = cmd_receipt(argparse.Namespace(seq=seq, out=None, currency="USDC-sim",
                                        ledger=path, node_secret=None))
    assert rc == 1
    assert "charge_receipt değil" in capsys.readouterr().out


def test_cmd_verify_accepts_receipt_without_node_secret(cli_env, tmp_path, capsys):
    """Alici-tarafi: node-secret YOKKEN bile proof dogrulanir (secret'siz)."""
    from sester.cli import cmd_receipt, cmd_verify
    out_path = str(tmp_path / "v.json")
    cmd_receipt(argparse.Namespace(seq=1, out=out_path, currency="USDC-sim",
                                   ledger=cli_env, node_secret=None))
    capsys.readouterr()
    rc = cmd_verify(argparse.Namespace(receipt=out_path, node_secret=None))
    out = capsys.readouterr().out
    assert rc == 0
    assert "KABUL" in out
    assert "secret'sız" in out


def test_cmd_verify_inline_json_arg(cli_env, tmp_path, capsys):
    from sester.cli import cmd_receipt, cmd_verify
    out_path = str(tmp_path / "v2.json")
    cmd_receipt(argparse.Namespace(seq=1, out=out_path, currency="USDC-sim",
                                   ledger=cli_env, node_secret=None))
    capsys.readouterr()
    text = (tmp_path / "v2.json").read_text(encoding="utf-8")
    rc = cmd_verify(argparse.Namespace(receipt=text, node_secret=None))
    assert rc == 0
    assert "KABUL" in capsys.readouterr().out


def test_cmd_verify_tampered_receipt_is_red(cli_env, tmp_path, capsys):
    from sester.cli import cmd_receipt, cmd_verify
    out_path = str(tmp_path / "v3.json")
    cmd_receipt(argparse.Namespace(seq=1, out=out_path, currency="USDC-sim",
                                   ledger=cli_env, node_secret=None))
    capsys.readouterr()
    r = json.loads((tmp_path / "v3.json").read_text(encoding="utf-8"))
    r["amount"] = "9.990000"
    (tmp_path / "v3.json").write_text(json.dumps(r), encoding="utf-8")
    rc = cmd_verify(argparse.Namespace(receipt=out_path, node_secret=None))
    assert rc == 1
    assert "RED" in capsys.readouterr().out


def test_cmd_verify_bozuk_json_is_red(tmp_path, capsys):
    from sester.cli import cmd_verify
    bad = tmp_path / "bozuk.json"
    bad.write_text("{bozuk", encoding="utf-8")
    rc = cmd_verify(argparse.Namespace(receipt=str(bad), node_secret=None))
    assert rc == 1
    assert "RED" in capsys.readouterr().out


def test_cmd_bundle_exports_and_selfverifies(cli_env, tmp_path, capsys):
    from sester.cli import cmd_bundle
    out_path = str(tmp_path / "wave-bundle.json")
    rc = cmd_bundle(argparse.Namespace(ledger=cli_env, agent=None, out=out_path))
    assert rc == 0
    lines = [l for l in (tmp_path / "wave-bundle.json").read_text(encoding="utf-8").splitlines()
             if l.strip().startswith("{")]
    b = json.loads(lines[0])
    assert b["event_count"] >= 1
    assert "pugio_bundle_version" in b


def test_cmd_bundle_agent_filter(cli_env, tmp_path, capsys):
    from sester.cli import cmd_bundle
    out_path = str(tmp_path / "wave-bundle2.json")
    rc = cmd_bundle(argparse.Namespace(ledger=cli_env, agent="wave-agent",
                                       out=out_path))
    assert rc == 0
    assert "kendi-doğrulama" in capsys.readouterr().err


# ============================================================= migrate_pg

@pytest.fixture()
def src_ledger(tmp_path):
    path = str(tmp_path / "src-wave.sqlite3")
    led = Ledger(path, secret=S)
    led.append("permission_decision", "ag-m", "/weather", 0.0,
               payload={"decision": "deny", "rule_id": "quota_exceeded"})
    led.append("charge_receipt", "ag-m", "/weather", 0.05,
               amount_minor=50_000, payload={"nonce": "m1"})
    led.append("charge_receipt", "ag-m", "/weather", 0.10,
               amount_minor=100_000, payload={"nonce": "m2"})
    led.claim_nonce("ag-m", "m1")
    led.claim_nonce("ag-m", "m2")
    led.close()
    return path


def test_migrate_copies_chain_verbatim(tmp_path, src_ledger):
    """dst bir PgLedger ile AYNI arayuze sahip Ledger (duck-type) — hash'ler
    aynen taşınır, hedef zincir SAĞLAM."""
    from sester.migrate_pg import migrate
    dst = Ledger(str(tmp_path / "dst-wave.sqlite3"), secret=S)
    try:
        rc = migrate(src_ledger, dst, secret=S)
        assert rc == 0
        src_events = Ledger(src_ledger, secret=S).export_events(None)
        assert [e["hash"] for e in src_events] == [
            e["hash"] for e in dst.export_events(None)]
        assert dst.verify_chain() is True
        assert len(dst.export_events(None)) == 3
    finally:
        dst.close()


def test_migrate_transfers_nonces(tmp_path, src_ledger):
    """Replay-penceresi taşınır: taşınan nonce bir daha claim edilemez."""
    from sester.migrate_pg import migrate
    dst = Ledger(str(tmp_path / "dst-n.sqlite3"), secret=S)
    try:
        assert migrate(src_ledger, dst, secret=S) == 0
        assert dst.nonce_count() == 2
        assert dst.claim_nonce("ag-m", "m1") is False
        assert dst.claim_nonce("ag-m", "m2") is False
        assert dst.claim_nonce("ag-m", "m3") is True
    finally:
        dst.close()


def test_migrate_is_idempotent(tmp_path, src_ledger):
    from sester.migrate_pg import migrate
    dst = Ledger(str(tmp_path / "dst-i.sqlite3"), secret=S)
    try:
        assert migrate(src_ledger, dst, secret=S) == 0
        assert migrate(src_ledger, dst, secret=S) == 0
        assert len(dst.export_events(None)) == 3
    finally:
        dst.close()


def test_migrate_dry_run_writes_nothing(tmp_path, src_ledger, capsys):
    from sester.migrate_pg import migrate
    dst = Ledger(str(tmp_path / "dst-d.sqlite3"), secret=S)
    try:
        rc = migrate(src_ledger, dst, secret=S, dry_run=True)
        assert rc == 0
        assert dst.export_events(None) == []
        assert dst.nonce_count() == 0
        assert "dry-run" in capsys.readouterr().out
    finally:
        dst.close()


def test_migrate_broken_source_is_refused(tmp_path, src_ledger, capsys):
    """Kaynak zinciri bozuksa taşıma başlatılmaz (fail-closed)."""
    from sester.migrate_pg import migrate
    led = Ledger(src_ledger, secret=S)
    led.conn.execute("UPDATE events SET amount=0.01 WHERE seq=2")
    led.conn.commit()
    led.close()
    dst = Ledger(str(tmp_path / "dst-b.sqlite3"), secret=S)
    try:
        rc = migrate(src_ledger, dst, secret=S)
        assert rc == 1
        assert "kaynak zincir bozuk" in capsys.readouterr().out
        assert dst.export_events(None) == []
    finally:
        dst.close()


# ============================================================= demo_api

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from sester import demo_api as demo  # noqa: E402


def test_demo_healthz_reports_chain_and_version():
    from sester import __version__
    r = TestClient(demo.app).get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["chain_valid"] in (True, False)


def test_demo_agents_json_discovery():
    body = TestClient(demo.app).get("/agents.json").json()
    assert len(body["agents"]) == 1
    a = body["agents"][0]
    assert a["id"] == "sester-demo"
    assert "USDC" in a["price"]
    assert a["quota"]


def test_demo_ucp_issue_returns_payment_header():
    r = TestClient(demo.app).get("/ucp/issue", params={"agent": "ag-ucp"})
    assert r.status_code == 200
    header = r.json()["payment_header"]
    assert header.startswith("UCP-Checkout ")


def test_demo_paid_weather_requires_payment():
    """/weather ücretli endpoint — ödemesiz istek 402 (x402 akışı)."""
    r = TestClient(demo.app).get("/weather")
    assert r.status_code == 402
    assert r.json()["error"] == "payment_required"


# ============================================================ facilitator

from sester.facilitator_svc import FacilitatorService, create_app  # noqa: E402

FAC_SECRET = "fac-wave-secret"


@pytest.fixture()
def fac_app(tmp_path):
    led = Ledger(str(tmp_path / "fac-wave.sqlite3"), secret=FAC_SECRET)
    svc = FacilitatorService(led, secret=FAC_SECRET, free_transactions=2)
    yield create_app(svc.ledger, secret=FAC_SECRET, auth_key="k-wave")
    led.close()


def test_facilitator_metrics_returns_prometheus_text(fac_app):
    r = TestClient(fac_app).get("/metrics",
                                headers={"X-Facilitator-Key": "k-wave"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "sester_facilitator_chain_valid" in r.text
    assert "# TYPE sester_facilitator" in r.text


def test_facilitator_metrics_requires_auth_key(fac_app):
    r = TestClient(fac_app).get("/metrics")
    assert r.status_code == 401
    r = TestClient(fac_app).get("/metrics",
                                headers={"X-Facilitator-Key": "yanlis"})
    assert r.status_code == 401


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
