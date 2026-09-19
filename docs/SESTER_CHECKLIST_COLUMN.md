# Sester sütunu — Tri-Product Spec↔Code Divergence Checklist

> **Amaç:** `TRI-PRODUCT-CHECKLIST.md` (Tamga `tests/conformance/`)-in önerdiği
> ortak formatta Sester'ın normatif kurallarını **iki yönde de ölçerek** doldurmak.
> **Ölçmeden iddia yok:** her kural için (a) spec-needle satırı, (b) kuralı çzen
> RED-vektörü üreten test, (c) bağımsız-verifier paritesi.
>
> **Ölçüm-tarihi:** 2026-09-19 · **Tarayıcı:** elle-ölçüldü (her satırın testi
> koşularak), `tools/`-tarayıcı-yazılmadı (metod aynı, sonuç elle-doğrulandı).

## Sonuç

```
Ürün: sester  |  aligned=10  spec-only=0  code-only=0  untested=0
```

**Önemli-not (dürüst-bildirim):** tarama sırasında **1 code-only kural bulundu**
— replay-koruması (S-3.1): kodda-zorunlu + 3-testle-sabitlenmiş ama normatif
metinde yazmıyordu. **ERRATUM-K0.3 ile aynı-gün kapatıldı** (K0 §7-kural-6,
commit `79ff6fa`). Bu, checklist'in-meta-for-sonucudur: yöntem bizim-tarafta-da
görünmez kural yakaladı. Kapatma-sonrası aligned=10, divergence=0.

## Ölçüm-tablosu

| id | kural | spec (needle) | kod (RED-vektörü) | parite | sınıf |
|---|---|---|---|---|---|
| **S-1.1** | hash-chain: `proof_i = sha256(canonical_line_i)`, `prev` önceki-proof'a-eşit | E — K0 §2 (l.26–28) | E — `test_204` (miktar-kazıma → `verify_chain()` False) | E | aligned |
| **S-1.2** | ilk-olay `GENESIS = 64×"0"` | E — K0 §1 (l.28) | E — `test_203` (3-olay temiz-zincir → True) + boş-zincir | E | aligned |
| **S-1.3** | canonical-line formatı (`%.6f` major + compact-JSON, alan-sırası) | E — K0 §1 (l.16–29) | E — `test_204`/`test_206` (herhangi-sapma yeniden-hesap → RED) | E | aligned |
| **S-2.1** | `amount_minor` preimage'DIŞI (negatif-kontrol: kalan-tutar) | E — K0 §1 ERRATUM-K0.1 | E — `test_207` (minor-sütun-değiş → GREEN kalır; miktar-değiş → RED) | E | aligned |
| **S-2.2** | `event_type` taksonomisi — küme-dışı yazım RED | E — K0 §1 ERRATUM-K0.2 (12 statik + `facilitator_*` ailesi) | E — `test_208` (bilinmeyen-tip → `ValueError`, satır-yazılmaz) | E | aligned |
| **S-2.3** | netting işareti: `charge_receipt` +, `refund` − | E — K0 §1 ERRATUM-K0.2 | E — `test_208` (0.10 − 0.03 = 0.07) | E | aligned |
| **S-3.1** | replay: nonce kalıcı-reddi (restart dahil) | E — K0 §7 kural-6 ERRATUM-K0.3 | E — `test_64`/`test_65`/`test_66` (ilk-yazan-kazanır, reopen-sonra hâlâ RED) | E | aligned (K0.3-öncesi code-only) |
| **S-3.2** | fail-closed: bozuk/eksik-policy → `DenyAll` | E — K0 §7 kural-5 + ADR-0003 | E — `test_17` (deny-all herşeyi-engeller), `test_19`–`test_22` (bozuk-rule → yükselt) | E | aligned |
| **S-4.1** | `anchor_id` = merkle-root bağlamı (üç-bağımsız-kontrol) | E — K0 §3 (l.83), §5 (l.103–105) | E — `test_57` (anchor-değiştirme → RED) | E | aligned |
| **S-4.2** | yanlış-`source` / bilinmeyen-`*_version` → hard-reject | E — K0 §7 kural-2 | E — `test_58` (yanlış-source → RED) | E | aligned |

**E=evet | ✓=uyumlu | S=sadece-spec'te | C=sadece-kodda | ?=ölçülemedi**
**Parite:** Sester'ın bağımsız-verifier'ı `sovereign_verify.py` (Tamga)-in
Sester-bacağıdır — `Ledger(path, secret).verify_chain()` + RISK-1/2-kapıları;
`test_205`/`test_206` (gerçek-wrapper, rc-ölçümü) ile kilitli.

## "REDleşirse kim etkilenir" — erratum-başına etki-yönü

Tamga'nın önerdiği sonraki sütun; her erratum için "geri-uyumlu mu" değil,
**"REDleşirse kim etkilenir ve hangi-yönde"**:

| erratum | REDLEŞİRSE-etki | yön | kıyas |
|---|---|---|---|
| **K0.1** (amount_minor) | Sester'ın-kendi `verify_chain`'i kırılır → **üretici** yazım/anlık-doğrulamada farkedip düzeltmeden ileri gidemez | **write-time, üretici-tarafı** | — |
| **K0.2** (event_type) | `append` yükseltir → olay-hiç-yazılmaz → **üretici** kendi-write-yolunda loud-fail alır; verifier asla-bozuk-veri görmez | **write-time, üretici-tarafı** | — |
| **K0.3** (replay) | çift `charge_receipt` yazılırsa → **alıcılar** harcama-toplamını çift-sayar; üç-ürün anchor/hesap ayrışır | **read-time, alıcı-tarafı** ← sınır-aşan | A1-ile-aynı-yönde (eski-anchor okuyan herkes), ama A1 bilinçli hard-fork-uyarısı, K0.3 kuralın-kendisi |

**Desen (Sester-tarafı):** K0.1/K0.2 hatada **üreticiyi** loud-fail'le durdurur
(kötü-fail değil, iyi-fail — hata ürün-dışına sıçramaz). K0.3 ise tek kural ki
hatası **sınırdan-geçer** — bu yüzden shared-spec'e ait, üretici-iç-not değil.
Tamga A1 de read-time/sınır-aşan — ama kasıtlı olarak (sessiz-geçiş tercih
edilmez). İki read-time etki arasındaki fark: A1 bilinçli-bir-tasarım-seçimi,
K0.3 bir yükümlülük (ihlali hata).

## Dürüst-sınırlar (Sester-tarafı)

- Bu sütun **yayımlanmış-spec'leri tarar** — Sester'ın tüm normatif kurallarını
  bildiğini iddia etmez. Tarama-derinliği K0 + ADR'ler + README ile sınırlı.
- Parite-ölçümü **Tamga'nın bağımsız-verifier'ına** bağlıdır; Veridict bir
  bağımsız-verifier yayımlamadıysa o sütun `untested` kalmalı (dürüst-bildirim,
  sessiz-geçiş-yok).
- Elle-ölçüm, otomatik-tarayıcıdan **daha-hassas-hata-eğilimli** — tekrar-
  üretilebilirlik için `tools/`-tarayıcı yazılması bir sonraki-adım olabilir.
