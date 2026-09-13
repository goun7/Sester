# sikke 0.2.0 — Sürüm Notları (2026-09-12)

**Tek middleware, dört protokol-yolu, insan-onayı dahil.** SIKKE, AI-ajan
API'lerinize x402-tarzı ücretlendirme + kota + fail-closed politika takar;
0.2.0 ile protokol-nötr çekirdek taahhüdü kod-karşılığına kavuştu.

## Öne çıkanlar

### 1 · AP2 mandate + ACP checkout-session (K4)
- `AP2-Mandate <b64>` — kullanıcının ajana verdiği imzalı harcama-yetkisi:
  kaynak-önekleri, per-request üst-sınırı, para-birimi, zaman-penceresi.
- `ACP-Session <b64>` — satıcı checkout-oturumu: line_item kaynak/tutar
  birebir doğrulanır.
- İkisi de K0 `ChargeIntent`/`ChargeReceipt` çekirdeğine iner; **aynı cüzdan,
  protokoller-arası tek kota-sayacı**; mandate_id/session_id kalıcı
  replay-korumasına girer. JWS-imza doğrulaması v0.3 (alan-şartı şimdiden).

### 2 · İnsan-onay kuyruğu
- Politika `then: escalate` artık gerçek akış: istek 402
  `escalation_required:<bilet>` ile park edilir.
- Onay: `python -m sikke.escalation approve <id> --by sen` ya da
  `GET /escalations`. Onaylı bilet **bir-kez** tüketilir; TTL (15 dk)
  dolan bilet otomatik-RED — sessiz onay imkânsız.
- Her geçiş (park/approve/deny/consume) hash-chain'li ledger'a yazılır.

### 3 · Dayanıklılık (v0.1 → v0.2 serinin tamamı)
- Kalıcı replay-koruması (restart-atlamaz), integer minor-unit kota
  (float-tuzak kapalı), facilitator verify/settle (fail-closed), x402
  `exact` EIP-3009 zarfları, harici-doğrulanabilir kanıt-bundle'ları
  (pür-sha256 + Merkle), Tamga-çıpası ve Veridict claim/watch-feed köprüleri.

## Doğrulama
- **106 test** (pytest) — politika, ledger, şemalar, facilitator, adaptörler,
  eskalasyon, çapraz-repo köprüler.
- S1 dogfood kabul-koşusu + pür-stdlib harici-dogrulayıcı (`scripts/dogrula.py`).
- Sıfır zorunlu-bağımlılık çekirdek; `pip install sikke[evm]` imza-katmanı.

## Kurulum
```bash
pip install sikke           # çekirdek (saf ASGI, stdlib)
pip install "sikke[evm]"    # EVM-imza doğrulaması
pip install "sikke[demo]"   # demo API + panel
```

## Bilinen sınırlar (dürüst liste)
- AP2 JWS-imza doğrulaması, on-chain settle, Postgres ledger, policy-imzası:
  v0.3 yolunda (KARAR_63B §4).
- Escalation onayı şu an CLI/endpoint; panel-UI butonları v0.3.
