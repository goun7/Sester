# KARAR_63B — PUGIO B-katmanı (AgentMeter) Prototip Kararı

> Tarih: 2026-09-12 · Durum: **v0.3.1 kodlandı, 158/158 test yeşil + S1–S4 KABUL + yayın-dry-run tamam** · Üst: `PRD.md` sürüm-tablosu
> Kapsam: PRD hafta-1 + hafta-2 çıktıları (x402 el sıkışması + ledger + kota + panel)
> ve hafta-3'ün DSL-çekirdeği (v0 alt-kümesi) tek vitrinde.
> **v0.1 eklentiler:** EVM-imza (exact-pugio) + x402 exact doz-şekli (EIP-3009/EIP-712),
> şema-kayıt-Registry'si, OSS paketi (pugio-meter), S1 dogfood-kabul-koşusu,
> 81-kanıt-köprüsü (pür-sha256 harici-doğrulanabilir bundle + Merkle).
> **v0.2 eklentiler:** facilitator verify/settle hattı (x402 v2 `exact` → `settlement`
> olayı, fail-closed), KALICI replay-koruması (`seen_nonces` tablosu — restart-atlamaz),
> integer minor-unit kota-aritmetiği (float-hatası imha), K0 ortak-kanıt-zarfı spec'i
> (`docs/K0_SHARED_ENVELOPE_SPEC.md`), K3 watch-feed üreticisi (`pugio/watchfeed.py`)
> + kardeş-repo alıcıları (Tamga `tamga_pugio_receiver.py`, Veridict
> `scripts/pugio_watch_receiver.py`) — çapraz-repo testleriyle (test_74–81).
> **v0.2.0 eklentiler:** K4 protokol-adaptörleri — AP2 mandate (`AP2-Mandate`)
> + ACP checkout-session (`ACP-Session`) → ChargeIntent/ChargeReceipt çekirdeği,
> ortak-cüzdan tek-kota (`pugio/adapters.py`, test_82–95); insan-onay kuyruğu —
> park→approve/deny→bir-kezlik consume, TTL fail-closed, tam ledger-denetim-izi
> (`pugio/escalation.py`, test_96–106); wheel+sdist inşa (0.2.0), üç-repo CI işi
> (kardeş-repo variable'larıyla etkinleşir).
> **v0.3.0 eklentiler:** AP2 JWS-imza-doğrulaması (RFC 7515: HS256/ES256,
> key_resolver, gövde-bağı — test_108–117); imzalı politika + 24s gevşetme-gate
> (S3: `pugio/policy_signed.py`, test_118–128); /approvals onay-paneli +
> decide-endpoint (test_129–135); 81-tarafı yerel bundle-okuyucu
> (S4-kapanış: Tamga repo'sunda `tamga_pugio_ingest.py`, test_136–140);
> Postgres backend (birebir Ledger-arayüzü, özdez-zincir parite-seti —
> `pugio/pg_ledger.py`, test_141–145).
> **v0.3.1 eklentiler:** ACP satıcı-ucu — `issue_acp_session` (imzalı oturum-
> üretimi) + `require_signature` üretim-bayrağı (test_146–152); SQLite→PG
> hash-koruyan migrasyon-aracı (`pugio/migrate_pg.py`, --plan/--dry-run/--verify,
> test_153–158); JWS gövde-bağı genelleştirildi — TÜM zarf-alanları bağlı
> (test_148'in yakaladığı ACP-kazıma boşluğu kapandı); SPEC_FARK v3 (dördüncü
> oyuncu UCP + katman-modeli teyidi — adaptör-tezi 4. kez doğrulandı);
> yayın-dry-run (twine PASSED, temiz-venv smoke, sıfır-zorunlu-bağımlılık).

## 2a) v0.3.1 güvenlik-notu

`verify_mandate_jws` expected_body-bağı v0.3.0'da yalnız AP2 alan-listesiydi;
ACP zarfının `line_item`'ı bağlı değildi → kazınmış gövde + geçerli-imza
geçebiliyordu. test_148 (satıcı-ucu kazıma senaryosu) açtı; bağ TÜM zarf-
alanlarına genellendi (K0 disiplini: envelope = imza-yuvası hariç tamamı).

## 1) Karar

63-B, `pugio/` Python paketi olarak v0'a alındı. Amaç: 2-3 OSS vitrin-kurulumuna
"kendi API'ne x402 tak" teklifinden önce **çalışır kendi demosu** — "ilk mikro-ödemeyi
kendi ajanımızla kes" başarı-ölçütünü dogfood'lamak.

## 2) Mimari (v0 gerçekleri)

| Bileşen | Dosya | Seçim | Gerekçe |
|---|---|---|---|
| x402 kapısı | `middleware.py` | Saf ASGI, çerçeve-bağımsız | FastAPI/Starlette/her ASGI app'e sarılır — vitrin-kurulumu sürtünmesi en düşük |
| Ödeme-dozu | `pugio0` / `Pugio-EVM` / `x402 exact` başlıkları | HMAC geri-uyum + EIP-191 + EIP-3009 zarfı | Şema-Registry (`register_scheme`) — ProtocolAdapter noktası |
| Ledger | `ledger.py` | SQLite(WAL) + hash-chain (prev_hash, HMAC-seal) + `seen_nonces` | tamga-ya göç: olay-tipi şeması korunur; demo'da kanıt-inkâr testi (test_24) |
| Settlement | `facilitator.py` | x402 v2 verify/settle istemcisi (transport enjekte-edilir) | fail-closed: unknown/hata → 402; settle-düşüşü `settlement` olayıyla kayıtlı (test_67–71) |
| Politika | `policy.py` | KURAL_DSL v0 alt-kümesi: ilk-eşleşen, fail-closed, DenyAll | KURAL_DSL_V0 §2 semantiği; bozuk dosya → tüm harcama durur (test_09–22) |
| Panel | `panel.py` | Tek-HTML tablo + marka gömülü | PRD hafta-2 kabulü; zincir-bütünlüğü rozeti canlı |
| Keşif | `GET /agents.json` | 64-agents.txt hizalı | protokol-keşif alışkanlığı |

## 3) Kabul ölçütleri (PRD sürüm-tablosu karşılığı)

- [x] "Demo API'ye bir ajan ücretli istek attı; kayıt oluştu" — test_29/42 + canlı-akış (HMAC ve EVM)
- [x] "Kota aşımı 402 döndürür" — test_33 (3. çağrı 402) + canlı + S1.b
- [x] "İade kaydı düzgün" — refund negatif-netleşir (test_25)
- [x] Kural ihlali engellenen istek + ledger olayı — policy_guard + permission_decision + S1.c/d
- [x] Fail-closed: bozuk politika → DenyAll (test_17) + canlı (dosya-değişim-izleme) + panel rozeti
- [x] Sayaç-çakışma: 8 thread × 10 append, zincir sağlam (test_27)
- [x] **S1 (IS_PLANI §7):** günlük-$50-cap + saat-aralığı dogfood → `scripts/s1_dogfood.py` KABUL
- [x] **S4 (IS_PLANI §7, ilk-adım):** kanıt-bundle pür-sha256 harici-doğrulanır (test_49 + dogrula.py) — 81-MERGEN hattına hazır
- [x] **Ajan-kimliği = cüzdan-adresi:** EIP-191 imza-dogrulaması (test_36–43) — non-custodial tezin kod-karşılığı
- [x] **Settlement-lifecycle:** exact → verify ✓ → handler → settle → `settlement` olayı; settle-düşüşü sessiz-kalmaz (test_67–71)
- [x] **Kalıcı replay:** nonce restart'tan sağ çıkar (test_64–66); float-tuzak kapalı: 0.10×3 = 0.30 kotasını tam doldurur (test_72)
- [x] **Çapraz-repo köprüler:** Tamga/Veridict alıcıları subprocess ile uçtan-uca — temiz→SAĞLAM, kazınmış→RED (test_74–81)

## 4) Bilinçli olmayanlar (v0.1 itibarıyla kalanlar)

1. ~~EVM-imza doğrulaması~~ ✅ v0.1; ~~facilitator verify/settle~~ ✅ v0.2
   (HTTP-istemci, transport-enjeksiyonu; zincir-üstü Settler-kontrat çağrısı hâlâ ileride).
2. ~~Nonce kalıcılığı~~ ✅ v0.2 (`seen_nonces` tablosu, append-kilidi altında first-writer-wins).
3. ~~escalate kuyruğu~~ ✅ v0.2.0 (`pugio/escalation.py`: park→approve/deny→
   bir-kezlik consume, TTL fail-closed, ledger-denetim-izi, CLI + /escalations
   + v0.3'te /approvals paneli ve decide-endpoint).
4. ~~AP2/ACP adaptörleri~~ ✅ v0.2.0 (`pugio/adapters.py`: mandate/session →
   ChargeIntent/ChargeReceipt; ortak-cüzdan tek-kota); ~~AP2 JWS-imza~~ ✅ v0.3.0
   (HS256/ES256, gövde-bağı, alg-allowlist). Kalan: ACP satıcı-oturum-açma hattı.
5. ~~Float-simülasyon~~ ✅ v0.2 karar-aritmetiği integer minor-unit; ledger saklama-kolonunun
   minor-int'e göçü ileride (v0.2'den beri karar-zamanında çevrim yapılır).
6. ~~Policy-imzası + 24s gevşetme-gecikmesi~~ ✅ v0.3.0 (`pugio/policy_signed.py`:
   JWS-mühürlü zarflar, sıkılaştırma-anında / gevşetme-24s, pending-sızıntı-yok).
7. **PyPI/GitHub yayını** — paket-adı `pugio-meter` boş-teyitli; **wheel+sdist inşa-edildi**
   (`dist/`); yayın (twine) kullanıcı-kararı: GitHub-release sonrası.
8. ~~Postgres backend~~ ✅ v0.3.0 (`pugio/pg_ledger.py`: ortak hash-chain çekirdeği,
   özdez-zincir parite-seti; PG-bundle harici-dogrulayıcıdan geçer). Kalan: migrasyon-
   aracı (SQLite→PG olay-taşıma) ileride.

## 5) Riskler / notlar

- Demo-kotası (0.20) bilinçli düşük: 5. çağrıda kota-aşımı vitrinde görünsün.
- SECRET demo-sabit; production'da ortam-değişkeni + cüzdan-anahtarı (non-custodial ilke).
- SQLite tek-yazıcı; çoklu-süreç senaryosu Postgres'e göçle v0.2 kararı.
