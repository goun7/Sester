# SESTER — Ajan Ticaret Yığını · B-katmanı (AgentMeter) v0.5.0

![CI](https://github.com/goun7/sester/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-Apache--2.0-gold)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-informational)
![Deps](https://img.shields.io/badge/forced%20deps-0-success)

<p align="center"><img src=".github/assets/og.svg" alt="SESTER — metering · policy · evidence" width="640"></p>

> 🪙 "Ajanınız ödeyecekse, kuralları siz koyarsınız."
> x402-uyumlu sayaç + kota + fail-closed politika + hash-chain kanıt-defteri +
> facilitator (verify/settle) — tek ASGI middleware. Kâğıt: `KAGIT.md` · `PRD.md` · karar: `KARAR_63B.md`.

## 3 dakikada demo

```bash
# 1) Sunucu (port 8402)
uvicorn sester.demo_api:app --port 8402

# 2) Ödemeyi hazırla (mac üretici)
python -m sester.demo_api --mac f1-telemetri:n1:0.05 /weather

# 3) Ödemeli isteği at (üstteki çıktıyı yapıştır)
curl -H "X-Sester-Agent: f1-telemetri" -H "X-Payment: pugio0 f1-telemetri:n1:0.05:<mac>" \
  "http://127.0.0.1:8402/weather?sehir=istanbul"

# 4) Paneli aç: http://127.0.0.1:8402/panel
```

Akış: `curl` ödemeden atarsa **402 + X-Payment-Required challenge**; ödemeyle
**200 + X-Sester-Receipt** kanıt-başlığı; 5. çağrıda **kota-aşımı 402**;
`/panel`de kim-kaç-çağrı-ne-kadar + zincir-bütünlüğü rozeti.

## Testler + kabul-koşuları

```bash
.venv/bin/python -m pytest tests/ -q      # 181 vektör (158 + UCP 8 + settlement 8 + minör-birim 7):
                                      # politika(22) + ledger/middleware(16)
                                      # + EVM-şema(12) + kanıt(7) + facilitator/v0.2(16) + köprü(8)
                                      # + protokol-adaptör(14) + eskalasyon(11) + JWS(10)
                                      # + imzalı-politika(11) + onay-panel(7) + 81-ingest(5) + PG-parite(5)
                                      # + ACP-satıcı(7) + migrasyon(6) + UCP(8) + settlement(8) + minör-birim(7)
python scripts/s1_dogfood.py          # S1 kabul-senaryosu (IS_PLANI §7) → KABUL
python scripts/dogrula.py adoption/s1-kanit-bundle.json   # alıcı-tarafı, sester'suz
```

> Not: `tests/test_bridges_crossrepo.py` kardeş-repo alıcılarını subprocess ile
> uçtan-uca koşar (temiz→SAĞLAM, kazınmış→RED); kardeş-repo yoksa otomatik atlanır.

## Kimlik + kanıt (v0.2)

- **Ödeme-şemaları:** `exact-sester` (EIP-191: ajan-kimliği = cüzdan-adresi) +
  `pugio0` HMAC geri-uyumu (DONUK kablo-alanı — ESKI_KIMLIK.md) + x402 v2 `exact` (EIP-3009/EIP-712) zarfı
  (`sester/schemes.py`); şema-kaydı `register_scheme` ile açılır —
  ProtocolAdapter noktası.
- **Settlement (v0.2):** `sester/facilitator.py` — x402 v2 verify → handler →
  settle → `settlement` olayı; transport enjekte-edilebilir (test-fake);
  **fail-closed:** facilitator yok/erişilemez → 402, settle-düşüşü sessiz-kalmaz.
- **Replay + kota (v0.2):** nonce'lar ledger `seen_nonces` tablosunda **kalıcı**
  (restart-atlamaz); kota-kararı **integer minor-unit** (float-hatasız).
- **81-kanıt-köprüsü:** `sester/evidence.py` — bundle üret; alıcı
  `scripts/dogrula.py` ile **kütüphanesiz, pür sha256** doğrular;
  işlem-inkârı proof-uyuşmazlığıyla yakalanır.
- **Protokol-adaptörleri (v0.2.0, K4):** `sester/adapters.py` — AP2 mandate
  (`AP2-Mandate <b64>`) + ACP checkout-session (`ACP-Session <b64>`) → K0
  `ChargeIntent`/`ChargeReceipt` çekirdeği; **ortak-cüzdan tek-kota**: aynı
  cüzdanın AP2+ACP harcaması tek sayaçta birleşir; mandate_id/session_id
  kalıcı replay-korumasına girer.
- **İnsan-onay kuyruğu (v0.2.0):** `sester/escalation.py` — politika
  `then: escalate` → 402 `escalation_required:<bilet>`; onay:
  `python -m sester.escalation approve <id> --by sen`, `GET /escalations`
  veya **`/approvals` onay-paneli** (v0.3: tek-tık onayla/reddet butonları);
  onay **bir-kez** tüketilir, TTL (15 dk) dolan bilet otomatik-RED
  (fail-closed); her geçiş ledger'a olay olarak yazılır.
- **AP2 JWS-imzası (v0.3, RFC 7515):** mandate-imzası kriptografik doğrulanır —
  HS256 (stdlib) + ES256 (`[jws]` extra); `key_resolver` üretimde şart;
  gövde-bağı (`expected_body`) scope-kazımayı öldürür; alg-allowlist
  (`none` → fail-closed).
- **İmzalı politika + 24s gevşetme-gate (v0.3, S3):** `sester/policy_signed.py`
  — JWS-mühürlü politika zarfları; sıkılaştırma anında, gevşetme 24 saat
  gecikmeli (KURAL_DSL §3); bekleyen gevşetme kararlara sızmaz; bozuk zarf
  son-iyi-durumu korur, fail-closed.
- **Postgres backend (v0.3):** `sester/pg_ledger.py` — birebir Ledger-arayüzü;
  ortak hash-chain çekirdeği: aynı secret+olaylar+ts → SQLite/PG **özdeş
  zincir**; PG-bundle pür-stdlib doğrulayıcıdan geçer; `[pg]` extra.
- **81-tarafı bundle-okuyucu (v0.3, S4-kapanış):** Tamga repo'sunda
  `tamga_pugio_ingest.py` — K0 bundle'ını kütüphanesiz doğrular +
  deterministik doğrulama-makbuzu üretir; inkâr-saldırısı/başlık-yalanı →
  makbuz ÜRETİLMEZ (fail-closed).
- **ACP satıcı-ucu (v0.3.1):** `issue_acp_session()` — satıcı, imzalı
  `ACP-Session` zarfı üretir (JWS); `require_signature` üretim-bayrağı
  imzasız eski-zarfı fail-closed ret eder.
- **UCP web-monetization (v0.4):** `issue_ucp_checkout()` / `verify_ucp_checkout()` —
  dördüncü protokol tek-çekirdekte (`UCP-Checkout <b64>`); satıcı-mührü JWS,
  merchant-bağı (manifest-sahteliği kapanır), `require_ucp_signature` üretim-bayrağı.
- **On-chain settlement-batch (v0.4):** `sester/settlement.py` — püür-stdlib
  keccak-256 (bilinen-vektör-testli), K0 kanıt-proof'larından keccak-merkle kökü
  (EVM'de yeniden-hesaplanabilir), ABI `settle(...)` calldata; chain/contract-bağı
  batch-digest'inde. Tx-imzalama bilinçli-dışı — non-custodial tez.
- **Minör-birim kolonu (v0.4):** `amount_minor` (SQLite+PG; idempotent-göç +
  hash-koruyan backfill) — kota-kararı uçtan-uca tam-sayı; `canonical_line` donmuş
  kaldığı için zincir-hash'leri değişmez (K0 korunur, eski-zincir göçeder).
- **SQLite→PG migrasyonu (v0.3.1):** `python -m sester.migrate_pg` —
  hash-koruyan replay (zincir yeniden-üretilmez), nonce-penceresi korunur,
  idempotent, `--plan/--dry-run/--verify` modları, bozuk-kaynak ret.
- **Suite-köprüleri (birleşme-değil-bağlama):** `sester/bridges.py` +
  `sester/watchfeed.py` — K1 Tamga-çıpası, K2 Veridict-claim'leri, K3 watch-feed.
  Alıcılar kardeş-repolarda bağımsız stdlib-script: Tamga `tamga_pugio_receiver.py`,
  Veridict `scripts/pugio_watch_receiver.py`. Ortak sözleşme:
  `docs/K0_SHARED_ENVELOPE_SPEC.md`. Karar: `BIRLESTIRME_DEGERLENDIRMESI.md`.

## Haritalama (kâğıt → kod)

| Kâğıt | Kod |
|---|---|
| KURAL_DSL_V0 §2 semantiği | `sester/policy.py` (ilk-eşleşen, fail-closed, DenyAll) |
| KURAL_DSL `then: escalate` | `sester/escalation.py` (park→approve/deny→consume, TTL fail-closed) + `/approvals` paneli |
| KURAL_DSL §3 değişim-yönetimi (S3) | `sester/policy_signed.py` (JWS-mühür + 24s gevşetme-gate) |
| 63-A ChargeIntent/ChargeReceipt tezi | `sester/adapters.py` (AP2 mandate + ACP session + UCP checkout → çekirdek, JWS-imzalı) |
| SPEC_FARK v3 UCP (4. oyuncu) | `sester/adapters.py` (`UCP-Checkout`, merchant-bağı) |
| PRD on-chain-kesinlik (v0.4) | `sester/settlement.py` (keccak-merkle + ABI settle-calldata) |
| PRD §4 çoklu-backend | `sester/pg_ledger.py` (Postgres, özdez-zincir parite-seti) |
| PRD §4 "ledger: tamga hash-chain" | `sester/ledger.py` (prev_hash + HMAC-seal, `verify_chain`) |
| PRD §2 hafta 1–2 (x402 + kota + panel) | `sester/middleware.py` + `sester/panel.py` |
| IS_PLANI §7 S4 (81 köprüsü) | `sester/evidence.py` + `scripts/dogrula.py` |
| BİRLEŞTİRME §3 K0/K1/K2/K3 | `docs/K0_SHARED_ENVELOPE_SPEC.md` + `sester/bridges.py` + `sester/watchfeed.py` + kardeş-repo alıcıları |
| IS_PLANI §7 S5+S6 (hosted-facilitator) | `sester/facilitator_svc/` + `docs/S6_JOINT_ACCEPTANCE.md` + 64-tarafı harita (`64-Tenderix/docs/internal/S6_ORTAK_KABUL_TENDERIX.md`) |
| IS_PLANI §9 demo-script | `README` 3-dakika + `python -m sester.demo_api --mac` |

## Bilinçli v0-sınırlar

`KARAR_63B.md` §4 — ~~escalate-kuyruğu~~ ✅ v0.2.0, ~~AP2/ACP adaptörleri~~ ✅ v0.2.0,
~~AP2 JWS~~ ✅ v0.3.0, ~~policy-imzası + 24s gevşetme~~ ✅ v0.3.0, ~~Postgres~~ ✅ v0.3.0,
~~ACP satıcı-oturum-açma~~ ✅ v0.3.1, ~~minor-unit kolon-göçü~~ ✅ v0.4.0,
~~on-chain batch-üretici~~ ✅ v0.4.0; kalan: tx-imzalama (bilinçli-dışı — imzalayıcı
tarafı), UCP/ACP canlı-trafik sertleşmesi; PyPI yayını kullanıcı-kararı (wheel+sdist
hazır: `dist/sester-0.5.0-*`).
