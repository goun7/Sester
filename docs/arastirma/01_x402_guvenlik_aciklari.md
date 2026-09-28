# x402 Ödeme Güvenliği — Akademik Açıklar ve Sester'ın Kapanışı

**Tarih:** 2026-09-28 · **Doğrulama:** Bu dokümandaki her kaynak çekilip özeti
ile birlikte okunmuştur (erişim: 2026-09-28). Yanlış-alıntı riskini azaltmak
için her makalenin **yalnızca çekildiği kısımdaki** rakamlar kullanılır.

---

## 1. Boşluğun kanıtı: üç makale, tek sonuç

### 1.1 USENIX Security 2026 — facilitator'lar dışarıdan doğrulanamıyor

**Kaynak:** Qinying Wang, Yong Yang, Yuan Chen, Shouling Ji, Mathias Payer,
*"When HTTP 402 Meets the Blockchain: Risks on Emerging x402 Payments"*,
arXiv:2607.19545 (arXiv kaydında `journal_ref: "USENIX Security 2026"`).
<https://arxiv.org/abs/2607.19545>

Çekilen özetin ulaştırdıkları:

- x402, `402 Payment Required` akışını zincir-üzeri settlement ile birleştirir
  ve **doğrulama + settlement'ı üçüncü-parti facilitator'lara devreder**.
  Facilitator'lar *shared payment infrastructure* olur: **tek bir kusur birçok
  hizmeti etkiler**.
- Yazarlar facilitator'lar için **8 güvenlik kuralı** tanımlar ve ihlallerden
  **4 yeni saldırı vektörü** türetir: *Free Shopping*, *Asset Theft*,
  *Service Denial*, *Gas Abuse*.
- 15 büyük x402 facilitator (60K+ satıcı, 360K+ alıcı tarafından kullanılan)
  yarı-otomatik bir kara-kutu araç ile taranmış: **"we find violations in all
  evaluated facilitators"** — 15/15.
- Ek olarak 119M+ Base/Solana işlemi ölçülüp facilitator merkezîleşmesi ve
  ekosistem-düzeyi risk göstergeleri quantify edilmiş. Açıklar sorumlu-açıklama
  (responsible disclosure) ile bildirilmiş, tarafça doğrulanmış ve mitigasyonlar
  (Coinbase dahil) benimsenmiş.

**Sester'a düşen not:** Açığın özü *facilitator'a güven* modelidir. Alıcı
"ödendi" der; karşı taraf bunu facilitator'un sözü dışında **bağımsızca
kanıtlayamaz**. Bu tam olarak Sester'ın receipt'inin hedeflediği boşluk:
proof, `sha256` ile sıfır-güvenle yeniden-hesaplanır.

### 1.2 Tamarin ile resmî analiz — 86 vaka, 40 yeni bulgu

**Kaynak:** Ke Jiang, Mohan Yu, Yuan Chang, Mohit Kumar Jangid, Jianyu Niu,
Cong Wang, Yinqian Zhang, *"A Formal Analysis of Agent Payment Protocols"*,
arXiv:2609.00060. <https://arxiv.org/abs/2609.00060>

Çekilen özetten:

- **x402, MPP, ACP ve AP2 Tamarin'de** resmî olarak modellenmiş; ortak bir
  ödeme-yaşam-döngüsü soyutlaması ile roller, durum, güven-varsayımları ve
  yaşam-döngüsü geçişleri kaynak-tabanlı modellenmiş.
- **86 doğrulama vakasında** 46 bilinen/kalibrasyon vakası yeniden üretilmiş,
  **40 daha önce belgelenmemiş formal-tutarlılık bulgusu** keşfedilmiş.
- Bulgular **18 paylaşılan güvenlik ilkesinde** birleştirilmiş; her ihlal için
  eksik protokol-bağıntısı izole edilip minimal güçlendirilmiş model yeniden
  doğrulanmış.
- Çözüm: *"delegated authorization must remain consistent with its resulting
  economic and service effects across actors, states, and protocol stages."*

**Sester'a düşen not:** "Missing bindings / cross-stage correspondences" —
receipt, bir **binding**'dir: imzalı-niyet (charge) ile ekonomik-etkisi
(tutar/kaynak/zaman) arasında dışarıdan-denetlenebilir bir bağ.

### 1.3 AP2'de imza geçerli ama karar değil — %90 / %56 / %73.3

**Kaynak:** Yedidel Louck, Amit Dvir, Ariel Stulman, *"Signing the Transaction
but Not the Decision: Whisper Attacks and a Binding Defense for AP2"*,
arXiv:2609.11757. <https://arxiv.org/abs/2609.11757>

Çekilen özetten:

- AP2 gibi ajan ödeme protokolleri **kriptografik geçerli imzalar üretir ama
  o imzalara götüren kararları kısıtlamaz**. Sıradan ürün-açıklama metni bir
  alışveriş-ajanını, her protokol-kontrolünden geçen ama kullanıcının isteğine
  uymayan bir sepete yönlendirebilir.
- Üç saldırı (Gemini Flash-Lite üzerinde, AP2'nin örnek-ajanlarının varsayımı):
  **%90** (başka kullanıcının ödeme-kimlik-bilgilerini çektirme), **%56**
  (gösterilenle uyuşmayan kriptografik-geçerli sepet), **%73.3** (tek bir
  stok/doğruluk iddiası ile daha pahalı ürüne kayma — sepet listeleme ile
  tamamen tutarlı kalır).
- Zafiyet **17 Google modeli, 3 alakasız ajan-çerçevesi, 2 çapraz-satıcı
  çapası ve Google'ın kendi tüketici asistanında** görülüyor.
- Savunma **A-VIP** (AP2 Verified-Intent Protection): imzalı niyeti bir
  *capability grant* olarak değerlendirir; her kimlik-bilgisi aramasını
  isteyen oturuma, her sepet-satırını görülen listeye bağlar. İlk iki saldırı
  yapısal izler bırakır → sıfır false-positive ile engellenir; üçüncü iz
  bırakmaz → yetkisiz harcama kullanıcı-onayına yükseltilir.

**Sester'a düşen not:** A-VIP'in "binding" doktrini ile Sester'ın receipt'i
aynı eksende: **neyin ödendiğini** (kaynak, tutar, ajan, an) dışarıdan
doğrulanabilir bir sabitliğe bağlamak. Sester niyet-tutoru değildir (LLM
katmanına karışmaz); ödenen-gerçekliğin kanıtını verir ve A-VIP-tarzı
bağlamalar için kriptografik zemin hazırlar.

---

## 2. Daha geniş kanıt tabanı (hepsi çekilip özetlendi)

| Makale | Çekilen-anahtar | Sester bağlantısı |
|---|---|---|
| *"Five Attacks on x402 Agentic Payment Protocol"*, arXiv:2605.11781 — Zelin Li, Qin Wang, Zhipeng Wang <https://arxiv.org/abs/2605.11781> | Yetkilendirme, bağlama, tekrar-koruması ve web-katmanı zayıflıkları; "unpaid service" ve **"paid-but-denied"** çıkışları; üç SDK/endpoint denetimi | Receipt tekrar-korumasını nonce + zincir-pozisyonu ile sabitler |
| *"Free-Riding the Agentic Web"*, arXiv:2605.30998 — Ling, Huang, Du, Chen, Zhou, Wu, Wang <https://arxiv.org/abs/2605.30998> | 5 invariant etrafında sistematik analiz; 4 hata-sınıfı: **cross-resource substitution**, **duplicate-settlement race**, **allowance overdraft**, **denial of settlement**; resource-leakage oranı %100'e kadar | Her receipt `resource` alanına bağlı; kota-bypass yolları fail-closed |
| *"Hardening x402: PII-Safe Agentic Payments"*, arXiv:2604.11430 <https://arxiv.org/abs/2604.11430> | Ödeme-meta-verisi (URL, açıklama, sebep) settlement-öncesi facilitator'a gider; presidio-hardened-x402 PII filtreler + **declarative spending policies** + replay blocking | Sester'ın Policy-DSL + receipt meta-verisi aynı üç ekseni karşılar |
| *"A402: Binding Payments to Service Execution"*, arXiv:2603.01179 <https://arxiv.org/abs/2603.01179> | x402 **uçtan-uca atomikliği dayatmaz**; TEE-adaptor imza ile ödeme ↔ hizmet-yürütme bağlar | Benzer hedef, farklı güven-modeli: Sester TEE'ye değil herkese-açık sha256'ye güvenir |
| *"SoK: Blockchain Agent-to-Agent Payments"*, arXiv:2604.03733 <https://arxiv.org/abs/2604.03733> | 4-aşamalı yaşam-döngüsü (discovery/authorization/execution/accounting); zorluklar: **weak intent binding**, payment-service decoupling, **limited accountability** | Receipt, *accounting* aşamasının dışarıdan-denetlenebilir parçasıdır |
| *"How Agentic Is Agentic Commerce?"*, arXiv:2607.12575 <https://arxiv.org/abs/2607.12575> | 280-gün Base ölçümü: 136.7M settlement / $44.1M; **%21.20 fictitious**, %63.78 iç-yığınsal; Gini >0.98 | Sayıların kendisi kanıtlanabilir-olmalı: bağımsız ledger doğrulaması |
| *"402Pilot"*, arXiv:2608.01341 <https://arxiv.org/abs/2608.01341> | Alıcı-tarafı karar-katmanı; wallet-baskısı altında sağlayıcı-seçimi | Sester satıcı-tarafı kanıt-verir; tamamlayıcı |
| *"Agentic Settlement Protocol (ASP)"*, arXiv:2609.02208 <https://arxiv.org/abs/2609.02208> | Gecikmiş-teslimat ticareti için authorize-and-capture escrow profili; üç-deadline hold modeli | Sester'ın escalation/human-approval ile aynı "parayı-geç- bırak" doktrini |

x402 referans-implementasyonu ve protokol metni: **<https://github.com/x402-foundation/x402>**
(eski upstream `coinbase/x402` artık geliştirme fork'u; issue/PR'ler Foundation
reposuna transfer edildi — README'sinden çekildi).

---

## 3. Sester bu açıklardan hangilerini kapatır?

Doğrulama-yolu açısından, kategorik olarak dürüst bir tablo:

### Kapatılanlar (kanıt mekanizması ile)

| Açık | Sester kapanış-yolu | Kanıt |
|---|---|---|
| "Ödendi" iddiası dışarıdan doğrulanamaz (facilitator güveni) | **node-cosigned receipt**: `proof` = `sha256(ts\|event_type\|agent\|resource\|amount\|payload\|prev_proof)` — alıcı tarafı Sester/secret/internet olmadan yeniden hesaplar | `tests/test_receipt.py`, `sester verify <receipt>` |
| Binding eksikliği (imza ≠ karar) | Receipt `resource`/`amount`/`agent`/`ts`'yi **asıl-kanıtın içine** gömer; değişiklik proof'u bozar → RED | `test_tamper_core_fields_caught_secretless` |
| Zincir-bütünlüğü opak | HMAC-mühürlü ledger + **secret'sız** evidence-bundle (merkle-root + head); `sester bundle` | `docs/K0_SHARED_ENVELOPE_SPEC.md`, `test_dogrula.py` |
| Üçüncü-parti "sessiz kabul" | fail-closed doktrini: bozuk politika → DENY_ALL; bilinmeyen şema → 402; facilitator-erişilemez → 402 | `docs/adr/0011_fail_closed_patterns.md` |
| Tekrar-harcama (replay) | Kalıcı nonce-tablosu + first-writer-wins; geçersiz ödeme nonce'u yine tüketir | `middleware.py` claim_nonce |
| Kota-bypass (TOCTOU / negatif amount) | Atomik check+act bölgesi; negatif/sıfır/negative-bool amount RED | `AT-181`, `AT-062`, `AT-188` |
| Ödeme meta-verisi denetimsiz | Policy-DSL: `host_in`, `hour_between`, `amount_gt`, `agent_in` + escalation | `examples/f1_policy.json` |

### Kapatılmayanlar (kasıtlı sınırlar — abartısız)

- **LLM karar-bağlama (Whisper saldırı 3)**: Sester bir ajanın *niyetini*
  doğrulamaz; ödediği gerçek ile iddia ettiği şey arasındaki tutarlılık A-VIP
  tarzı bir karar-katmanı işidir. Sester bunun için **kriptografik zemin**
  verir (receipt = bağlanabilir anchor), yargıç değildir.
- **Facilitator iç-robustluk (Asset Theft / Gas Abuse)**: Bunlar facilitator
  implementasyon hatasıdır; Sester bir middleware/kanıt katmanıdır, bir
  facilitator-un yerini almaz. `facilitator_svc` kasıtlı olarak non-custodial
  kalır (fon hareketi yok).
- **Uçtan-uca atomiklik (A402'un TEE modeli)**: Sester HTTP-akışında kalır;
  adaptor-imza/TEE tabanlı atomiklik kapsam-dışı (docs/ROADMAP'teki non-goal).

---

## 4. Saldırı-başarı-oranları neden bu projenin konumunu doğrular

%90 / %56 / %73.3 (arXiv:2609.11757) ve 15/15 facilitator ihlali
(arXiv:2607.19545) tek bir mesaj verir: **imza-geçerliliği çözülmüş, kanıt
değil.** Pazarda ödeme-yapan ajanlar var; bunları dışarıdan denetleyebilecek
stdlib-only, registry-yayınlanabilir bir araç ise yok (bkz.
`03_pazar_boslugu_mcp.md`). Sester'ın receipt + MCP ikilisi tam bu noktada.

---

## 5. Kullanılan-olmayan kaynaklar (dürüst-not)

Aşağıdaki referanslar **dokümantasyona alınmadı** çünkü çekilemedi/doğrulanamadı:

- USENIX Security 2026 resmi oturum-sayfası (arXiv `journal_ref` alanı ile
  yetinildi; resmi URL çekilmedi).
- Tarama iddiası "Smithery'de 715 MCP" — bu sayı görev-brifinginden geldi;
  bu oturumda Smithery registry API'si üzerinden yeniden sayılmadı. MCP
  araması için `smithery mcp search` kullanılması önerilir.

Hiçbir rakam brifing-varsayımıyla yazılmadı; tablodaki her değer yukarıdaki
arXiv sayfalarından çekilen metinden alıntıdır.
