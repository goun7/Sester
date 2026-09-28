#!/usr/bin/env python3
"""SESTER CLI — ödeme-kanıtı komutları.

Bağımsız-doğrulama disiplini (stdlib-only): `sester verify` bir receipt'i
Sester-kurulu-değil, node-secret-değil-şartıyla doğrular — alıcı tarafı.

Komutlar:
    sester verify <receipt.json|-> [--node-secret ENV]  kanıtı bağımsız doğrula
    sester receipt <seq>   [--ledger DB] [--secret ENV] ledger'dan kanıt üret
    sester history   [--ledger DB] [--agent ID]         kanıt-zinciri olayları
    sester bundle    [--ledger DB] [--agent ID]         dışa-doğrulanir bundle
    sester version

Çevre-değişkenleri (hepsi opsiyonel; local testler için $0):
    SESTER_LEDGER_DB      ledger yolu (varsayılan: sester.sqlite3)
    SESTER_LEDGER_SECRET  ledger-mührü (receipt üretimi için zorunlu)
    SESTER_NODE_SECRET    node-cosign anahtarı (üretim/doğrulama)
    SESTER_NODE_ID        node kimliği (varsayılan: sester:node)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


def _load_ledger(db: str, secret: str):
    from .ledger import Ledger
    return Ledger(db, secret=secret)


def _db(args) -> str:
    return args.ledger or os.environ.get("SESTER_LEDGER_DB", "sester.sqlite3")


def _secret() -> str:
    s = os.environ.get("SESTER_LEDGER_SECRET")
    if not s:
        raise SystemExit(
            "RED: SESTER_LEDGER_SECRET gerekli — ledger-secret'i set-edin "
            "(üretim-öncesi; testler için herhangi-bir-rastgele-dizge)")
    return s


def _node_secret(args) -> str | None:
    s = args.node_secret or os.environ.get("SESTER_NODE_SECRET")
    return s or None


def _print_receipt_summary(r: dict[str, Any]) -> None:
    print(f"  seq      : {r['seq']}")
    print(f"  agent    : {r['sub']}")
    print(f"  resource : {r['resource']}")
    print(f"  amount   : {r['amount']} {r['currency']} ({r['amount_minor']} minor)")
    print(f"  node     : {r['iss']} [{r['node_key_id']}]")
    print(f"  proof    : {r['proof'][:24]}…  (sha256, secret'sız-yeniden-hesaplanabilir)")
    print(f"  anchor   : {r['node_cosign'][:24]}…  (HMAC-node-imzası)"
          if r.get("node_cosign") else "  anchor   : (cosign-yok)")


def cmd_verify(args) -> int:
    """Alıcı-tarafı: receipt'i Sester olmadan doğrula."""
    from .receipt import load_receipt_json, verify_receipt

    src = args.receipt
    if src == "-":
        text = sys.stdin.read()
    elif os.path.exists(src):
        with open(src, "r", encoding="utf-8") as fh:
            text = fh.read()
    else:
        # doğrudan JSON argümanı da kabul (boru-hattı kolaylığı)
        text = src
    try:
        r = load_receipt_json(text)
    except Exception as e:  # ReceiptError
        print(f"RED: {e}")
        return 1
    ns = _node_secret(args)
    ok, msg = verify_receipt(r, node_secret=ns)
    print(f"== Sester receipt doğrulaması ==")
    _print_receipt_summary(r)
    print()
    if ok:
        print(f"KABUL: {msg}")
        return 0
    print(f"RED: {msg}")
    return 1


def cmd_receipt(args) -> int:
    """Ledger'dan seq için node-cosigned kanıt üret."""
    from .receipt import issue_receipt, receipt_json

    led = _load_ledger(_db(args), _secret())
    try:
        rows = led.conn.execute(
            "SELECT seq, ts, event_type, agent_id, host, amount, payload,"
            " prev_hash, hash, amount_minor FROM events WHERE seq = ?",
            (int(args.seq),)).fetchone()
        if not rows:
            print(f"RED: seq={args.seq} bulunamadı (ledger: {_db(args)})")
            return 1
        ev = {"seq": rows[0], "ts": rows[1], "event_type": rows[2],
              "agent_id": rows[3], "host": rows[4], "amount": rows[5],
              "payload": rows[6], "prev_hash": rows[7], "hash": rows[8],
              "amount_minor": rows[9]}
        if ev["event_type"] != "charge_receipt":
            print(f"RED: seq={args.seq} bir charge_receipt değil "
                  f"({ev['event_type']}) — kanıt-üretilemez (fail-closed)")
            return 1
        ns = _node_secret(args)
        r = issue_receipt(
            ev,
            node_id=os.environ.get("SESTER_NODE_ID", "sester:node"),
            node_secret=ns,
            chain_head=led.chain_head(),
            currency=args.currency,
        )
        print(receipt_json(r))
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(receipt_json(r) + "\n")
            print(f"# yazıldı: {args.out}", file=sys.stderr)
        return 0
    finally:
        led.close()


def cmd_history(args) -> int:
    """Kanıt-zinciri olayları (alıcı-tarafı-özeti)."""
    led = _load_ledger(_db(args), _secret())
    try:
        rows = led.conn.execute(
            "SELECT seq, ts, event_type, agent_id, host, amount, hash FROM events"
            + (" WHERE agent_id = ?" if args.agent else "")
            + " ORDER BY seq DESC LIMIT ?",
            (*(  (args.agent,) if args.agent else ()), int(args.limit))).fetchall()
        if not rows:
            print("(boş ledger — henüz ödeme yok)")
            return 0
        for seq, ts, et, ag, host, amount, h in rows:
            print(f"seq={seq:>5} {et:<16} agent={ag:<20} host={host:<24}"
                  f" amount={amount:<10.6f} hash={h[:16]}…")
        print(f"\n# zincir-sağlam: {led.verify_chain()}")
        print(f"# head: {led.chain_head()[:24]}…")
        return 0
    finally:
        led.close()


def cmd_bundle(args) -> int:
    """Dışa-doğrulanabilir kanıt-bundle'ı üret (alıcı sester olmadan doğrular)."""
    from .evidence import bundle_json, produce_bundle, verify_bundle

    led = _load_ledger(_db(args), _secret())
    try:
        b = produce_bundle(led, agent_id=args.agent)
        line = bundle_json(b)
        ok, msg = verify_bundle(b)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(line + "\n")
            print(f"# yazıldı: {args.out}", file=sys.stderr)
        print(f"# events={b['event_count']} head={b['head'][:16]}…")
        print(line)
        print(f"# kendi-doğrulama: {msg}", file=sys.stderr)
        return 0 if ok else 1
    finally:
        led.close()


def cmd_version(args) -> int:
    from . import __version__
    print(__version__)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sester",
        description="SESTER — ödeme-kanıtı CLI'si (bağımsız-doğrulama)")
    p.add_argument("--ledger", help="ledger yolu (env: SESTER_LEDGER_DB)")
    p.add_argument("--node-secret", dest="node_secret", default=None,
                   help="node-cosign anahtarı (env: SESTER_NODE_SECRET)")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="receipt'i bağımsız doğrula (alıcı tarafı)")
    v.add_argument("receipt", help="receipt JSON yolu, '-' (stdin) veya ham JSON")
    v.set_defaults(func=cmd_verify)

    r = sub.add_parser("receipt", help="ledger'dan seq için kanıt üret")
    r.add_argument("seq", type=int)
    r.add_argument("--out", help="çıktı-dosyası (stdout'a ek olarak)")
    r.add_argument("--currency", default="USDC-sim")
    r.set_defaults(func=cmd_receipt)

    h = sub.add_parser("history", help="kanıt-zinciri olayları")
    h.add_argument("--agent", default=None)
    h.add_argument("--limit", type=int, default=25)
    h.set_defaults(func=cmd_history)

    b = sub.add_parser("bundle", help="dışa-doğrulanir bundle üret")
    b.add_argument("--agent", default=None)
    b.add_argument("--out", default=None)
    b.set_defaults(func=cmd_bundle)

    ver = sub.add_parser("version", help="sürüm")
    ver.set_defaults(func=cmd_version)
    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
