"""PUGIO migrate_pg — SQLite→Postgres migrasyonu (hash-koruyan replay).

İlke: zincir YENİDEN ÜRETİLMEZ — her olay hash/prev_hash/seq ile aynen
taşınır. Aynı secret'la PgLedger.verify_chain() geçmek taşimanın tek kanıtıdır.

Modlar:
  --plan      yalnız sayım (bağlantı yok, zararsız)
  --dry-run   hedefe yazmadan bütünlük-ön-kontrol (kaynak verify_chain)
  --verify    hedefteki zincir + nonce-sayısını doğrula (yazma yok)
  (varsayılan) taşı: batch-insert + doğrula; tekrar-çalıştırma güvenli
              (mevcut seq'ler atlanır — idempotent)

Kullanım:
  python -m pugio.migrate_pg --sqlite pugio.sqlite3 \
      [--dsn "host=… dbname=… user=… password=…"] [--secret SECRET]
      [--batch 500] [--plan|--dry-run|--verify]
"""

from __future__ import annotations

import argparse
import sys

from .ledger import Ledger
from .pg_ledger import PgLedger

DEFAULT_SECRET = "dev-secret"


def _source_events(src: Ledger) -> list[dict]:
    return src.export_events(None)


def migrate(src_path: str, dst: PgLedger, *, secret: str, batch: int = 500,
            dry_run: bool = False) -> int:
    src = Ledger(src_path, secret=secret)
    try:
        events = _source_events(src)
        nonces = src.export_nonces()
        if not src.verify_chain():
            print("RED: kaynak zincir bozuk — migrasyon başlatılmaz (fail-closed)")
            return 1
        print(f"kaynak: {len(events)} olay, {len(nonces)} nonce, zincir SAĞLAM")

        if dry_run:
            print("dry-run: hedefe YAZILMADI")
            return 0

        # idempotentlik: hedefteki mevcut seq'leri atla
        existing = {e["seq"] for e in dst.export_events(None)}
        pending = [e for e in events if e["seq"] not in existing]
        moved = 0
        for i in range(0, len(pending), batch):
            chunk = pending[i:i + batch]
            for ev in chunk:
                dst.insert_event(ev)
            moved += len(chunk)
            print(f"  … {moved}/{len(pending)} olay taşındı")
        for n in nonces:
            agent, nonce = n["nonce_key"].split("|", 1)
            dst.insert_nonce(agent, nonce, n["ts"])

        ok = dst.verify_chain()
        print(f"hedef: {len(dst.export_events(None))} olay, "
              f"{dst.nonce_count()} nonce, zincir "
              f"{'SAĞLAM' if ok else 'KIRIK'}")
        if not ok:
            print("RED: hedef-zincir doğrulanmadı")
            return 1
        print(f"KABUL: {moved} olay taşındı; hash'ler korundu")
        return 0
    finally:
        src.close()


def verify(src_path: str, dst: PgLedger, *, secret: str) -> int:
    src = Ledger(src_path, secret=secret)
    try:
        se, de = src.export_events(None), dst.export_events(None)
        ok_chain = dst.verify_chain()
        same = [(a["seq"], a["hash"]) for a in se] == [(b["seq"], b["hash"]) for b in de]
        same_nonces = (src.nonce_count() == dst.nonce_count())
        print(f"kaynak {len(se)} olay / hedef {len(de)} olay; "
              f"hash-dizisi {'AYNI' if same else 'FARKLI'}; "
              f"nonce {src.nonce_count()}/{dst.nonce_count()}; "
              f"hedef-zincir {'SAĞLAM' if ok_chain else 'KIRIK'}")
        return 0 if (same and same_nonces and ok_chain) else 1
    finally:
        src.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pugio.migrate_pg",
                                 description="SQLite→PG hash-koruyan migrasyon")
    ap.add_argument("--sqlite", default="pugio.sqlite3")
    ap.add_argument("--dsn", default=None)
    ap.add_argument("--secret", default=DEFAULT_SECRET)
    ap.add_argument("--batch", type=int, default=500)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = ap.parse_args(argv)

    # kaynak-tarafı kontrolleri ÖNCE: DSN'siz de plan/dry-run/bozuk-kaynak-ret çalışır
    src = Ledger(args.sqlite, secret=args.secret)
    try:
        chain_ok = src.verify_chain()
        n_events, n_nonces = len(_source_events(src)), src.nonce_count()
    finally:
        src.close()
    if not chain_ok:
        print("RED: kaynak zincir bozuk — migrasyon başlatılmaz (fail-closed)")
        return 1
    if args.plan:
        print(f"plan: {n_events} olay, {n_nonces} nonce, zincir SAĞLAM")
        return 0
    if args.dry_run:
        print(f"dry-run: {n_events} olay, {n_nonces} nonce — hedefe YAZILMADI")
        return 0

    try:
        dst = PgLedger(secret=args.secret, dsn=args.dsn)
    except RuntimeError as e:
        print(f"RED: {e}")
        return 2
    try:
        if args.verify:
            return verify(args.sqlite, dst, secret=args.secret)
        return migrate(args.sqlite, dst, secret=args.secret,
                       batch=args.batch, dry_run=False)
    finally:
        dst.close()


if __name__ == "__main__":
    sys.exit(main())
