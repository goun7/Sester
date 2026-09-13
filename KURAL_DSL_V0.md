# 63 — AjanTicaretYigini · A-Katmanı Kural DSL v0 (Mükemmelliyet E2)

> Amaç: ajan cüzdanının harcama kurallarının **insan-okunur, makine-çalıştırılır,
> imzalanabilir** şeması. Non-custodial ilke: anahtar kullanıcıda; DSL yalnız
> "hangi harcamaya izin var"ı tanımlar, parayı asla tutmaz.

## 1) YAML şeması v0

```yaml
wallet_policy:
  id: "wpol-2026-09-f1-demo"          # imzalanır, sürümlenir
  owner: "did:agent:kok:f1-treasury"  # 68-RobotProof kimlik şemasına köprü
  wallet: "evm:0x..."                 # non-custodial; anahtar bu dosyada DEĞİL
  defaults:
    currency: "USDC"
    per_request_max: 0.50             # tek istek üst sınırı
    daily_max: 25.00
    monthly_max: 400.00
    timezone: "Europe/Istanbul"
  rules:
    - id: allow-data-api
      when:
        host_in: ["api.example-data.io", "api.seccond-source.io"]
        hour_between: ["08:00", "22:00"]
      then: allow
      budget: { daily_max: 10.00 }
    - id: allow-agent-services
      when:
        x402_payee_verified: true     # 68 itibar skoru ≥ eşik
        reputation_min: 0.75
      then: allow
      budget: { per_request_max: 0.25 }
    - id: deny-unknown-hosts
      when: { host_in: [] }           # boş = tüm bilinmeyen hostlar
      then: deny
    - id: require-human-for-large
      when: { amount_gt: 5.00 }
      then: escalate                  # L2 onay kuyruğuna
  audit:
    ledger: "tamga://f1-demo/agent-payments"  # her karar olayı zincire
    on_violation: "block+log"                 # sessiz-geçiş yok
```

## 2) Değerlendirme semantiği

1. Kurallar sırayla; **ilk eşleşen** karar verir (deny-by-default üstte, allow
   kuralları spesifik) — belirsizlik deny'ye düşer (fail-closed).
2. Her karar → `permission_decision` olayı (81'in Veridict upstream şemasıyla
   aynı tip) → tamga zinciri.
3. Bütçe sayaçları işlem-atomik; çakışmada en dar üst sınır kazanır.
4. `escalate` → insan onay kuyruğu; onay = tek-kullanımlık izin olayı.

## 3) Değişim yönetimi

- Policy dosyası **imzalı** değişir (sahip anahtarı); sürüm zincire yazılır.
- "Kural gevşetme" (deny→allow) değişiklikleri 24 saat gecikmeli geçerlilik
  (acele-gevşetme saldırısına karşı) — sıkıleştirme anında geçer.

## 4) Test maddeleri (SDK kabul ölçütü)

- [ ] 20 pozitif/negatif vaka (limit aşımı, saat dışı, bilinmeyen host, escalate)
- [ ] Fail-closed doğrulaması (kural dosyası bozuksa → tüm harcama durur)
- [ ] Sayaç-çakışma testi (paralel isteklerde bütçe taşması yok)
- [ ] İmza-dogrulama: değiştirilmiş policy reddedilir

## 5) Tehdit-modeli bağlantısı (2026-09-12 literatür-taraması — ARASTIRMA §5)

DSL'in fail-closed semantiği artık "tasarım-zevki" değil, tarihli
literatür-destekli blast-radius kontrolüdür:

- **Prompt-injection üretimde yaygın:** üretim-deploy'ların ~%73'ünde görüldü
  (2025 anketi; ⚠️ tek-kaynak) — ajanın harcama-kararı güvenilmeyen içerikten
  etkilenebilir. DSL'in cevabı: politika **model-dışı, yorumlayıcı-tarafında**;
  LLM'e sorulmaz, imzalı dosyadan okunur.
- **"Lethal trifecta"** (özel-veri + dış-erişim + kontrolsüz-içerik, Oca 2026):
  63-A'nın kural-seti üçlemeden **dış-erişim bacağını** kısaltır — host-beyaz
  listesi + per-request/daily cap + escalate kuyruğu.
- **RAG-manipülasyonu ~%90** (5 kurgu-belge, Haz 2026; ⚠️): `x402_payee_verified`
  + `reputation_min` şartı, katalog-açıklamasına güvenen ajanı politika-zırhına
  alır.
- **KYA yakınsaması:** Skyfire'ın "Know Your Agent" kimlik+yetki platformu
  (günc. 8 Eyl 2026) `x402_payee_verified` alanının sektörde karşılığı olduğunu
  teyit eder — alan-adı 68-RobotProof köprüsüyle hizalı kalır.

**Satış-cümlesi (kurumsal):** "Ajanınız injection'a uğrarsa, cüzdan politikanız
uğramaz — kurallar modelin dışında, fail-closed ve imzalı çalışır."
Sektör-standardı: test-vektörleri (§4) + AgentSecBench-tipi tool-use bütünlük
değerlendirmesi (May 2026) B-katmanı kabul-ölçütlerine aday.
