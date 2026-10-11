"""sester.demo_api._cli dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — sys.argv monkeypatch + stdout capture (network YOK).
Demo-CLI: --mac (HMAC pugio0 basligi) ve --evm (Sester-EVM imzali baslik)
üretir; bilinmeyen-cagri -> docstring.
"""
import base64
import contextlib
import hashlib
import hmac
import io
import json

import pytest

from sester import demo_api as D


@pytest.fixture
def run_cli(monkeypatch):
    """sys.argv + stdout capture — Kural-4: GERCEK process YOK."""
    def _run(*argv):
        monkeypatch.setattr("sys.argv", ["demo-api", *argv])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = D._cli()
        return rc, buf.getvalue()
    return _run


# -- --mac =======================================================================================

def test_mac_returns_0(run_cli):
    assert run_cli("--mac", "a:n:0.05", "/weather")[0] == 0


def test_mac_first_line_format(run_cli):
    rc, out = run_cli("--mac", "agent1:nonce1:0.05", "/weather")
    line = out.splitlines()[0]
    """ORTAM-ANATOMI: 'pugio0 <agent>:<nonce>:<amount>:<hmac-sha256-hex>'."""
    assert line.startswith("pugio0 ")
    parts = line[len("pugio0 "):].split(":")
    assert len(parts) == 4
    assert parts[0] == "agent1" and parts[1] == "nonce1" and parts[2] == "0.05"
    int(parts[3], 16)
    assert len(parts[3]) == 64


def test_mac_formula(run_cli):
    """ORTAM: hmac.new(SECRET, '{agent}|{nonce}|{amount}|{path}', sha256)."""
    rc, out = run_cli("--mac", "agent1:nonce1:0.05", "/weather")
    expected = hmac.new(D.SECRET.encode(),
                        b"agent1|nonce1|0.05|/weather", hashlib.sha256).hexdigest()
    assert expected in out


@pytest.mark.parametrize("agent,nonce,amount,path", [
    ("a", "n", "0.05", "/weather"),
    ("f1-telemetri", "n1", "0.05", "/weather"),
    ("görev-1", "nonce-ü", "0,25", "/yol/ü"),
    ("emoji", "😀", "1.00", "/"),
])
def test_mac_formula_variants(run_cli, agent, nonce, amount, path):
    rc, out = run_cli("--mac", f"{agent}:{nonce}:{amount}", path)
    expected = hmac.new(D.SECRET.encode(),
                        f"{agent}|{nonce}|{amount}|{path}".encode(),
                        hashlib.sha256).hexdigest()
    assert expected in out


def test_mac_default_path_is_weather(run_cli):
    """ORTAM: path argümani YOKSA '/weather' (sys.argv[3] YOKSA default)."""
    rc, out = run_cli("--mac", "a:n:0.05")
    expected = hmac.new(D.SECRET.encode(), b"a|n|0.05|/weather", hashlib.sha256).hexdigest()
    assert expected in out


def test_mac_secret_from_env(run_cli, monkeypatch):
    """ORTAM: SECRET module-level — demo_api.SECRET env-override (SESTER_DEMO_SECRET)."""
    monkeypatch.setattr(D, "SECRET", "custom-secret")
    rc, out = run_cli("--mac", "a:n:0.05", "/x")
    expected = hmac.new(b"custom-secret", b"a|n|0.05|/x", hashlib.sha256).hexdigest()
    assert expected in out


def test_mac_includes_curl_template(run_cli):
    rc, out = run_cli("--mac", "a:n:0.05", "/weather")
    assert "curl" in out
    assert "X-Sester-Agent: a" in out
    assert "X-Payment: pugio0 a:n:0.05:" in out
    assert "http://127.0.0.1:8402/weather" in out


def test_mac_curl_line_count(run_cli):
    rc, out = run_cli("--mac", "a:n:0.05", "/w")
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 4


@pytest.mark.parametrize("fields", ["a:n", "a", "a:n:0.05:x", "a:n:0.05:x:y", ""])
def test_mac_wrong_field_count_returns_2(run_cli, fields):
    """ORTAM-OGRENDI: len(fields)!=3 -> print(kullanim) + rc 2 (fail-loud)."""
    rc, out = run_cli("--mac", fields, "/w")
    assert rc == 2
    assert "kullanım" in out
    assert "--mac" in out


@pytest.mark.parametrize("fields", ["a:n", "a:n:0.05:x"])
def test_mac_usage_message_content(run_cli, fields):
    rc, out = run_cli("--mac", fields)
    assert out.strip() == "kullanım: --mac <agent>:<nonce>:<amount> [path]"


def test_mac_fields_split_on_colon(run_cli):
    """ORTAM: split(':') — baska-ayrac ile 1-field -> rc 2."""
    rc, out = run_cli("--mac", "a-n-0.05", "/w")
    assert rc == 2


def test_mac_amount_verbatim(run_cli):
    """ORTAM: amount string HAM gecer (float-coerce YOK)."""
    rc, out = run_cli("--mac", "a:n:0,5", "/w")
    assert "0,5" in out


@pytest.mark.parametrize("path", ["/", "/weather", "/yol/uzun/detay", "/p?x=1&y=2"])
def test_mac_path_verbatim(run_cli, path):
    rc, out = run_cli("--mac", "a:n:0.05", path)
    assert f"http://127.0.0.1:8402{path}" in out


def test_mac_deterministic(run_cli):
    a = run_cli("--mac", "a:n:0.05", "/w")[1]
    b = run_cli("--mac", "a:n:0.05", "/w")[1]
    assert a == b


def test_mac_different_path_different_mac(run_cli):
    a = run_cli("--mac", "a:n:0.05", "/w")[1]
    b = run_cli("--mac", "a:n:0.05", "/other")[1]
    assert a != b


def test_mac_different_nonce_different_mac(run_cli):
    a = run_cli("--mac", "a:n1:0.05", "/w")[1]
    b = run_cli("--mac", "a:n2:0.05", "/w")[1]
    assert a != b


# -- --evm =======================================================================================

def test_evm_returns_0(run_cli):
    rc, out = run_cli("--evm", "n1", "/weather")
    assert rc == 0


def test_evm_first_line_format(run_cli):
    """ORTAM-ANATOMI: 'Sester-EVM <urlsafe-b64url-json>' payload."""
    rc, out = run_cli("--evm", "n1", "/weather")
    line = out.splitlines()[0]
    assert line.startswith("Sester-EVM ")
    tok = line[len("Sester-EVM "):]
    padded = tok + "=" * (-len(tok) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded))
    assert set(payload) >= {"scheme", "agent", "nonce", "amount", "signature"}


def test_evm_payload_fields(run_cli):
    rc, out = run_cli("--evm", "nonce42", "/weather")
    tok = out.splitlines()[0][len("Sester-EVM "):]
    payload = json.loads(base64.urlsafe_b64decode(tok + "=" * (-len(tok) % 4)))
    assert payload["scheme"] == "exact-sester"
    assert payload["nonce"] == "nonce42"
    assert payload["amount"] == f"{D.PRICE:.2f}"


def test_evm_agent_is_demo_key_address(run_cli):
    """ORTAM: sk='0x'+'d3'*32 (SABIT demo-anahtar) — agent = checksum-address lower."""
    from eth_account import Account
    sk = "0x" + "d3" * 32
    expected_agent = Account.from_key(sk).address.lower()
    rc, out = run_cli("--evm", "n1", "/weather")
    tok = out.splitlines()[0][len("Sester-EVM "):]
    payload = json.loads(base64.urlsafe_b64decode(tok + "=" * (-len(tok) % 4)))
    assert payload["agent"] == expected_agent


def test_evm_signature_hex(run_cli):
    """ORTAM-OGRENDI: imza '0x'-öneksiz ham-hex (130-char = 65-byte r+s+v)."""
    rc, out = run_cli("--evm", "n1", "/weather")
    tok = out.splitlines()[0][len("Sester-EVM "):]
    payload = json.loads(base64.urlsafe_b64decode(tok + "=" * (-len(tok) % 4)))
    sig = payload["signature"]
    assert not sig.startswith("0x")
    int(sig, 16)
    assert len(sig) == 130


def test_evm_default_path(run_cli):
    """ORTAM: path YOKSA '/weather'."""
    rc, out = run_cli("--evm", "n1")
    assert "8402/weather" in out


def test_evm_custom_path(run_cli):
    rc, out = run_cli("--evm", "n1", "/custom")
    assert "8402/custom" in out


def test_evm_curl_template(run_cli):
    rc, out = run_cli("--evm", "n1", "/weather")
    assert "curl" in out
    assert "X-Payment" in out
    assert "8402/weather" in out


def test_evm_deterministic_same_nonce(run_cli):
    a = run_cli("--evm", "same", "/w")[1].splitlines()[0]
    b = run_cli("--evm", "same", "/w")[1].splitlines()[0]
    assert a == b


def test_evm_amount_is_price(run_cli):
    rc, out = run_cli("--evm", "n1", "/weather")
    tok = out.splitlines()[0][len("Sester-EVM "):]
    payload = json.loads(base64.urlsafe_b64decode(tok + "=" * (-len(tok) % 4)))
    assert payload["amount"] == "0.05"


# -- yardim / varsayilan =========================================================================

@pytest.mark.parametrize("argv", [
    [], ["--help"], ["--nope", "x"], ["--mac"], ["--evm"], ["other"],
])
def test_unknown_or_no_args_prints_doc_returns_0(run_cli, argv):
    """ORTAM: bilinmeyen-flag/arg-YOK -> __doc__ yazilir + rc 0 (fail-loud DEGIL)."""
    rc, out = run_cli(*argv)
    assert rc == 0
    assert out.strip() == D.__doc__.strip()


def test_doc_first_line(run_cli):
    rc, out = run_cli()
    assert out.splitlines()[0].startswith("SESTER demo")


# -- dal-onceligi ================================================================================

def test_mac_flag_checked_before_evm(run_cli):
    """ORTAM: --mac once kontrol edilir (if-sira) — '--mac --evm' -> mac-dali."""
    rc, out = run_cli("--mac", "--evm:x")
    assert rc == 2


def test_two_args_minimum(run_cli):
    """ORTAM: len(sys.argv)>=3 gerekir — 2-arg'da doc dali."""
    rc, out = run_cli("--mac")
    assert rc == 0
    assert D.__doc__.strip() in out


def test_argv_index_1_must_match_flag(run_cli):
    """ORTAM: sys.argv[1] '--mac' DEGILSE doc dali (arg-sira oncelik)."""
    rc, out = run_cli("not-a-flag", "--mac", "a:n:0.05")
    assert rc == 0
    assert "SESTER demo" in out
