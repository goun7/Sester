# 63 · SESTER — Veridict + Tamga Protocol Birleşme Değerlendirmesi (2026-09-12)

> Soru: `Veridict/` ve `Tamga Protocol/` ayrı projeler olarak kalmalı mı, birleşmeli mi?
> NOT (2026-09-13): kimlik-göçü PUGIO → Sikke → **SESTER** (klasör+repo+kod).
> Kablo-alanları DONUK: `pugio0`, `pugio_bundle_version`, `pugio_evidence_bundle`,
> `source: "sikke"`, alıcı-dosya adları — bu tablodaki köprüler etkilenmez (ESKI_KIMLIK.md).
> Yöntem: iki deponun README/ARCHITECTURE/pyproject/commit-geçmişi yerinde okundu
> (yalnız-okuma); karar kâğıt-bağı mimarisi (KAGIT/IS_PLANI) üzerinden verildi.

## 1) Üç projenin bugünkü hâli (fiyatlar tarihli: 2026-09-12)

| | **Veridict** | **Tamga Protocol** | **SESTER (63)** |
|---|---|---|---|
| Soru | "AI'ı AI'la denetlerken kanıt nasıl bağlayıcı olur?" | "Ajanın işi/ezberi/kimliği ölürse nasıl taşınır ve ispatlanır?" | "Ajan API'den harcarken kim sınırlar ve kanıtlar?" |
| Katman | Denetleme+hüküm (jury/ladder/certificate) | Durum+alınan-iş (WASI-sandbox, şifreli snapshot, work-receipt) | Sayaç+politika+ücret (x402-el sıkışma) |
| Olgunluk | v0.3.1 · **228 test** · CI canlı · **lansman-fazası** (launch-kit, FUNDING rails, TRC-20) | v0.2.2 · 42–46 test · **PyPI'da yayında** · Phase-2 pilot | v0.1–0.2 · 54 test · vitrin-prototipi |
| Bağımlılık-ayı | stdlib + cryptography (ed25519) | PyNaCl + wasmtime | sıfır-çekirdek (+eth-account opsiyonel) |
| Paylaşan DNA | hash-chain append-only ledger · offline-dogrulama · Apache-2.0 · "verify, don't trust" | aynı | aynı |

## 2) Karar: **BİRLEŞMESİNLER — protokol-köprüsüyle bağlansınlar**

Tek-depo/tek-paket birleşim **red**. Gerekçeler:

1. **Momentum-asimetrisi en büyük maliyet.** Veridict lansmanın ortasında
   (commit-geçmişi: launch-kit, badge-receipts, bağış-rails). Birleşim =
   lansmanı dondurmak. Tamga PyPI'da yayında — paket-kırılması = itibar-kırılması.
2. **Üç farklı alıcı, üç farklı keşif-yüzeyi.** Veridict → denetleme/README-tr
   governance-alıcısı; Tamga → agent-infra geliştiricisi (x402 #2887, ERC-8004
   ekosistemiyle konuşuyor); SESTER → API-satıcısı. Üç repo = üç yıldız-huni;
   birleşik repo hunileri eritir.
3. **Sözleşme-uyumu zaten kurulmuş.** 63-kâğıdının kendi mimarisi köprüyü
   tarif ediyor: "*tamga: olay ledger'ı → vitrin kredisi iki yöne akar*",
   "*Veridict: guvence sertifikası watcher ekosistemine bağlanır*",
   "*C-katmanı Veridict standardıyla en çok entegre olan*". Yani vizyon
   **monorepo değil, ortak-dil** diyor.
4. **Paketleme-çatışması.** Bağımlılık-katları çakışıyor (py≥3.11/cryptography vs
   py≥3.10/PyNaCl vs sıfır-bağımlılık). Tek paket = en düşük ortak payda veya
   ağır extras-matriksi.
5. **Arıza-yarıçapı.** Üç ayrı CI/itibar havuzu: biri kırmızıya düşse ikisi
   etkilenmez. Monorepo'da tek regression üç markayı birden vurur.

## 3) Bağlantı mimarisi (birleşme yerine): "tek-dil, üç-gövde"

Ortak zemin **zaten var**: append-only hash-chain + offline-dogrulama +
canonical-JSON/sha256. Eksik tek şey: bu ortak dili **üç tarafta da adlandırılmış
sözleşmeye** çevirmek. Köprüler (en ucuzdan pahalıya):

| Köprü | Yön | Mekanizma | Durum |
|---|---|---|---|
| **K0 · Ortak olay-zarfı** | hepsi | canonical satır-formatı + sha256 proof-zinciri + Merkle-kök şartnamesi | ✅ **v0.2'de yazıldı: `docs/K0_SHARED_ENVELOPE_SPEC.md`** (draft v0.1) — SESTER `sester/evidence.py` referans-uygulama |
| **K1 · SESTER → Tamga çıpası** | 63→tamga | SESTER chain-head + merkle-root'unu Tamga work-receipt-zarfı olarak kaydet (deterministik JSONL satırı) | ✅ **kodlandı: `sester/bridges.py` + Tamga tarafı alıcı `tamga_pugio_receiver.py` (pür stdlib, fail-loud; alıcı-dosya adı DONUK)** — çapraz-repo testli (test_74–76) |
| **K2 · SESTER → Veridict talebi** | 63→veridict | SESTER politika-kararları, Veridict'in makine-doğrulanabilir claim formatına dökülür ("quota enforced, replayable") | ✅ **kodlandı: `sester/bridges.py`** (test_81: claim_id-kuralı format-testi) |
| **K3 · Veridict watcher → SESTER** | veridict→63 | Veridict watcher'ı SESTER karar-akışını izler; deny-kararları W2/W3 doktriniyle denetlenir | ✅ **ilk-adım kodlandı: `sester/watchfeed.py` üretici (K0 §6 zinciri) + Veridict tarafı alıcı `scripts/pugio_watch_receiver.py`** — çapraz-repo testli (test_77–79); tam-watcher-entegrasyonu lansman-sonrası |
| **K4 · Tamga receipt ↔ SESTER charge** | tamga↔63 | Aynı ajanın work-receipt'leri ile charge-receipt'leri tek evidence-stream'de (`evidence_ref`, IS_PLANI §6 veri-modeli) | ileride |

**GitHub-org notu** (yayın günü kararı, şimdi değil): üç repo tek org altında
gruplanabilir (badge'ler ve "suite" algısı kazanıır) — repo'lar ayrı kalır.

## 4) Red-dilenen alternatifler

- **Monorepo:** §2'deki 1–5 maddesi. Hayır.
- **Tamga'yı SIKKE'nun ledger'ına gömme:** Tamga'nın WASI-sandbox'ı farklı problem
  (determinizm + taşınabilirlik); gömmek ikisini de küçültür.
- **Veridict'i "sertifika-kütüphanesi" olarak SIKKE'ya bağımlı kılmak:**
  Veridict'in spec-only-verifier disiplini (sıfır-import) satılabilir-tek-şey —
  kirletilmez.

## 5) Özet cümle

> "Üçü tek şirket-kütüphanesi değil; üçü **tek kanıt-dili konuşan üç bağımsız
> tanık**. Birleşme onları bir tanığa indirir — bağlamak onları birbirinin
> denetçisi yapar. Bağlayın, birleştirmeyin."

Kod-karşılığı: `sikke/bridges.py` (K1+K2), `sikke/watchfeed.py` (K3 üretici),
`docs/K0_SHARED_ENVELOPE_SPEC.md` (K0) + kardeş-repo alıcıları
(Tamga: `tamga_pugio_receiver.py` · Veridict: `scripts/pugio_watch_receiver.py`,
her ikisi pür stdlib + `--selftest`) — test_74–81 çapraz-repo kanıtıyla.
K4 Veridict-lansmanı sonrası ayrı karar-kaydıyla.

> **Köprüler çalışma-şeklini etkiler mi? Hayır — tasarım gereği etkileyemez (K0 §7):**
> üretici-tarafı yalnız **kamuya kanıt-alanlarını** okur (secret dışarı çıkmaz),
> alıcılar **bağımsız stdlib script'ler** (karşı-tarafın çekirdeğine/CI'ına dokunmaz),
> tüm artefaktlar **opt-in** (köprü çağrılmazsa hiçbir şey değişmez) ve
> **sürümlü** (bilinmeyen sürüm → hard-reject). Veridict lansmanı, Tamga PyPI
> yayınları ve SIKKE vitrini kendi hızlarında sürer — köprü yalnız üç tarafın da
> **doğrulayabildiği** ortak-dili ekler.
