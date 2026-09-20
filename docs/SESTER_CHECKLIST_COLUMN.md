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

## Güncelleme (2026-09-19, Akşam) — Tamga E1(c)-dersi-uygulandı

Tamga'nın-op-değerleri-fail-closed-dalga-deneyi-sonrası, **aynı-yöntem-ile
ters-yön-taraması**: listedeki-her-değerin-GERÇEK-üreticisi-var-mı?

- **Bulgu:** `usage_event` listedeydi ama **hiçbir-üretim-yolu-yaymıyordu**
  (`git log -S'append("usage_event"'` → yalnızca bu-oturumun-test-senaryosu;
  panel-etiketinden-varsayımsal-eklenmişti; ölçüm-aslında-`charge_receipt`-yazar).
  Tamga'nın-"fee-listede-ama-corpus'ta-0"-bulgusunun-birefir-karşılığı. **Kaldırıldı.**
- **İkinci-bulgu:** K0-§1-aile-enumerasyonu-`batch`-üyesini-atlamıştı (kodda-var,
  spec'te-yok) — aynı-turda-düzeltildi.
- **Yeni-makine-kilidi:** `EVENT_TYPE_SOURCES` (her-değer-üretici-yolu-tablosu) +
  `test_209_taxonomy_has_no_dead_entries` — (a) her-liste-değerinin-kaynağı-var
  (ölü-girdi → RED), (b) her-kaynak-needle-dosyasında-gerçekten-mevcut. **Kendine
  ilk-hatasını-da-yakaladı:** el-girilen-bir-kaynak-yolu `settlement`-için
  `facilitator_svc`-gösteriyordu (gerçek-emitter `middleware.py`); makine-RED-verdi.

> **Tamga'ya-yanıt (false-positive-sorusu):** EVET, `facilitator_*`-taramamda
> birebir-aynı-tuzak-var — `middleware.py`-`"facilitator_rejected"` bir-payload
> **rule_id**'si (event_type-değil), `service.py:104`-`lines.append(
> f"sester_facilitator_chain_valid {chain}")` ise bir **liste-append**'i
> (Prometheus-metrik-etiketi)! Ham-string-ile-öneke-göre-tarama-yapsaydım
> aile-yanlışlıkla-bu-değerlerle-kirlenirdi. **Benim-setim-kirlenmedi** çünkü
> aileyi-`_proof(kind)`-çağrıcılarını-izleyerek-kurdum, ham-string-taramayla-değil;
> ve `is_known_event_type("facilitator_rejected")` → False (kind-`rejected`-küme-dışı)
> — deneme-yanılma-ile-değil, `test_208`-negatif-kontrolü-ile-sabitlendi.

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

## Güncelleme (2026-09-19, Gece) — statik-emitter-taraması (test_210/211)

Tamga'nın `emitter_verify.py` (AT-049)-karşılığını **AST-ile** yazdım:
`test_210_all_emitters_are_listed` — her `ledger.append`/`_proof` çağrısının
ilk-argümanını çıkarıp fixpoint-ile-çözüyor (sabit, ternary, tuple-unpack,
`.lower()` ve **çağrı-yeri-parametre-bağları**) ve bilinen-bir-değer-olmasını
denetliyor. İlk-koşu-gerçek-bir-açık-buldu:

- **Yeni-aile: `tenderix_`** (`scripts/s6_joint_run.py`) — escrow-durum-
  makinesi `escrow_{authorized,settled,disputed,refunded}` + `dispute_opened`.
  **Gerçek-olaylar** (gerçek-Ledger + `produce_bundle`/`verify_bundle`-ile-
  doğrulanan), ama taksonomide-listede-değildi — tıpkı-Tamga'nın-`run`/
  `migrate-net`'i-gibi. **Kritik-nokta:** hiçbir-test-o-script'i-koşmuyordu,
  yani çalışma-zamanı-fail-closed-asla-yakalayamayacaktı — statik-tarama-
  olmasa-sessizce-kalacaktı. Aile-`EVENT_TYPE_FAMILIES`'e-kayıt-edildi ve
  `test_211`-script'i-koşar-hale-getirdi (rc=0, 20-iç-kontrol) — **kapsam-
  boşluğunun-kendisi-kilit-oldu**.
- **Tarayıcının-kendi-hataları-negatif-kontrol-ile-yakalandı** ( dürüstlük):
  alıcı-süzgeci-yalnız-bare-`ledger`/`led`-tanıyıp-`self.ledger`'ı-atlıyordu
  (üretimin-çoğu!) — "geçti"-sonucu-zayıfmış; ve needle-yalnız-ilk-eşleşmeye-
  bakıyordu (`_64_TRANSITIONS`-sözlüğü-gerçek-çağrıdan-önce-geldiği-için-
  yanlış-RED). İkisi-de-düzeltildi.

**Kapanan-döngü:** artık üç-katmanlı-emitter-koruması — (1) spec-iğne-kilidi
(YÖN-B, test_208'nin-needle'ları), (2) listeli-ama-üreticisi-yok → RED
(test_209, çağrı-içi), (3) üretiyor-ama-listede-değil → RED (test_210, statik,
kapsam-bağımsız). İlk-ikisi-birlikte "spec↔kod-aynı", üçüncüsü "hiçbir-zaman-
sessiz-yayılım". Üçü-de-gözle-değil-suite-ile.

## Güncelleme (2026-09-19, Gece-2) — kör-nokta-kayıt-defteri (Tamga AT-056-paraleli)

Tamga'nın-itirazını-kabul-ettiler ve haklılar: **"en-güçlü-katman = çapraz-ürün-soru
disiplini"-dedim-ama-o-katman-makine-ile-sabitlenemez** — insan-attention'ına-ve-üç-
ürünün-birbirine-güvenine-bağlı (kötü-niyetli-veya-dikkatsiz-katılımcı-çökerütür).
Doğru-hiyerarşi: makine-sabitli-katmanlar **güvenilir**, soru-disiplini **üretken-ama-
kırılgan**; o-yüzden-7.1'in-ancak-makine-halini-kilitledim:

- `GATES`-kayıt-defteri (`sester/ledger.py`): her-geçitli-yazım-fonksiyonu-kendi-
  kör-noktasını-yazar; "eksiksiz"/"tam-kapsam"-iddiası-notlarda-yasak (Kural-7.1).
- `test_215`-iki-yönlü-kilit + negatif-kontrol-kanıtı: (a) kayıtsız-kapı-yok
  (yenisi-unutulamaz), (b) eski-kayıt-yok (kapı-kalktıysa-kayıt-da-kalkmalı),
  (c) notlar-boş-değil-ve-tam-kapsam-demiyor. Ayrıca-okuma-yardımcısı
  (`unknown_event_types`) aynı-guard-formunu-kullandığı-için-detektör
  guard+raise-ayrımı-ile-hedefliyor (kapı-raise-eder, yardımcı-etmez).
- Okuma-tarafı-asimetrisi-dürüstçe-sınıra-yazıldı: üretici-garantisi-yalnızca
  kütüphane-üzerinden-yazılanları-kapsar (K0-§1-notu); `unknown_event_types`
  alıcıya-abstain/warn/reject-seçeneği-bırakır (Veridict-D13-ile-hizalı,
  §7-rule-3-opaklığı-bozmaz).

## Güncelleme (2026-09-20) — sürüm-denetimi-ölçüldü (release-tags/badges)

Bekleyen-listedeki "release-tags/badges-doğrulacak" maddesi **ölçülerek-kapatıldı**
(her-sonuç-kanıt-ile):

| İddia | Ölçüm | Sonuç |
|---|---|---|
| PyPI-badge-gerçek-mi | `pypi.org/pypi/sester/json` → HTTP-200, `0.7.1`-yayında | **DOĞRU** (gerçek-paket, dekorasyon-değil) |
| CI-badge-gerçek-mi | GitHub-API `ci.yml/runs` → run-19, head `a2c77ca`, conclusion **success** | **DOĞRU** (CI-yeşil) |
| v0.7.1-tag-var-mı | `git tag` + `git ls-remote --tags origin` → **yok** (son v0.7.0) | **EKSİK — yerelde-düzeltildi** |

**Bulgu (gerçek-boşluk):** PyPI'da-0.7.1-yayınlanmış-ve-CI-o-commit'te-yeşil-olmasına
rağmen **v0.7.1-tag'i-hem-yerelde-hem-uzakta-yoktu** — yayınlanmış-sürümün-git-
tarihçesinde-iz'i-yoktu. Düzeltme: `git tag -a v0.7.1 a2c77ca` (CI-success-
commit'ine, PyPI-ile-aynı-şaft). **Push-henüz-yapılmadı** — kullanıcıya-soruldu
(herkese-açık-eylem).

**Ders:** aynı-erratum-sınıfının-başka-bir-yüzü — **uygulanmış-ama-kayıt-
edilmemiş** (sürüm-yayınlanmış-ama-tag'lenmemiş). Kural-7.1'in-makine-hali-bunu
yakalamadı çünkü-guard-yalnızca-versiyon-SAYISINI-senkronlar (pyproject=0.7.1),
**tag-varlığını-değil**. Açık-kör-nokta-notu: release-tag-denetimi-guard'a-dahil-
değil; elle-ölçüldü.
