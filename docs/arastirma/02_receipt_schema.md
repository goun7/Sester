# Ödeme Kanıtı (Receipt) — Şema Tasarımı ve Gerekçesi

**Soru:** "Ödendi" iddiasını dışarıdan doğrulanabilir bir kanıta dönüştürmenin en
iyi formatı nedir? Bu doküman, Sester'ın v1 receipt şemasının tasarım
kararlarını harici standartlara dayanarak gerekçeler.

---

## 1. Tasarım hedefleri (sıralı öncelik)

1. **Sıfır-güven doğrulanabilirlik** — alıcı tarafı `sha256` dışında bir
   kriptografi, kütüphane veya sır bilmeden kanıtı yeniden hesaplayabilmeli.
   Gerekçe: USENIX-Sec-2026 bulgusu (2607.19545) facilitator'a güvenin
   merkezileştiğidir; kanıtın kendisi merkezileşmeyen bir yapıda olmalı.
2. **Node hesap-denkliği (non-repudiation-lite)** — node (sunucu) kanıtı
   imzalamalı; imza yoksa bile kanıtın özü geçerli kalmalı.
3. **Determinizm** — aynı ödeme → bayt-bayt aynı receipt JSON (alıcılar
   arşivleyip yeniden doğrulayabilmeli).
4. **Stdlib-only** — protokolün kendisi için sıfır zorunlu bağımlılık
   (RFC 2104 HMAC ve sha256 her yerde vardır).
5. **Minimal alan-seti** — her alan bir güvenlik-kararı ifade etmeli.

---

## 2. Şema v1 (donuk — değişiklik = v2)

```
receipt_version : 1                    # donuk sürüm-kilidi
iss             : node kimliği          # kanıt-üreticisi (RFC 7519'dan ödünç)
sub             : ödeyen ajan kimliği   # RFC 7519 "subject"
resource        : ödenen kaynak (host/path)
event_type      : "charge_receipt"      # yalnızca harcama (fail-closed)
amount          : "0.050000"            # 6-ondalık sabit-nokta (major)
amount_minor    : 50000                 # tam-sayı minor (USDC 6-dec)
currency        : "USDC-sim"
ts              : 1790627670.9845848    # UTC epoch (float, 6-ondalık)
seq             : 7                     # ledger sıra-no (denetim-izi)
payload         : '{"nonce":"n1",...}'  # sabit-sıralı JSON string
prev_proof      : önceki-olayın mührü   # HMAC zincir-bağlantısı (node ile)
proof           : <sha256 hex, 64>      # ASIL KANIT — secret'sız
chain_head      : <sha256 hex>          # üretim-anındaki ledger head
node_key_id     : "sester-node-1"       # anahtar-kimliği (key rotation)
node_cosign     : <HMAC hex>            # node anchor (D10-modeli)
```

### 2.1 Asıl kanıtın kanonik-formülü (herkes tarafından hesaplanabilir)

```
proof = sha256( f"{ts:.6f}" | event_type | sub | resource
              | f"{amount:.6f}" | payload | prev_proof )
```

Bu, Sester'ın kanıt-zinciriyle **birebir aynı kanonik**'tir
(`sester/evidence.py:proof_hash`); alıcı ister tek receipt, ister tüm
bundle'ı doğrulasın aynı formül çalışır. K0 sözleşmesinin donuk alanıdır:
sıralama/alan değişimi alıcıları kırar, bu yüzden yalnızca yeni sürümle.

### 2.2 Node anchor (cosign)

```
receipt_hash = sha256(receipt_canonical(receipt))   # 15 alan, sabit-sıralı
node_cosign  = HMAC-SHA256(node_secret, receipt_hash + "|" + node_key_id)
```

**Neden HMAC değil de asimetrik imza?** Stdlib-only kısıtı: `hmac`+`hashlib`
stdlib'dedir; `cryptography`/`eth-account` opsiyonel ekstralar. HMAC anchor
**symmetric-queue** modelini izler: alıcı ile node önceden sır paylaşmışsa
imzayı doğrular; paylaşmamışsa `proof`+`receipt_hash` yine de kanıtın özüdür.
`node_key_id` anahtar-rotasyonuna izin verir ve her imza anahtar-ayrımı taşır
(key separation).

### 2.3 Doğrulama-yolları ve yakalanan saldırılar

| Alıcının bildiği | Doğrulama adımları | Yakalananlar |
|---|---|---|
| Hiçbir şey (secret'sız) | (1) sürüm, (2) `proof` == yeniden-hesaplanan sha256 | tutar/kaynak/ajan/zaman/payload değişikliği; zincir-kopması (`prev_proof`); bozuk/sürüm-dışı receipt |
| + node-secret | (1)(2) + (3) `node_cosign` == HMAC | ek olarak `iss`/`amount_minor`/`currency`/`seq`/`node_key_id` değişikliği (metadata taklidi) |
| + tüm bundle | merkle-root + head + zincir | tek-olay-yerine toplu kanıt; sıralama-bozukluğu |

Önemli sınır (dürüst): **`seq` asıl-kanıtın içinde değildir** — secret'sız
modda `seq` bir *iddia*dır (proof, `seq`'yi sabitlemez). Zincir-pozisyonu
isteyen alıcı ya node-secret (cosign sabitler) ya da `sester bundle`
almalıdır. Bu K0 kanonik-dondurmasının bilinçli bedelidir.

---

## 3. Diğer kanıt-formatları ile karşılaştırma

| Format | Doğrulama için gereken | Sester'dan farkı |
|---|---|---|
| **x402 `PAYMENT-RESPONSE` header** (Settlement Response) | zincir-istemcisi + node doğrulaması | zincir-yerel; facilitator aracı-sıfır kanıt vermez (2607.19545'in bulgusu) |
| **EIP-3009 TransferWithAuthorization** (x402 `exact` scheme) | EVM node + abi-kod çözme | zincir-üzeri authorization; kanıt zincir-tarihine bağlı, yeniden-hesaplama kolaylığı yok |
| **RFC 7515 JWS** (Sester AP2/ACP/UCP'de kullanır) | imza-algoritması + anahtar-dağıtım | *niyet* imzası; "ödendi-sonrası kanıt" değil (Sester ikisini de kullanır) |
| **Merkle-bundle** (Sester evidence K0) | sha256 + tüm olaylar | toplu denetim için; tek-ödeme sorgusu için ağırdır → receipt onun tek-olay-projesiyonu |
| **RFC 2104 HMAC anchor** (Tamga D8/D10 modeli) | paylaşılan sır | Sester'ın `node_cosign`'inin modeli; tek-seferlik anchor |

İlham: Tamga'nın anchor modeli (kanonik → sha256 → HMAC anchor) ve x402'nin
402-el-sıkışması. Sester bunları **tek-olay, secret'sız-asıl-kanıt +
node-anchor** iki-katmanlı birleştirir.

---

## 4. Örnek — alıcı tarafı (Sester YOK)

```python
import hashlib, json

r = json.loads(receipt_json)                      # herhangi bir kanaldan
assert r["receipt_version"] == 1                  # 1) sürüm
manual = "|".join([                               # 2) asıl kanıt
    f"{float(r['ts']):.6f}", r["event_type"], r["sub"], r["resource"],
    f"{float(r['amount']):.6f}", r["payload"], r["prev_proof"],
])
assert hashlib.sha256(manual.encode()).hexdigest() == r["proof"]
print("kanıt: ", r["sub"], r["amount"], r["currency"], "→", r["resource"])
```

Aynı şey komut satırında: `sester verify receipt.json` (RC=0 KABUL, RC=1 RED).

---

## 5. Sürüm-politikası

- v1 alan-seti DONUK. Ekleme/çıkarma/yer-değiştirme YASAK.
- Yeni gereksinim → `receipt_version: 2` + alıcılar her ikisini de tanır.
- `receipt_version` dışında hiçbir alan sürüm-anlamı taşımaz.
