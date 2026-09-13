# PUGIO — Benimseme Günlüğü (KAGIT.md ölçüm-planı)

> Vitrin benimseme (kurulum → aktif-demo) haftalık takip. Kill-kriteri:
> 2-3 vitrin kurulumundan ≥2 aktif demo çıkmazsa → B-katmanı dondur
> (KAGIT.md operasyon-sözleşmesi).

| Tarih | Olay | Kanıt |
|---|---|---|
| 2026-09-12 | v0.1 prototip: kendi-demoda ilk mikro-ödeme kesildi (402→ödeme→receipt), kota-aşımı + fail-closed canlı doğrulandı | `KARAR_63B.md` §3, pugio-demo.sqlite3 (19 olay, zincir SAĞLAM) |
| 2026-09-12 | Test-seti 47 vektöre büyüdü (EVM-imza + EIP-3009 doz dahil) | `pytest tests/ -q` → 47 passed |
| 2026-09-12 | OSS paket-iskeleti: pugio-meter (PyPI boş-ad teyitli), Apache-2.0, CI | `pyproject.toml`, `.github/workflows/ci.yml` |
| 2026-09-12 | v0.1: EVM-imza canlı (ajan-kimliği = cüzdan-adresi, panelde 0xaaf3b12a… göründü) | canlı-akış: 402→Pugio-EVM→200+receipt `3658d614e9e52d23` |
| 2026-09-12 | **S1 KABUL:** F1-dogfood (günlük-$50-cap + saat-aralığı) deterministik koşu | `scripts/s1_dogfood.py` → 5 ✓ madde; bundle: `adoption/s1-kanit-bundle.json` |
| 2026-09-12 | 81-kanıt-köprüsü ilk-adım: alıcı kütüphanesiz doğruladı; inkâr-saldırısı yakalandı | `scripts/dogrula.py` → SAĞLAM; değiştirilmiş bundle → çıkış-1 |
| 2026-09-12 | Suite-köprüleri (K1 Tamga-çıpası + K2 Veridict-claim'leri) kodlandı; birleşme-kararı: ayrı-repo + köprü | `BIRLESTIRME_DEGERLENDIRMESI.md`, `pugio/bridges.py`, test_55–63 |
| 2026-09-12 | **v0.2 çekirdek:** KALICI replay-koruması (`seen_nonces`, restart-atlamaz), integer minor-unit kota (float-tuzak kapalı), facilitator verify→settle hattı (fail-closed, `settlement` olayı) | `pugio/ledger.py`, `pugio/middleware.py`, `pugio/facilitator.py`, test_64–73 |
| 2026-09-12 | **K0 ortak-kanıt-zarfı spec'i** yazıldı (canonical satır + proof-zinciri + Merkle + anchor + watch-feed, sürümlü, fail-loud) | `docs/K0_SHARED_ENVELOPE_SPEC.md` |
| 2026-09-12 | **Çapraz-repo köprüler canlı:** K1 alıcısı Tamga repo'suna (`tamga_pugio_receiver.py`), K3 üretici+alıcı Veridict repo'suna (`pugio/watchfeed.py` + `scripts/pugio_watch_receiver.py`) — pür stdlib, fail-loud, `--selftest`'li | test_74–81 subprocess uçtan-uca: temiz→SAĞLAM (exit 0), kazınmış→RED (exit 1) |
| 2026-09-12 | Suite 81 vektöre büyüdü (22 politika + 16 ledger/middleware + 12 EVM-şema + 7 kanıt + 16 v0.2 + 8 çapraz-repo) — hepsi yeşil | `pytest tests/ -q` → 81 passed |
| 2026-09-12 | **K4 protokol-adaptörleri:** AP2 mandate + ACP checkout-session → ChargeIntent/ChargeReceipt; ortak-cüzdan tek-kota (aynı cüzdan AP2+ACP tek sayaçta) | `pugio/adapters.py`, test_82–95 |
| 2026-09-12 | **İnsan-onay kuyruğu:** escalate → park/approve/deny/consume; bir-kezlik tüketim + TTL fail-closed + tam ledger-denetim-izi; CLI + GET /escalations | `pugio/escalation.py`, test_96–106 |
| 2026-09-12 | **v0.2.0 hazırlık:** sürüm-bump, CHANGELOG, sürüm-notları; wheel+sdist inşa-edildi (PyPI yayını kullanıcı-kararı) | `CHANGELOG.md`, `docs/RELEASE_NOTES_v0.2.0.md`, `dist/pugio_meter-0.2.0-*` |
| 2026-09-12 | Üç-repo CI işi: kardeş-repo variable'larıyla etkinleşen bridges-job (K1+K3 + selftest'ler) | `.github/workflows/ci.yml` |
| 2026-09-12 | Suite **106 vektöre** büyüdü (… + 14 protokol-adaptör + 11 eskalasyon) — hepsi yeşil | `pytest tests/ -q` → 106 passed |
| 2026-09-12 | **AP2 JWS-imzası:** HS256 (stdlib) + ES256; gövde-bağı scope-kazımayı öldürür; alg-none fail-closed | `pugio/adapters.py`, test_108–117 |
| 2026-09-12 | **S3 KABUL:** imzalı politika + 24s gevşetme-gate; sıkılaştırma-anında, gevşetme-gecikmeli, pending-sızıntı-yok | `pugio/policy_signed.py`, test_118–128 |
| 2026-09-12 | **Onay-paneli:** /approvals (Pugio-Tally marka) + decide-endpoint (404/409/400 fail-loud) | `pugio/panel.py`, `pugio/demo_api.py`, test_129–135 |
| 2026-09-12 | **S4 KAPANDI:** 81-tarafı yerel bundle-okuyucu Tamga repo'sunda — deterministik doğrulama-makbuzu; inkâr-saldırısı makbuz-üretimsiz RED | `tamga_pugio_ingest.py`, test_136–140 |
| 2026-09-12 | **Postgres backend:** birebir Ledger-arayüzü; aynı secret+olaylar+ts → SQLite/PG özdeş zincir; PG-bundle pür-stdlib doğrulayıcıdan geçer | `pugio/pg_ledger.py`, test_141–145 |
| 2026-09-12 | Suite **145 vektöre** büyüdü — hepsi yeşil (PG-parite dahil, ephemeral Docker PG ile) | `pytest tests/ -q` → 145 passed |
| 2026-09-12 | **ACP satıcı-ucu:** `issue_acp_session` imzalı oturum-üretimi + üretim-bayrağı; test-önce süreci JWS gövde-bağı boşluğunu yakaladı (güvenlik-düzeltmesi) | `pugio/adapters.py`, test_146–152 |
| 2026-09-12 | **Migrasyon-aracı:** SQLite→PG hash-koruyan replay; zincir yeniden-üretilmez, nonce-penceresi korunur, idempotent | `pugio/migrate_pg.py`, test_153–158 |
| 2026-09-12 | **SPEC_FARK v3:** UCP (4. oyuncu) + katman-modeli teyidi — adaptör-tezi 4. kez doğrulandı; öncelikler değişmedi, UCP izlemede | `SPEC_FARK_TABLOSU.md` §0/§5 |
| 2026-09-12 | **Yayın-dry-run tamam:** twine PASSED (wheel+sdist), temiz-venv smoke (sıfır-zorunlu-bağımlılık), checklist hazır — gerçek-yayın kullanıcı-kararı | `docs/PUBLICATION_CHECKLIST.md`, `dist/pugio_meter-0.3.1-*` |
| 2026-09-12 | Suite **158 vektöre** büyüdü — hepsi yeşil | `pytest tests/ -q` → 158 passed |
