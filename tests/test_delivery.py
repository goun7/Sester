"""Delivery attestation testleri — x402 #1195 SAR.

LEAD 2026-10-01: self-attestation kapatildi, failed verdict yazilir,
charge_receipt payload'ina baglanir (yeni event-type YOK).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from sester.delivery import (  # noqa: E402
    ATTESTOR_SELLER,
    DELIVERY_KEY,
    DeliveryReceipt,
    attested_receipt,
    content_hash_of,
    extract_delivery,
)
from sester.ledger import Ledger  # noqa: E402


class TestDeliveryReceipt:
    def test_gecerli_delivered(self):
        r = attested_receipt("d1", "delivered", "oracle-1", proof_ref="pr/1")
        assert r.verdict == "delivered"
        p = r.as_payload()
        assert p["delivery_id"] == "d1"
        assert p["proof_ref"] == "pr/1"
        assert "content_hash" not in p  # content yok

    def test_bos_id_reddedilir(self):
        with pytest.raises(ValueError, match="bos delivery_id"):
            DeliveryReceipt("", 1.0, "delivered", "a")

    def test_gecersiz_verdict_reddedilir(self):
        with pytest.raises(ValueError, match="gecersiz verdict"):
            attested_receipt("d2", "maybe", "oracle-1", proof_ref="x")

    def test_satici_self_attestation_reddedilir(self):
        """#1195: 'trusts the agent self-report' KAPALI — proof_ref sart."""
        with pytest.raises(ValueError, match="self-attestation"):
            attested_receipt("d3", "delivered", ATTESTOR_SELLER)

    def test_satici_oracle_ile_gecerli(self):
        r = attested_receipt("d4", "delivered", ATTESTOR_SELLER,
                             proof_ref="github.com/x/y/pull/7")
        assert r.proof_ref == "github.com/x/y/pull/7"

    def test_failed_verdict_gecerli(self):
        """#2332 (aeoess): basarisiz teslimat da kaydedilir (sessiz degil)."""
        r = attested_receipt("d5", "failed", "oracle-1", proof_ref="probe")
        assert r.verdict == "failed"
        assert r.as_payload()["verdict"] == "failed"

    def test_partial_verdict_gecerli(self):
        r = attested_receipt("d6", "partial", "oracle-1")
        assert r.verdict == "partial"

    def test_content_hash_gizli(self):
        """content_hash icerigi aciklamaz (sha256)."""
        r = attested_receipt("d7", "delivered", "oracle-1",
                             content=b"yanit-govdesi", proof_ref="x")
        assert r.content_hash == content_hash_of(b"yanit-govdesi")
        assert len(r.content_hash) == 64  # sha256 hex
        # payload'da icerigin KENDISI yok
        assert "yanit-govdesi" not in str(r.as_payload())


class TestExtractDelivery:
    def test_yoksa_none(self):
        assert extract_delivery(None) is None
        assert extract_delivery({"amount_minor": 50000}) is None

    def test_varsa_donar(self):
        p = {"amount_minor": 50000,
             DELIVERY_KEY: {"delivery_id": "d8", "verdict": "delivered"}}
        d = extract_delivery(p)
        assert d["delivery_id"] == "d8"

    def test_yanlis_tip_none(self):
        assert extract_delivery({DELIVERY_KEY: "string"}) is None


class TestLedgerEntegrasyon:
    """Delivery, charge_receipt payload'ina baglanir (yeni event YOK)."""

    def test_delivery_charge_receipt_e_baglanir(self, tmp_path):
        led = Ledger(str(tmp_path / "del.sqlite3"), secret="k")
        try:
            r = attested_receipt("d9", "delivered", "oracle-2",
                                 proof_ref="probe-x")
            payload = {"amount_minor": 50000, "currency": "USDC",
                       DELIVERY_KEY: r.as_payload()}
            led.append("charge_receipt", "agent-z", "/api/y", 0.05,
                       payload=payload)

            import sqlite3
            conn = sqlite3.connect(str(tmp_path / "del.sqlite3"))
            try:
                rows = conn.execute(
                    "SELECT payload FROM events WHERE event_type='charge_receipt'"
                ).fetchall()
            finally:
                conn.close()
            import json
            p = json.loads(rows[0][0])
            assert p[DELIVERY_KEY]["delivery_id"] == "d9"
            assert p[DELIVERY_KEY]["verdict"] == "delivered"
            led.verify_chain()
        finally:
            led.close()
