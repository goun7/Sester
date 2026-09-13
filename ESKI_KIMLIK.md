# Eski kimlik

- Kimlik-dizisi: `01_unicorn/63-Pugio` -> `01_unicorn/63-Sikke` -> **`01_unicorn/63-Sester`**
- Tarih: 2026-09-13
- Neden-1 (Pugio elendi): bilinen ekosistem-kalabalığı (pugio.js, ASUS ROG Pugio, Rust aracı).
- Neden-2 (Sikke elendi): İngilizce fonetiğinde "Sick" (hastalık) ve argo çağrışımları.
- Seçilen: Antik Roma'nın ilk standart ticaret sikkesi **Sester** (Sestertius'tan).
  PyPI, Crates, NPM, .ai, .io tescil taramalarında **%100 temizdir**.
- Kod-göçü (2026-09-13): paket `sikke` → **`sester`**, `SikkeMeter` → **`SesterMeter`**,
  `X-Sikke-*` → `X-Sester-*`, `exact-sikke` → `exact-sester`, `PUGIO_*` env'leri →
  `SESTER_*` (PG_DSN, ESCALATION_DB, DEMO_LEDGER_DB, TAMGA/VERIDICT_PATH,
  UCP/AP2_SECRET, DEMO_STRICT). Eski `sikke/` paketi fail-loud tombstone (sonra silinir);
  sınıf-takma-adı: `sester/compat.py`.

## Dondurulmuş kablo-alanları (uyumluluk) — v2'ye kadar DEĞİŞMEZ

- `pugio0` şema-önadı (HMAC geri-uyum başlığı)
- `pugio_bundle_version` / `pugio_evidence_bundle` (kanıt-bundle alan-adları)
- `source: "sikke"` (K1 çıpası + K2 claim'ler + K3 watch-manifest kaynak-değeri)
- Kardeş-repo alıcı-dosya adları: `tamga_pugio_receiver.py`, `tamga_pugio_ingest.py`,
  `scripts/pugio_watch_receiver.py`
- **Kanonik kopya (2026-09-13):** kardeş-repolar yeniden konumlandı
  (`05_acik_kaynak/TamgaProtocol`, `05_acik_kaynak/Veridict`) — alıcıların
  birincil kopyası yine kardeşlerde; `bridge_receivers/` SESTER'daki
  regresyon-aynası olarak kalır (ayna-testleriyle her koşumda doğrulanır:
  tests/test_bridges_mirror.py).

Bu değerleri değiştirmek kardeş-repo (Tamga Protocol / Veridict) alıcılarını ve
yayınlanmış kanıt-bundle'larının doğrulanabilirliğini kırar — KARAR-kaydı olmadan
dokunulmaz (KARAR_63B §deprekasyon-politikası).

## Göç-öncesi test-durumları

- Pugio→Sikke göçü: 159 passed (2026-09-13, klasör+repo+kod)
- Sikke→Sester göçü: kod+test+CI+scripts birebir; final-gate koşusu göç-sonrası yapılır
