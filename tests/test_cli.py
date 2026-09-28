"""CLI testleri — `sester verify/receipt/history/bundle` (alıcı-tarafı).

`sester verify <receipt>` dışarıdan birinin makinesinde Sester YOKKEN bile
çalışmalı: bu test onu sabitler."""
from __future__ import annotations

import json
import os

import pytest

from sester import Ledger
from sester.cli import main


@pytest.fixture
def env(tmp_path, monkeypatch):
    d = str(tmp_path)
    monkeypatch.setenv("SESTER_LEDGER_DB", os.path.join(d, "cli.sqlite3"))
    monkeypatch.setenv("SESTER_LEDGER_SECRET", "cli-secret")
    monkeypatch.setenv("SESTER_NODE_SECRET", "node-secret")
    led = Ledger(os.path.join(d, "cli.sqlite3"), secret="cli-secret")
    led.append("charge_receipt", "cli-agent", "/weather", 0.05,
               amount_minor=50_000, payload={"nonce": "n1"})
    led.close()
    return d


def test_verify_accepts_valid_receipt(env, capsys):
    rc = main(["receipt", "1", "--out", os.path.join(env, "r.json")])
    assert rc == 0
    rc = main(["verify", os.path.join(env, "r.json")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "KABUL" in out
    assert "secret'sız" in out


def test_verify_reads_stdin(env, capsys, monkeypatch):
    main(["receipt", "1", "--out", os.path.join(env, "r.json")])
    with open(os.path.join(env, "r.json")) as fh:
        text = fh.read()
    monkeypatch.setattr("sys.stdin", type("S", (), {"read": lambda self: text})())
    rc = main(["verify", "-"])
    assert rc == 0
    assert "KABUL" in capsys.readouterr().out


def test_verify_inline_json_arg(env, capsys):
    main(["receipt", "1", "--out", os.path.join(env, "r.json")])
    with open(os.path.join(env, "r.json")) as fh:
        text = fh.read()
    rc = main(["verify", text])
    assert rc == 0


def test_verify_tampered_is_red(env, capsys):
    main(["receipt", "1", "--out", os.path.join(env, "r.json")])
    with open(os.path.join(env, "r.json")) as fh:
        r = json.load(fh)
    r["amount"] = "9.990000"
    with open(os.path.join(env, "bad.json"), "w") as fh:
        json.dump(r, fh)
    rc = main(["verify", os.path.join(env, "bad.json")])
    out = capsys.readouterr().out
    assert rc == 1
    assert "RED" in out


def test_verify_bozuk_json_is_red(env, capsys):
    with open(os.path.join(env, "x.json"), "w") as fh:
        fh.write("{bozuk")
    rc = main(["verify", os.path.join(env, "x.json")])
    assert rc == 1
    assert "RED" in capsys.readouterr().out


def test_receipt_refuses_non_charge(env, capsys):
    led = Ledger(os.environ["SESTER_LEDGER_DB"], secret="cli-secret")
    ev = led.append("permission_decision", "a", "/x", 0.0, payload={"d": 1})
    seq = ev["seq"]
    led.close()
    rc = main(["receipt", str(seq)])
    assert rc == 1
    assert "charge_receipt değil" in capsys.readouterr().out


def test_receipt_missing_seq_is_red(env, capsys):
    rc = main(["receipt", "999"])
    assert rc == 1
    assert "bulunamadı" in capsys.readouterr().out


def test_history_shows_chain(env, capsys):
    rc = main(["history", "--limit", "5"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "charge_receipt" in out
    assert "zincir-sağlam: True" in out


def test_bundle_exports_and_selfverifies(env, capsys):
    rc = main(["bundle", "--out", os.path.join(env, "b.json")])
    assert rc == 0
    with open(os.path.join(env, "b.json")) as fh:
        line = [l for l in fh if l.strip().startswith("{")][0]
    b = json.loads(line)
    assert b["event_count"] >= 1
    assert "pugio_bundle_version" in b  # K0 donuk-alan


def test_no_ledger_secret_fails_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SESTER_LEDGER_DB", str(tmp_path / "n.sqlite3"))
    monkeypatch.delenv("SESTER_LEDGER_SECRET", raising=False)
    with pytest.raises(SystemExit):
        main(["history"])


def test_version(capsys):
    assert main(["version"]) == 0
    from sester import __version__
    assert __version__ in capsys.readouterr().out
