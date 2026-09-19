"""Sovereign-wrapper uyumluluk yüzeyi — donuk sözleşmenin makine-koruması.

Tamga'nın ``tools/sovereign_verify.py`` sarmalayıcısı (K23.5 / AT-038
bağımsızlık-ilkesi) SESTER'ı tam olarak şöyle çağırır::

    from sester.ledger import Ledger
    lg = Ledger(path)           # secret YOK — read-only doğrulama
    ok = lg.verify_chain()
    lg.close()                  # finally ile korunuyor

Bu test, söz verdiğimiz donuk-yüzeyi (bkz. Tamga durum-bildirimi,
AGENT_MESH_PROTOCOLU §5 iletişim-önce kuralı) makine ile sabitler:
yüzeylerden biri yanlışlıkla değişirse, wrapper kırılmadan ÖNCE bu test
kırmalıdır. Donuk öğeler:

  * ``Ledger(db_path)`` tek-posizyonel kurucu (secret opsiyonel, default
    ``"dev-secret"`` — sarmalayıcı secret'sız çağırır),
  * ``Ledger.verify_chain() -> bool`` (HMAC-SHA256 zincir, GENESIS ``"0"*64``),
  * ``Ledger.close()`` (sarmalayıcının finally bloğu buna bağlı).

Sarmalayıcı-tarafı zafiyetler (Sester'da bulundu → Tamga'da düzeltildi +
karşılıklı doğrulandı, 2026-09-19; Sester yüzeyinde DEĞİŞİKLİK YOK —
düzeltmeler donmuş imzayı kullanır: ``Ledger(path, secret)``):

  * RISK-1 (sahte-GREEN): var-olmayan ``--sester-db`` yolu boş DB yaratıp
    verify_chain() boş zincirde True dönerdi → olmayan ledger GREEN idi.
    Düzeltme: yol-varlığı + ``SELECT COUNT(*) FROM events`` denetimi
    (boş/yok → RED).
  * RISK-2 (sahte-RED): ``Ledger(path)`` default-secret kullandığı için gerçek
    secret'la mühürlenmiş üretim ledger'ları sağlamken RED düşerdi.
    Düzeltme: ``--sester-secret`` / ``SESTER_LEDGER_SECRET`` (yanlış secret
    hâlâ RED — fail-closed). Dört durum kanıtlandı: yol-yok RED ·
    üretim-doğru-secret GREEN · üretim-secretsiz RED · eski-dev-ledger GREEN.

Cross-repo bacağı opsiyonel: ``SESTER_TAMGA_PATH`` Tamga checkout'una
işaret edildiğinde GERÇEK ``sovereign_verify.py`` koşulur; yoksa yalnızca
yüzey testleri koşar (CI'da SESTER-seti tek başına koşar).
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from sester.ledger import Ledger

ROOT = Path(__file__).resolve().parent.parent

# Kardeş-repo opsiyonel: SESTER_TAMGA_PATH Tamga checkout'una işaret ederse
# gerçek sarmalayıcı koşulur (test_bridges_crossrepo kalıbı).
TAMGA = os.environ.get("SESTER_TAMGA_PATH", "")
SOVEREIGN = os.path.join(TAMGA, "tools", "sovereign_verify.py")


def _scenario(db: Path, secret: str = "dev-secret") -> None:
    """Üç olaylı sağlam zincir — sarmalayıcının beklediği default-secret."""
    led = Ledger(str(db), secret=secret)
    led.append("usage_event", "ag-sv", host="h", amount=0.0025)
    led.append("charge_receipt", "ag-sv", host="h", amount=0.0025,
               payload={"nonce": "n1", "paid": 0.0025, "scheme": "pugio0"})
    led.append("permission_decision", "ag-sv", host="h", amount=0.0,
               payload={"decision": "allow"})
    led.close()


def _carve_amount(db: Path) -> None:
    """Zinciri yerinde kurcala — amount hash'e girdiği için zincir kırılır."""
    c = sqlite3.connect(str(db))
    try:
        c.execute("UPDATE events SET amount = 999.0 WHERE seq = 2")
        c.commit()
    finally:
        c.close()


def _wrapper_env() -> dict[str, str]:
    """Alt-süreçte sester import-edilebilsin diye repo-kökü PYTHONPATH'e."""
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(ROOT), existing) if p)
    return env


# -------------------------------------------- donuk-yüzey (her zaman koşar)

def test_202_wrapper_call_shape_single_arg_constructor(tmp_path):
    """Ledger(path) — secret'sız tek-posizyonel kurucu çalışmalı."""
    db = tmp_path / "sv.sqlite3"
    led = Ledger(str(db))  # secret YOK — sarmalayıcının çağrı şekli
    try:
        assert hasattr(led, "verify_chain")
        assert hasattr(led, "close")  # finally bloğu buna bağlı
    finally:
        led.close()
    assert db.is_file()


def test_203_clean_chain_verifies_green_and_close(tmp_path):
    """Sağlam zincir verify_chain() True + close() temiz kapanış."""
    db = tmp_path / "sv.sqlite3"
    _scenario(db)
    led = Ledger(str(db))
    try:
        assert led.verify_chain() is True
    finally:
        led.close()  # finally'de — sarmalayıcının kullandığı şekil


def test_204_tampered_chain_verifies_red(tmp_path):
    """Amount kazınınca verify_chain() False — kurcalama yakalanır."""
    db = tmp_path / "sv.sqlite3"
    _scenario(db)
    _carve_amount(db)
    assert Ledger(str(db)).verify_chain() is False


# ------------------------------------- cross-repo (SESTER_TAMGA_PATH opsiyonel)

pytestmark_crossrepo = pytest.mark.skipif(
    not os.path.isfile(SOVEREIGN),
    reason="Tamga checkout / tools/sovereign_verify.py bu makinede yok "
           "(SESTER_TAMGA_PATH ayarlanmadı)",
)


@pytestmark_crossrepo
def test_205_real_sovereign_wrapper_green(tmp_path):
    """Gerçek sovereign_verify.py --kind sester-ledger → GREEN (rc=0)."""
    db = tmp_path / "sv.sqlite3"
    _scenario(db)  # default-secret — sarmalayıcının beklediği şekil
    p = subprocess.run(
        [sys.executable, SOVEREIGN, "--kind", "sester-ledger",
         "--sester-db", str(db)],
        capture_output=True, text=True, timeout=90, env=_wrapper_env())
    assert p.returncode == 0, p.stdout[-400:] + p.stderr[-400:]
    r = json.loads(p.stdout[p.stdout.index("{"):])["results"][0]
    assert r["product"] == "sester"
    assert r["ok"] is True and r["verdict"] == "GREEN"


@pytestmark_crossrepo
def test_206_real_sovereign_wrapper_red_on_tamper(tmp_path):
    """Gerçek sarmalayıcı kurcalanmış zinciri RED görmeli (rc=1)."""
    db = tmp_path / "sv.sqlite3"
    _scenario(db)
    _carve_amount(db)
    p = subprocess.run(
        [sys.executable, SOVEREIGN, "--kind", "sester-ledger",
         "--sester-db", str(db)],
        capture_output=True, text=True, timeout=90, env=_wrapper_env())
    assert p.returncode == 1, p.stdout[-400:] + p.stderr[-400:]
    r = json.loads(p.stdout[p.stdout.index("{"):])["results"][0]
    assert r["product"] == "sester"
    assert r["ok"] is False and r["verdict"] == "RED"


def test_207_amount_minor_column_stays_outside_hash(tmp_path):
    """K0 erratum (2026-09-19): ``amount_minor`` yardımcı-kolonu canonical
    preimage'e GIRMEZ. Doğrudan değiştirilince verify_chain hâlâ SAĞLAM
    olmalı — çünkü sarmalayıcı SQLite'i doğrudan okur ve bağımsız bir
    doğrulayıcı hash'leri türetirken bu kuralı bilmek zorundadır. Yanlış
    kolonu hedefleyen bir kurcalama testi sessiz yeşile dönmesin diye bu
    yön de kilitli (negatif-kontrol; preimage-içi amount kazıma test_204
    ile RED'dir)."""
    db = tmp_path / "sv.sqlite3"
    _scenario(db)
    assert Ledger(str(db)).verify_chain() is True
    c = sqlite3.connect(str(db))
    try:
        c.execute("UPDATE events SET amount_minor = 123456 WHERE seq = 2")
        c.commit()
    finally:
        c.close()
    assert Ledger(str(db)).verify_chain() is True


def test_208_event_type_taxonomy_is_locked(tmp_path):
    """ERRATUM-K0.2: olay-tipi taksonomisi tek kaynak (``Ledger.EVENT_TYPES``
    + ``EVENT_TYPE_FAMILIES``). (a) SCHEMA yorumu kümenin TAMAMINI belgeler;
    (b) escalation ailesi (consumed dahil) ve facilitator ailesi kümede;
    (c) bilinmeyen tip ``append``'te RED — tükenmezlik suite ile kanıtlanır
    (bu satır bir üretim yolunu kırarsa taksonomi eksik demektir);
    (d) refund netting: charge_receipt +, refund −."""
    from sester.ledger import (EVENT_TYPE_FAMILIES, EVENT_TYPES, SCHEMA,
                               is_known_event_type)

    expected = {
        "usage_event", "charge_receipt", "refund", "permission_decision",
        "policy_denied", "escalation_parked", "escalation_approved",
        "escalation_denied", "escalation_consumed", "protocol_intent",
        "settlement", "webhook_delivery",
    }
    assert EVENT_TYPES == expected
    # (a) SCHEMA yorumu her tipi belgeler — ayrışma = kod/spec kayması
    assert all(v in SCHEMA for v in EVENT_TYPES)
    assert all(prefix in SCHEMA for prefix in EVENT_TYPE_FAMILIES)
    # (b) aileler: kapalı kind'lar bilinir, bogus kind bilinmez
    for kind in EVENT_TYPE_FAMILIES["facilitator_"]:
        assert is_known_event_type(f"facilitator_{kind}") is True
    assert is_known_event_type("facilitator_bogus") is False
    # (c) fail-closed: taksonomi dışı tip YAZILMAMALI (sessiz ayrışmayı önler)
    led = Ledger(str(tmp_path / "t208.sqlite3"), secret="t208")
    with pytest.raises(ValueError, match="bilinmeyen event_type"):
        led.append("sesterci_bilinmeyen", "ag-t")
    # (d) netting işareti: 0.10 charge − 0.03 refund = 0.07 net harcama
    led.append("charge_receipt", "ag-t", amount=0.10)
    led.append("refund", "ag-t", amount=0.03)
    led.close()
    assert abs(Ledger(str(tmp_path / "t208.sqlite3"), secret="t208")
               .spent_today("ag-t") - 0.07) < 1e-9
