# Araştırma — x402 Ödeme Güvenliği ve Sester'ın Konumu

Bu dizin, Sester'ın **ödeme-kanıtı** özelliğinin akademik ve pazar gerekçesini
taşır. Her dokümanda atılan her kaynak 2026-09-28 tarihinde çekilip özetiyle
doğrulanmıştır; doğrulanamayan iddialar açıkça "kullanılmadı" olarak işaretlidir.

| Doküman | İçerik |
|---|---|
| [`01_x402_guvenlik_aciklari.md`](01_x402_guvenlik_aciklari.md) | USENIX Sec 2026 facilitator-ihlal çalışması, Tamarin formal analiz, AP2 whisper saldırıları (%90/56/73.3) + Sester'ın kapatığı/kapatmadığı açıkların dürüst tablosu |
| [`02_receipt_schema.md`](02_receipt_schema.md) | Receipt v1 şemasının tasarımı: kanonik formül, doğrulama katmanları, EIP-3009/JWS/Merkle karşılaştırması, alıcı-tarafı örnek kod |
| [`03_pazar_boslugu_mcp.md`](03_pazar_boslugu_mcp.md) | MCP registry'lerindeki ödeme-kanıtı boşluğu, farklılaştırma ve Smithery/Arcade yayın planı |

## Öz-özet (tek paragraf)

Üç bağımsız akademik çalışma aynı sonucu veriyor: ajan ödeme protokolleri
**imzayı** çözmüş ama **kanıtı** çözememiş — facilitator "ödendi" diyor ve
alıcı bunu bağımsızca kanıtlayamıyor (15/15 facilitator'da ihlal; 86 formal
vakada 40 yeni bulgu; AP2'de üç saldırı %90/56/73.3 başarı). Sester'ın
receipt'i bu boşluğu sıfır-güven `sha256` ile kapatır: alıcı tarafının
ihtiyacı olan tek şey `hashlib` — Sester kurulu değil, sır yok, internet yok.
MCP server bunu AI ajanlarının doğal araç-yüzeyine taşır ve registry boşluğu
ilk-mover konumu verir.
