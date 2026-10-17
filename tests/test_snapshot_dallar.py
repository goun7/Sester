# -*- coding: utf-8 -*-
"""DALGA-D3: sester/snapshot.py dal-kesen testleri — gerçek SQLite WAL kanıtı.

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4 (ağır-hücre): testler GERÇEK SQLite dosyası üzerinde çalışır —
mock/stub YOK. tmp_path + gerçek disk-yan-dosyaları (-wal/-shm) ile OS-seviye
kanıtlar (os.path.getsize/os.path.exists).

Neden-WAL-gerçekliği-şart: DALGA-D3'ün özü WAL checkpoint'in fiziksel-kanıtıdır.
`VACUUM INTO` ve `PRAGMA wal_checkpoint(TRUNCATE)` bir SQLite-üzerinde-çalışır;
sahte-nesne ile çalışırsa operasyon-aracı boş-iddia olurdu.

Fonksiyon basina dal listesi:

wal_checkpoint(db_path):
    basari: WAL-modlu-DB'ye yazınca `-wal` DOSYASI gerçekten oluşur (OS)
    basari: checkpoint-sonrası WAL boyutu 0'a düşer (TRUNCATE) — OS-kanıtı
    basari: checkpoint-öncesi DB-boyutu < checkpoint-sonrası (veri ana-DB'ye)
    basari: WAL-dışı-DB'de (journal=delete) no-op + log=-1 raporlanır
    basari: rapor dict'i beklenen tüm alanları taşır
    sınır : WAL modunda WAL-dosyası yokken wal_bytes_before=0 (temiz-DB)

snapshot(db_path, out_path):
    basari: snapshot-dosyası gerçekten oluşur + WAL'suzdur (tek-dosya)
    basari: snapshot içeriği kaynakla birebir (satır-sayısı + zincir-sağlam)
    basari: WAL'de-bekleyen-olaylar checkpoint-sonrası snapshot'a yansır
    hata : mevcut-hedef-dosyaya FileExistsError (fail-closed — üzerine-yazmaz)
    basari: snapshot-dosyası 0600 yetki-kilidi taşır (AT-179 disiplini)
    basari: checkpoint=False bayrağı checkpoint-adımını atlatır

main(argv) — CLI (python -m sester.snapshot):
    basari: snapshot <DB> <OUT> rc=0 + tutarlı-kopya çıktısı
    basari: wal-checkpoint <DB> rc=0 + WAL/DB boyut-raporu
    basari: WAL doluyken wal-checkpoint TRUNCATE-kanıtı çıktıda
    hata : bilinmeyen-komut rc=2 (RED)
    hata : eksik-argüman rc=2 (kullanım-bilgisi)
    hata : mevcut-hedef rc=1 (RED — fail-closed)
"""

from __future__ import annotations

import os
import sqlite3

import pytest

from sester.ledger import Ledger
from sester.snapshot import main, snapshot, wal_checkpoint

SECRET = "d3-snapshot-test-secret"


# -------------------------------------------------------------- yardımcılar

def _wal_exists(db: str) -> bool:
    return os.path.exists(db + "-wal")


def _wal_size(db: str) -> int:
    try:
        return os.path.getsize(db + "-wal")
    except OSError:
        return 0


def _db_size(db: str) -> int:
    return os.path.getsize(db)


def _make_wal_db(db: str, n_events: int = 80) -> Ledger:
    """Gerçek WAL-modlu ledger: WAL'i gerçekten-dolu-bırakır.

    Ledger bağlantısı AÇIKken WAL'de biriken çerçeveler OS-seviyesinde
    gözlemlenir — close() otomatik-checkpoint yapıp WAL'i temizler, bu yüzden
    bağlantıyı açık-tutuyoruz (DALGA-D3'ün test-ettiği gerçek-durum)."""
    led = Ledger(db, secret=SECRET)
    for i in range(n_events):
        led.append("charge_receipt", "d3-agent", "/resource", 0.01,
                   amount_minor=10_000, payload={"i": i})
    return led


# ==================================================== wal_checkpoint başarısı

def test_d3_wal_file_really_exists_after_writes(tmp_path):
    """WAL-mode'da yazınca `-wal` yan-dosyası OS-seviyesinde GERÇEK oluşur.

    Bu DALGA-D3'ün fiziksel-önkoşuludur: WAL dosyası yoksa checkpoint'in
    yapıtığı hiçbir şey yoktur (test-edilen-şey-gerçek-değil)."""
    db = str(tmp_path / "wal.sqlite3")
    led = _make_wal_db(db, n_events=60)
    try:
        assert _wal_exists(db), (
            "WAL-dosyası oluşmadı — Ledger WAL-modunda değil (önkoşul-bozuk)")
        assert _wal_size(db) > 0
    finally:
        led.close()


def test_d3_checkpoint_truncates_wal_to_zero_os_level(tmp_path):
    """WAL-checkpoint TRUNCATE: WAL boyutunu gerçekten 0'a düşürür.

    Üretim-kanıtı: os.path.getsize ile OS-seviyesinde-ölçülür, mock'suz."""
    db = str(tmp_path / "trunc.sqlite3")
    led = _make_wal_db(db, n_events=80)
    try:
        wal_before = _wal_size(db)
        db_before = _db_size(db)
        assert wal_before > 0, "WAL boş — test-anlamsız (önkoşul-bozuk)"

        rep = wal_checkpoint(db)

        assert rep["wal_bytes_before"] == wal_before
        assert rep["wal_bytes_after"] == 0
        assert _wal_size(db) == 0  # OS-seviyesi-kanıtı
        assert rep["truncated"] is True
        assert rep["busy"] == 0
        # veri ana-DB'ye taşındı: DB boyutu büyüdü
        assert rep["db_bytes_after"] > db_before
        assert _db_size(db) == rep["db_bytes_after"]
    finally:
        led.close()


def test_d3_checkpoint_grows_main_db_os_level(tmp_path):
    """WAL'deki olaylar ana-DB'ye konsolide-olduğunda DB dosyası büyür.

    Dikkat: WAL-okuyucusu olmayan-tek-süreç-ortamında checkpoint-sonrası
    db_bytes_after >= db_bytes_before + (WAL'deki-veri) ilişkisi-vardır."""
    db = str(tmp_path / "grow.sqlite3")
    led = _make_wal_db(db, n_events=40)
    try:
        db_before = _db_size(db)
        wal_before = _wal_size(db)
        rep = wal_checkpoint(db)
        growth = rep["db_bytes_after"] - db_before
        assert growth > 0, (
            f"ana-DB büyümedi: {db_before} -> {rep['db_bytes_after']} "
            f"(WAL {wal_before} bayt iken) — checkpoint veriyi taşımıyor")
    finally:
        led.close()


def test_d3_checkpoint_report_carries_all_fields(tmp_path):
    """Rapor-dict beklenen tüm alanları taşır (sözleşme-sabitleme)."""
    db = str(tmp_path / "rep.sqlite3")
    led = _make_wal_db(db, n_events=10)
    try:
        rep = wal_checkpoint(db)
    finally:
        led.close()
    expected = {"db_path", "journal_mode", "mode", "busy", "log_frames",
                "checkpointed_frames", "wal_bytes_before", "wal_bytes_after",
                "db_bytes_before", "db_bytes_after", "wal_file_existed",
                "truncated"}
    assert expected <= set(rep), f"eksik-alanlar: {expected - set(rep)}"
    assert rep["db_path"] == db
    assert rep["mode"] == "TRUNCATE"
    assert rep["journal_mode"] == "wal"


def test_d3_checkpoint_passive_mode_is_reported(tmp_path):
    """truncate=False → PASSIVE modu raporlanır (mod-sözleşmesi)."""
    db = str(tmp_path / "passive.sqlite3")
    led = _make_wal_db(db, n_events=10)
    try:
        from sester.snapshot import wal_checkpoint as wc
        rep = wc(db, truncate=False)
        assert rep["mode"] == "PASSIVE"
    finally:
        led.close()


def test_d3_checkpoint_on_non_wal_db_is_noop_not_error(tmp_path):
    """WAL-dışı (delete-journal) DB'de checkpoint no-op'dur — RED-değil.

    SQLite gerçeği: PRAGMA wal_checkpoint WAL-olmayan-DB'de (0, -1, -1)
    döndürür. Araç bunu raporlar, exception-değil (operasyon-aracı)."""
    db = str(tmp_path / "plain.sqlite3")
    conn = sqlite3.connect(db, isolation_level=None)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("CREATE TABLE t(x)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.close()

    rep = wal_checkpoint(db)
    assert rep["journal_mode"] != "wal"
    assert rep["log_frames"] == -1  # SQLite'ın no-op-imzası
    assert rep["truncated"] is False


# ==================================================== snapshot başarısı

def test_d3_snapshot_file_is_created_without_wal(tmp_path):
    """Snapshot: tek-dosya, WAL'siz, disk-gerçeği.

    VACUUM INTO çıktısı daima tek-başına bir DB'dir — `-wal`/`-shm`
    yan-dosyaları OLMAZ (snapshot'ın tüm-şeyiyile-taşınabilir-olması)."""
    db = str(tmp_path / "src.sqlite3")
    out = str(tmp_path / "out" / "snap.sqlite3")
    os.makedirs(os.path.dirname(out))
    led = _make_wal_db(db, n_events=30)
    led.close()

    rep = snapshot(db, out)

    assert rep["snapshotted"] is True
    assert os.path.exists(out)
    assert _wal_size(out) == 0
    assert os.path.exists(out + "-wal") is False
    assert os.path.exists(out + "-shm") is False
    assert rep["snapshot_bytes"] == _db_size(out) > 0


def test_d3_snapshot_content_matches_source_row_count_and_chain(tmp_path):
    """Snapshot içeriği kaynakla birebir: satır-sayısı + hash-zinciri-sağlam."""
    db = str(tmp_path / "chain.sqlite3")
    out = str(tmp_path / "chain_snap.sqlite3")
    led = _make_wal_db(db, n_events=25)
    led.close()

    rep = snapshot(db, out)
    assert rep["snapshotted"] is True

    src = sqlite3.connect(db)
    dst = sqlite3.connect(out)
    try:
        n_src = src.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        n_dst = dst.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert n_dst == n_src == 25
        # hash-zinciri aynen-taşınmış-mı (seq+hash birebir)
        src_rows = src.execute(
            "SELECT seq, hash FROM events ORDER BY seq").fetchall()
        dst_rows = dst.execute(
            "SELECT seq, hash FROM events ORDER BY seq").fetchall()
        assert dst_rows == src_rows
    finally:
        src.close()
        dst.close()

    # kaynak-ledger yeniden-açılır ve zincir doğrulanır (hash-koruyan-taşıma)
    led2 = Ledger(db, secret=SECRET)
    try:
        assert led2.verify_chain() is True
    finally:
        led2.close()


def test_d3_snapshot_includes_wal_pending_events(tmp_path):
    """WAL'de-bekleyen-olaylar checkpoint-sonrası snapshot'a yansır.

    Bu DALGA-D3'ün özüdür: WAL'siz-düz-kopya YAPAMAYACAĞI şeyi snapshot yapar
    — `-wal` dosyasını kopyalamadan son-olayları kaybeden naïv-kopya-tuzağı."""
    db = str(tmp_path / "pend.sqlite3")
    out = str(tmp_path / "pend_snap.sqlite3")
    led = _make_wal_db(db, n_events=50)
    try:
        assert _wal_exists(db) and _wal_size(db) > 0
        # snapshot: checkpoint-önce (WAL dolu) + VACUUM INTO
        rep = snapshot(db, out)
        assert rep["snapshotted"] is True
        ck = rep["checkpointed"]
        assert ck is not None and ck["wal_bytes_before"] > 0
        # WAL'deki-olaylar snapshot'ta-olmalı (checkpoint taşıdı)
        dst = sqlite3.connect(out)
        try:
            n = dst.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            assert n == 50, (
                f"snapshot'ta {n}/50 olay — WAL'dekiler kayboldu "
                "(checkpoint-öncesi snapshot bozuk)")
        finally:
            dst.close()
    finally:
        led.close()


def test_d3_snapshot_refuses_existing_target_fail_closed(tmp_path):
    """Mevcut-hedef-dosyaya FileExistsError — VACUUM INTO üzerine-yazmaz.

    Fail-closed: sessizce-üzerine-yazmak veri-kaybına-yol-açar (eski-snapshot
    zaten-doğrulanmış-bir-kanıt-olabilir)."""
    db = str(tmp_path / "src2.sqlite3")
    out = str(tmp_path / "exists.sqlite3")
    led = _make_wal_db(db, n_events=5)
    led.close()
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("önceden-var")

    with pytest.raises(FileExistsError):
        snapshot(db, out)
    # hedef-değişmedi (üzerine-yazılmadı)
    with open(out, encoding="utf-8") as fh:
        assert fh.read() == "önceden-var"


def test_d3_snapshot_file_mode_is_0600(tmp_path):
    """Snapshot-dosyası 0600 — AT-179: ödeme-geçmişi gizli (mode-kanıtı)."""
    db = str(tmp_path / "mode.sqlite3")
    out = str(tmp_path / "mode_snap.sqlite3")
    led = _make_wal_db(db, n_events=5)
    led.close()

    snapshot(db, out)

    mode = os.stat(out).st_mode & 0o777
    assert mode == 0o600, f"snapshot-yetkisi {oct(mode)} — 0600 olmalı (AT-179)"


def test_d3_snapshot_without_checkpoint_step(tmp_path):
    """checkpoint=False → checkpoint-adımı atlanır (raporda None)."""
    db = str(tmp_path / "nock.sqlite3")
    out = str(tmp_path / "nock_snap.sqlite3")
    led = _make_wal_db(db, n_events=15)
    try:
        rep = snapshot(db, out, checkpoint=False)
        assert rep["snapshotted"] is True
        assert rep["checkpointed"] is None
        # VACUUM INTO yine-tutarlı-kopya-verir (checkpoint'sız-da çalışır)
        dst = sqlite3.connect(out)
        try:
            n = dst.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            assert n == 15
        finally:
            dst.close()
    finally:
        led.close()


def test_d3_snapshot_absorbs_free_pages_vacuum(tmp_path):
    """VACUUM: silinmiş-satırların boş-sayfaları snapshot'ta-yer-kapamaz.

    Üretim-kanıtı: kaynak-DB'de büyük-silme-sonrası snapshot-dosyası
    kaynak-DB'den belirgin-daha-küçüktür (VACUUM INTO'un temiz-kopyası)."""
    db = str(tmp_path / "vac.sqlite3")
    out = str(tmp_path / "vac_snap.sqlite3")
    led = Ledger(db, secret=SECRET)
    for i in range(120):
        led.append("charge_receipt", "vac-agent", "/r", 0.01,
                   amount_minor=10_000, payload={"i": i, "blob": "x" * 200})
    led.claim_nonce("vac-agent", "n1")
    led.close()

    # büyük-silme: çoğu-olayı-sil → boş-sayfalar
    conn = sqlite3.connect(db, isolation_level=None)
    conn.execute("DELETE FROM events WHERE seq > 5")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    rep = snapshot(db, out)
    assert rep["snapshotted"] is True
    # kaynak boş-sayfalar-taşıyor, snapshot-temiz: snapshot kayda-değer-küçük
    assert rep["snapshot_bytes"] < _db_size(db), (
        f"VACUUM INTO çalışmadı: snapshot {rep['snapshot_bytes']} "
        f">= kaynak {_db_size(db)} (boş-sayfalar-temizlenmedi)")


# ==================================================== CLI (main)

def test_d3_cli_snapshot_command_succeeds(tmp_path, capsys):
    """`snapshot <DB> <OUT>` rc=0 + KABUL + boyut-bilgisi."""
    db = str(tmp_path / "cli_src.sqlite3")
    out = str(tmp_path / "cli_out.sqlite3")
    led = _make_wal_db(db, n_events=20)
    led.close()

    rc = main(["snapshot", db, out])

    out_text = capsys.readouterr().out
    assert rc == 0
    assert os.path.exists(out)
    assert "KABUL: tutarlı-kopya alındı" in out_text
    assert str(out) in out_text


def test_d3_cli_wal_checkpoint_command_reports_sizes(tmp_path, capsys):
    """`wal-checkpoint <DB>` rc=0 + WAL/DB boyut-raporu + TRUNCATE-kanıtı."""
    db = str(tmp_path / "cli_wal.sqlite3")
    led = _make_wal_db(db, n_events=60)
    try:
        wal_before = _wal_size(db)
        assert wal_before > 0
        rc = main(["wal-checkpoint", db])
        out_text = capsys.readouterr().out
        assert rc == 0
        assert "wal-checkpoint" in out_text
        assert "TRUNCATE" in out_text
        assert f"{wal_before} -> 0 bayt" in out_text
        assert "KABUL: WAL TRUNCATE ile sıfırlandı" in out_text
        # OS-seviyesi-kanıtı: WAL gerçekten-sıfırlandı
        assert _wal_size(db) == 0
    finally:
        led.close()


def test_d3_cli_wal_checkpoint_underscore_alias(tmp_path, capsys):
    """`wal_checkpoint` (alt-tire-alias) da çalışır — ergonomi."""
    db = str(tmp_path / "alias.sqlite3")
    led = _make_wal_db(db, n_events=8)
    try:
        rc = main(["wal_checkpoint", db])
        assert rc == 0
        assert "wal-checkpoint" in capsys.readouterr().out
    finally:
        led.close()


def test_d3_cli_unknown_command_is_red(tmp_path, capsys):
    """Bilinmeyen-komut rc=2 + RED (fail-closed)."""
    rc = main(["bogus-komut"])
    assert rc == 2
    assert "RED" in capsys.readouterr().out


def test_d3_cli_snapshot_missing_args_is_usage_red(tmp_path, capsys):
    """Eksik-argüman rc=2 + kullanım-bilgisi (argüman-sözleşmesi)."""
    rc = main(["snapshot", str(tmp_path / "x.sqlite3")])
    assert rc == 2
    assert "kullanım" in capsys.readouterr().out


def test_d3_cli_snapshot_existing_target_is_red(tmp_path, capsys):
    """Mevcut-hedef rc=1 + RED (fail-closed — üzerine-yazma)."""
    db = str(tmp_path / "cli_e.sqlite3")
    out = str(tmp_path / "cli_e_out.sqlite3")
    led = _make_wal_db(db, n_events=5)
    led.close()
    snapshot(db, out)  # ilk-alım-başarılı

    rc = main(["snapshot", db, out])
    assert rc == 1
    assert "RED" in capsys.readouterr().out


def test_d3_cli_no_args_prints_usage_and_returns_2(capsys):
    """Argümansız-çağrı rc=2 + kullanım (help-değil-kırmızı-sessiz)."""
    rc = main([])
    assert rc == 2
    assert "kullanım" in capsys.readouterr().out


# ==================================================== modül-seviyesi

def test_d3_snapshot_module_runs_as_python_m(tmp_path):
    """`python -m sester.snapshot` gerçek-süreç olarak çalışır (entry-kanıtı)."""
    import subprocess
    import sys

    # alt-süreç kendi-cwd'sine-gider; PYTHONPATH repo-kökünü-taşımalı
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ)
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")

    db = str(tmp_path / "m_src.sqlite3")
    out = str(tmp_path / "m_out.sqlite3")
    led = _make_wal_db(db, n_events=12)
    led.close()

    proc = subprocess.run(
        [sys.executable, "-m", "sester.snapshot", "snapshot", db, out],
        capture_output=True, text=True, timeout=120,
        cwd=str(tmp_path), env=env)
    assert proc.returncode == 0, (
        f"python -m sester.snapshot başarısız: {proc.stderr[-400:]}")
    assert os.path.exists(out)

    # wal-checkpoint alt-komutu da gerçek-süreçte
    proc2 = subprocess.run(
        [sys.executable, "-m", "sester.snapshot", "wal-checkpoint", db],
        capture_output=True, text=True, timeout=120,
        cwd=str(tmp_path), env=env)
    assert proc2.returncode == 0
    assert "TRUNCATE" in proc2.stdout
