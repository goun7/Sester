"""SESTER snapshot — ledger DB tutarlı-kopya (WAL-checkpoint + VACUUM INTO) aracı.

DALGA-D3: ödeme-akışı koduna DOKUNMADAN yeni bir operasyon-aracı eklendi.
Mevcut `Ledger`/CLI kodu değiştirilmedi — bu modül yalnızca OKU + dışa-aç
işlemleri yapar (events/seen_nonces tablolarına YAZMAZ).

Neden-bu-tool: SQLite WAL modunda yazılan olaylar önce `-wal` yan-dosyasında
yaşar. Bir yedek/doğrulama paketi `db.sqlite3` dosyasını kopyalarsa WAL'de
bulunan son olayları kaybeder — tutarsız/eksik kopya. Bu yüzden:

  1) `wal_checkpoint(TRUNCATE)` — WAL'i ana DB'ye yazar, yan-dosyayı sıfırlar
  2) `VACUUM INTO` — ana DB'nin temiz, tek-dosya kopyasını üretir

SQLite detayları (gerçek 3.54 ile doğrulandı, tests/test_snapshot_dallar.py):
  * `VACUUM INTO` autocommit dışında çalışmaz — kodumuz `isolation_level=None`
    ile açılan bağlantı kullanır (Ledger ile aynı disiplin).
  * `PRAGMA wal_checkpoint(TRUNCATE)` üçlü-döner: (busy, log, checkpointed).
    busy=1 → bir okuyucu WAL'i hâlâ okuyor, checkpoint TAMAMLANAMADI.
  * WAL modu olmayan (`:memory:`, `file::memory:?cache=shared`) DB'lerde
    `journal_mode='memory'` olur; wal_checkpoint no-op'dur (log=-1) — bu durum
    raporlanır, hata-değil.

Güvenlik-notu: açık-erişim disiplini. snapshot hedef-dosyası 0600 oluşturulur
(AT-179: ödeme-geçmişi + replay-koruma dünya-okunabilir-olmamalı).
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any

# VARSAYILAN: WAL modundaki bir ledger için checkpoint'e kadar yaklaşık
# bayt-consolide-beklentisi. Yalnızca raporlama/bilgi-amaçlı.
DEFAULT_TIMEOUT_MS = 5000


def _sql_str(s: str) -> str:
    """SQLite tek-tırnak kaçışı — VACUUM INTO hedefi için güvenli literal."""
    return "'" + s.replace("'", "''") + "'"


def wal_checkpoint(db_path: str, *, truncate: bool = True,
                   timeout_ms: int = DEFAULT_TIMEOUT_MS) -> dict[str, Any]:
    """TRUNCATE modunda WAL checkpoint yapar; önceki/sonraki WAL+DB boyutları.

    Bağlantı kendi-üzerinde açılır (Ledger'a DOKUNMAZ) — `isolation_level=None`
    (autocommit) şart: PRAGMA'lar autocommit bağlamında çalışır.

    Raporlanan alanlar:
      db_path              : bağlanılan DB yolu
      journal_mode         : checkpoint-sonrası journal_mode (wal/memory/...)
      mode                 : kullanılan checkpoint modu ('TRUNCATE' varsayılan)
      busy                 : 0=tamamlandı, 1=okuyucu-kilidi (eksik-checkpoint)
      log_frames           : WAL'deki toplam çerçeve (checkpoint-öncesi)
      checkpointed_frames  : WAL'den ana-DB'ye yazılan çerçeve sayısı
      wal_bytes_before     : checkpoint-öncesi `-wal` dosya boyutu (yoksa 0)
      wal_bytes_after      : checkpoint-sonrası `-wal` dosya boyutu (yoksa 0)
      db_bytes_before      : checkpoint-öncesi ana-DB dosya boyutu
      db_bytes_after       : checkpoint-sonrası ana-DB dosya boyutu
      wal_file_existed     : `-wal` dosyası checkpoint-öncesi mevcut miydi
      truncated            : WAL boyutu sıfırlandı mı (busy=0 ve WAL modu)
    """
    path = str(db_path)
    wal_path = path + "-wal"

    def _size(p: str) -> int:
        try:
            return os.path.getsize(p)
        except OSError:
            return 0

    wal_existed = os.path.exists(wal_path)
    wal_before = _size(wal_path)
    db_before = _size(path)

    mode = "TRUNCATE" if truncate else "PASSIVE"
    conn = sqlite3.connect(path, isolation_level=None,
                           check_same_thread=False)
    try:
        conn.execute(f"PRAGMA busy_timeout={int(timeout_ms)}")
        # Mod önce SET edilir — WAL-olmayan DB'lerde wal_checkpoint no-op'tur
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        result = conn.execute(f"PRAGMA wal_checkpoint({mode})").fetchone()
        busy, log_frames, checkpointed = (int(result[0]), int(result[1]),
                                          int(result[2]))
    finally:
        conn.close()

    wal_after = _size(wal_path)
    db_after = _size(path)
    # journal_mode WAL-değilse (memory/delete) checkpoint fiziksel no-op'dur;
    # busy=0 + frames=0 raporlanır ama "truncated" yanıltıcı-olmasın
    truncated = (busy == 0 and journal == "wal" and wal_after == 0)

    return {
        "db_path": path,
        "journal_mode": journal,
        "mode": mode,
        "busy": busy,
        "log_frames": log_frames,
        "checkpointed_frames": checkpointed,
        "wal_bytes_before": wal_before,
        "wal_bytes_after": wal_after,
        "db_bytes_before": db_before,
        "db_bytes_after": db_after,
        "wal_file_existed": wal_existed,
        "truncated": truncated,
    }


def snapshot(db_path: str, out_path: str, *, checkpoint: bool = True,
             timeout_ms: int = DEFAULT_TIMEOUT_MS) -> dict[str, Any]:
    """Tutarlı ledger-kopyası üret: önce WAL checkpoint, sonra VACUUM INTO.

    Adımlar:
      1) checkpoint=True ise WAL'deki olaylar ana-DB'ye yazılır (TRUNCATE)
      2) `VACUUM INTO out_path` — ana-DB'nin temiz tek-dosya kopyası
         (sayfa-bütünlüğü-yeniden-öre-r, boş-sayfaları-temizler)
      3) 0600 yetki- kilidi (AT-179 disiplini: ödeme-geçmişi gizli)

    VACUUM INTO sınırları (SQLite-esası):
      * hedef dosya MEVCUT OLMAMALI (overwrite etmez, hata fırlatır)
      * kaynak bağlantıda aktif-transaction OLMAMALI (autocomuit şart)
      * :memory: kaynağından da çalışır (WAL checkpoint no-op raporlanır)

    Dönüş: wal_checkpoint raporu + snapshot-bilgisi (yol/boyut/varlık).
    """
    path = str(db_path)
    out = str(out_path)
    if os.path.exists(out):
        raise FileExistsError(
            f"snapshot-hedefi-mevcut: {out} — VACUUM INTO üzerine-yazmaz; "
            "önce-silin-veya-farklı-yol-verin (fail-closed)")

    ckpt: dict[str, Any] | None = None
    if checkpoint:
        ckpt = wal_checkpoint(path, truncate=True, timeout_ms=timeout_ms)
        # busy=1 durumunda bile devam: WAL'de-kalan-olaylar snapshot'ın
        # gerisinde-kalabilir; bunu raporda-donuyoruz (çağıran karar-verir)
        # — sessiz-geçiş yapmıyoruz (metin-env disiplini)

    conn = sqlite3.connect(path, isolation_level=None,
                           check_same_thread=False)
    try:
        conn.execute(f"PRAGMA busy_timeout={int(timeout_ms)}")
        # VACUUM INTO autocomit-dışı-Red; isolation_level=None şart.
        # Hedef-yol tek-tırnak-kaçışlı literal (dosya-adında quote/' olsa güvenli).
        conn.execute(f"VACUUM INTO {_sql_str(out)}")
    finally:
        conn.close()

    if not os.path.exists(out):
        raise RuntimeError(
            f"VACUUM INTO tamamlandı-ama-hedef-yok: {out} (tutarsız-durum)")
    # 0600 — AT-179: ödeme-geçmişi + replay-koruma dünya-okunabilir-olamaz
    os.chmod(out, 0o600)
    snap_size = os.path.getsize(out)

    return {
        "db_path": path,
        "out_path": out,
        "checkpointed": ckpt,
        "snapshotted": True,
        "snapshot_bytes": snap_size,
        "source_bytes_after_checkpoint": (
            ckpt["db_bytes_after"] if ckpt else os.path.getsize(path)),
    }


# --------------------------------------------------------------- CLI (modül)

def main(argv: list[str] | None = None) -> int:
    """CLI: python -m sester.snapshot <snapshot|wal-checkpoint> ...

    Komutlar:
      snapshot <DB> <OUT>          WAL-checkpoint + VACUUM INTO ile kopya al
      wal-checkpoint <DB>          TRUNCATE-checkpoint; WAL/DB boyut-raporu
    """
    import sys

    args = sys.argv[1:] if argv is None else list(argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__.split("\n", 1)[0])
        print("kullanım: python -m sester.snapshot "
              "snapshot <DB> <OUT> | wal-checkpoint <DB>")
        return 0 if args else 2

    cmd = args[0]
    rest = args[1:]
    if cmd == "snapshot":
        if len(rest) != 2:
            print("kullanım: snapshot <DB> <OUT>")
            return 2
        db, out = rest
        try:
            rep = snapshot(db, out)
        except (FileExistsError, sqlite3.Error, OSError) as e:
            print(f"RED: {e}")
            return 1
        ck = rep["checkpointed"]
        print(f"== snapshot: {rep['db_path']} -> {rep['out_path']} ==")
        if ck:
            print(f"  checkpoint : mode={ck['mode']} busy={ck['busy']} "
                  f"journal={ck['journal_mode']}")
            print(f"  WAL        : {ck['wal_bytes_before']} -> "
                  f"{ck['wal_bytes_after']} bayt")
            print(f"  ana-DB     : {ck['db_bytes_before']} -> "
                  f"{ck['db_bytes_after']} bayt")
            print(f"  çerçeveler : {ck['checkpointed_frames']}/"
                  f"{ck['log_frames']} yazıldı")
        else:
            print("  checkpoint : atlandı (--no-checkpoint)")
        print(f"  snapshot   : {rep['snapshot_bytes']} bayt (0600)")
        print("KABUL: tutarlı-kopya alındı")
        return 0

    if cmd in ("wal-checkpoint", "wal_checkpoint"):
        if len(rest) != 1:
            print("kullanım: wal-checkpoint <DB>")
            return 2
        try:
            rep = wal_checkpoint(rest[0])
        except (sqlite3.Error, OSError) as e:
            print(f"RED: {e}")
            return 1
        print(f"== wal-checkpoint: {rep['db_path']} ==")
        print(f"  mode            : {rep['mode']}")
        print(f"  journal_mode    : {rep['journal_mode']}")
        print(f"  busy            : {rep['busy']} "
              f"(0=tamamlandı, 1=okuyucu-kilidi)")
        print(f"  çerçeveler      : {rep['checkpointed_frames']}/"
              f"{rep['log_frames']} konsolide")
        print(f"  WAL-boyutu      : {rep['wal_bytes_before']} -> "
              f"{rep['wal_bytes_after']} bayt")
        print(f"  DB-boyutu       : {rep['db_bytes_before']} -> "
              f"{rep['db_bytes_after']} bayt")
        if rep["truncated"]:
            print("KABUL: WAL TRUNCATE ile sıfırlandı")
            return 0
        if rep["busy"] == 1:
            print("RED: checkpoint tamamlandı — WAL'de hâlâ veri var "
                  "(okuyucu-kilidi)")
            return 1
        # WAL-olmayan DB (memory/delete modu): fiziksel-no-op — bilgi
        print("KABUL: WAL-dışı journal-modu — checkpoint no-op (oluştu)")
        return 0

    print(f"RED: bilinmeyen-komut: {cmd!r} "
          "(snapshot | wal-checkpoint)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
