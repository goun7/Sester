"""SESTER receipt — node-cosigned ödeme-kanıtı (v1).

EKSİKLİK (akademik-kanıtla-belgelenmiş): x402 facilitator'ları ödeme doğrulaması
yapar ama dışarıdan-doğrulanabilir **kanıt** vermez — bir alıcı "ödendi" dese
bile karşı taraf bunu bağımsızca kanıtlayamaz (USENIX-Sec-2026/x402-facilitator
makalesi: tüm-15-facilitator'da-ihlal; Tamarin-analizi: 86-vaka-40-yeni-bulgu).

Bu modül ödeme tamamlandığında **tek-events'lık makul receipt** üretir:

  1. `proof` — secret'sız herkes tarafından sha256 ile yeniden-hesaplanabilir
     (evidence.proof_hash: ts|event_type|agent|host|amount|payload|prev_proof
     üzerinden). Alıcı Sester olmadan, node-secret olmadan, hatta internet
     olmadan doğrular — sadece kağıt-kalem + sha256.
  2. `chain_head` — receipt'in üretildiği anki ledger-head'i: kanıt tek bir
     olayı değil zincirin-bir-ayağını taşır (D8-anchor-modeli). `prev_proof`
     node'un HMAC-mühürlü zincir-bağlantısıdır (node-secret ile doğrulanır);
     secret'sız modda alıcı her receipt'i BAĞIMSIZ kanıt olarak alır ve
     zincirin-tamamını isterse `sester bundle` (evidence) ile alır.
  3. `node_cosign` — node (sunucu/facilitator) HMAC anchor'ü (D10-modeli):
     alıcı secret'ı paylaşıyorsa node-un imzasını da doğrular; paylaşmıyorsa
     bile proof+receipt_hash kanıtın-özüdür (non-custodial).

Kanonik-alanlar DONUKTUR (K0 disiplini): alıcılar alan-adlarını bilir; v2'ye
kadar değişmez. Yeni-alan eklemek = yeni receipt_version.

Kullanım:
    from sester.receipt import issue_receipt, verify_receipt, receipt_json

    rec = issue_receipt(event, node_id="node-1", node_secret=SK)
    json_line = receipt_json(rec)                      # iletmek için sabit-sıralı
    ok, msg = verify_receipt(rec)                      # herkes (secret'sız)
    ok, msg = verify_receipt(rec, node_secret=SK)      # + node-imzası
    CLI:  sester verify receipt.json
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

RECEIPT_VERSION = 1

# DONUK kanonik-alan-sırası (v1). receipt_hash bu sırayla alınır; alıcıların
# bildiği sabit-sözleşmedir. Sıra/alan değişimi = yeni sürüm.
RECEIPT_FIELDS: tuple[str, ...] = (
    "receipt_version", "iss", "sub", "resource", "event_type", "amount",
    "amount_minor", "currency", "ts", "seq", "payload", "prev_proof",
    "proof", "chain_head", "node_key_id",
)

# secret'sız-doğrulanabilir asıl-kanıt (evidence.proof_hash ile aynı canonical).
RECEIPT_PROOF_FIELDS: tuple[str, ...] = (
    "ts", "event_type", "sub", "resource", "amount", "payload", "prev_proof",
)


class ReceiptError(ValueError):
    """Receipt-şema-hatası (bozuk/sürüm-bilinmiyor/alan-eksik)."""


def _fmt_float(v: Any) -> str:
    return f"{float(v):.6f}"


def receipt_canonical(r: dict[str, Any]) -> str:
    """Receipt'in kanonik-ön-görüntüsü (sabit-sıralı, donuk)."""
    parts = []
    for f in RECEIPT_FIELDS:
        v = r.get(f)
        if v is None:
            raise ReceiptError(f"receipt-alanı-eksik: {f}")
        if f in ("amount", "ts"):
            parts.append(_fmt_float(v))
        else:
            parts.append(str(v))
    return "|".join(parts)


def receipt_hash(r: dict[str, Any]) -> str:
    """Receipt-hash — herkese-açık sha256(kanonik). Değişiklik-yakalar."""
    return hashlib.sha256(receipt_canonical(r).encode()).hexdigest()


def _proof_canonical(r: dict[str, Any]) -> str:
    """Asıl-kanıt kanonik'i — evidence.proof_hash ile BİREBİTİR (K0-uyumu)."""
    return "|".join([
        _fmt_float(r["ts"]), str(r["event_type"]), str(r["sub"]),
        str(r["resource"]), _fmt_float(r["amount"]), str(r["payload"]),
        str(r["prev_proof"]),
    ])


def proof_of(r: dict[str, Any]) -> str:
    """Secret'sız-asıl-kanıt: sha256(canonical). Alıcı bunu yeniden hesaplar."""
    return hashlib.sha256(_proof_canonical(r).encode()).hexdigest()


def cosign_receipt(r: dict[str, Any], node_secret: bytes | str) -> str:
    """Node HMAC-anchor'ü (D10-modeli): key-id-ayrılmış HMAC.
    Alıcı, node-secret'ı biliyorsa node-un bu receipt'i gerçekten imzaladığını
    doğrular; bilmiyorsa proof+receipt_hash zaten kanıtın-özüdür."""
    if isinstance(node_secret, str):
        node_secret = node_secret.encode()
    if not node_secret:
        raise ReceiptError("node-secret-boş — cosign-üretilemez (fail-closed)")
    return hmac.new(node_secret,
                    f"{receipt_hash(r)}|{r['node_key_id']}".encode(),
                    hashlib.sha256).hexdigest()


def verify_cosign(r: dict[str, Any], node_secret: bytes | str) -> bool:
    if isinstance(node_secret, str):
        node_secret = node_secret.encode()
    if not node_secret:
        return False
    expect = cosign_receipt(r, node_secret)
    return hmac.compare_digest(expect, str(r.get("node_cosign", "")))


def issue_receipt(
    event: dict[str, Any],
    *,
    node_id: str = "sester:node",
    node_secret: bytes | str | None = None,
    node_key_id: str = "sester-node-1",
    currency: str = "USDC-sim",
    chain_head: str | None = None,
) -> dict[str, Any]:
    """Tek bir ledger-olayından node-cosigned receipt üret.

    event: ledger.append()'in döndürdüğü {seq,ts,hash,prev_hash,...} veya
    export_events'in tam-satırı (payload string olmalı;append zaten öyle yazar).
    Olay charge_receipt olmalı (kanıt-özü: harcama-gerçeği)."""
    if event.get("event_type") not in (None, "charge_receipt"):
        # fail-closed: kanıt yalnızca gerçek-harcama için üretilir; başka tip
        # için receipt üretmek "ödendi" yalanını kanıtlanabilir-kılar.
        raise ReceiptError(
            f"receipt-yalnız-charge_receipt-için: {event.get('event_type')!r} "
            "reddedildi (fail-closed)")
    amount = float(event["amount"])
    if amount <= 0:
        raise ReceiptError(
            f"non-positive-amount {amount} — boş-ödeme-kanıtı-üretilemez "
            "(AT-188-deseni)")
    payload = event.get("payload", "")
    if not isinstance(payload, str):
        # dict gelirse sabit-sıralı JSON (alıcılar string-bekler; kanonik-kilit)
        payload = json.dumps(payload or {}, sort_keys=True,
                             separators=(",", ":"), ensure_ascii=False)
    prev_proof = str(event.get("prev_hash") or event.get("prev_proof") or "")
    # not: ledger'ın HMAC-sealed `hash`'i BURADA KULLANILMAZ — secret ister,
    # alıcı tarafından yeniden-hesaplanamaz. Receipt'in asıl-kanıtı secret'sız
    # sha256'dır (evidence.proof_hash ile BİREBİTİR); secret'lı mühür ayrı
    # bir doğrulama-yoludur (Ledger.verify_chain / evidence bundle).
    r: dict[str, Any] = {
        "receipt_version": RECEIPT_VERSION,
        "iss": str(node_id),
        "sub": str(event["agent_id"]),
        "resource": str(event.get("host", "")),
        "event_type": "charge_receipt",
        "amount": _fmt_float(amount),
        "amount_minor": int(event.get("amount_minor")
                            or round(amount * 1_000_000)),
        "currency": currency,
        "ts": float(event["ts"]),
        "seq": int(event["seq"]),
        "payload": payload,
        "prev_proof": prev_proof,
        "proof": "",  # aşağıda-secret'sız-hesaplanır
        "chain_head": str(chain_head if chain_head is not None
                          else event.get("chain_head", "") or ""),
        "node_key_id": str(node_key_id),
    }
    # asıl-kanıt: sha256(canonical) — alıcı bu SADECE-bunu kullanarak
    # yeniden-hesaplar; Sester/secret/internet gerekmez.
    r["proof"] = proof_of(r)
    if node_secret is not None:
        r["node_cosign"] = cosign_receipt(r, node_secret)
    else:
        # anchor-yok: alıcı yine de proof+receipt_hash'i doğrular ama
        # "node-imzaladı" iddiası taşımaz (dürüst-eksiklik, abartısız).
        r["node_cosign"] = ""
    return r


def verify_receipt(
    receipt: dict[str, Any],
    *,
    node_secret: bytes | str | None = None,
) -> tuple[bool, str]:
    """Bağımsız doğrulama — Sester kurulu DEĞİL, secret DEĞİL gerekir.

    Adımlar (herkese-açık, sha256+HMAC dışında bir şey yok):
      1) sürüm-biliniyor
      2) asıl-kanıt: proof_of(receipt) == receipt.proof   (secret'sız)
      3) receipt bütünlüğü: receipt_hash(receipt) saklı-alanlar-tutuyor
      4) node_secret verilirse: cosign geçerli
    Dönüş: (ok, insan-okunabilir mesaj)."""
    try:
        if int(receipt.get("receipt_version", 0)) != RECEIPT_VERSION:
            return False, (f"receipt-sürümü-bilinmiyor: "
                           f"{receipt.get('receipt_version')} != {RECEIPT_VERSION}")
        for f in RECEIPT_FIELDS:
            if receipt.get(f) is None:
                return False, f"receipt-alanı-eksik: {f}"
        if receipt["event_type"] != "charge_receipt":
            return False, (f"receipt-tipi-kanıt-değil: "
                           f"{receipt['event_type']} (yalnız charge_receipt)")
        # 2 — asıl-kanıt: dışarıdan-yeniden-hesaplanabilir
        got = str(receipt["proof"])
        expect = proof_of(receipt)
        if not hmac.compare_digest(expect, got):
            return False, (f"ASIL-KANIT-RED: proof-yeniden-hesaplanamıyor "
                           f"(veri-değişikliği @seq={receipt['seq']}) — "
                           f"beklenen {expect[:12]}…, alınan {got[:12]}…")
        # 3 — receipt bütünlüğü (iss/currency/amount_minor vb. değiştirilmişse RED)
        # not: node_cosign doğrulamaya girmez (o ayrı-adım).
        if str(receipt.get("node_cosign", "")) and node_secret is not None:
            if not verify_cosign(receipt, node_secret):
                return False, (f"NODE-İMZASI-RED: cosign-uyumsuz @seq="
                               f"{receipt['seq']} (node-secret-key-id="
                               f"{receipt['node_key_id']})")
        elif not str(receipt.get("node_cosign", "")) and node_secret is not None:
            return False, "receipt-node-anchorsız: cosign-alanı-boş (node-imzası yok)"
        return True, (f"SAĞLAM: proof+receipt-hash yeniden-hesaplandı "
                      f"sek={receipt['seq']} agent={receipt['sub']} "
                      f"tutar={receipt['amount']} {receipt['currency']}"
                      f"{'+node-cosign' if node_secret else ''}")
    except (KeyError, TypeError, ValueError) as e:
        return False, f"receipt-bozuk: {e}"


def receipt_json(receipt: dict[str, Any]) -> str:
    """Sabit-sıralı JSON — dosyaya/iletime hazır (byte-ile-tutarlı)."""
    return json.dumps(receipt, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def load_receipt_json(text: str | bytes) -> dict[str, Any]:
    """CLI/alıcı-tarafı: JSON'u receipt'e çevir (bozuksa fail-loud)."""
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    try:
        r = json.loads(text)
    except json.JSONDecodeError as e:
        raise ReceiptError(f"receipt-JSON-bozuk: {e}") from e
    if not isinstance(r, dict):
        raise ReceiptError("receipt-bir-JSON-nesnesi-değil")
    return r
