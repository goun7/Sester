# Pazar Boşluğu — MCP Registry'lerde Ödeme-Kanıtı Yok

**Tarih:** 2026-09-28

---

## 1. Gözlem

Brifing: Smithery üzerinden ~715 MCP sunucusu taranmış ve **ödeme-kanıtı /
receipt-ledger / payment-proof çözümü bulunamamış**. Bu oturumda o tarama
yeniden yapılmadı (dürüst-not §4); bunun yerine **kanıtlı-yapısal** argüman:

1. **Akademik kanıt** (01 dokümanı): 15/15 facilitator ihlali, 40 yeni formal
   bulgu, %90/56/73 saldırı-başarısı — hepsi tek bir şey söyler: ödeme-yapan
   ajan altyapısı var, **dışarıdan-denetlenebilir kanıt** yok.
2. **Protokol-kanıtı**: x402'nin resmi terimler-sözlüğünde
   (`facilitator`, `resource server`, `client`) "receipt" bir rol-değildir;
   spec `PAYMENT-RESPONSE`'u settlement-yanıtı olarak tanımlar — alıcının
   bağımsızca arşivleyip yeniden-doğrulayacağı bir kanıt-nesnesi değil.
   Kaynak: <https://github.com/x402-foundation/x402>
3. **MCP ekosistemi**: MCP 2025-06-18 spec'inde tools/prompts/resources vardır;
   bir ödeme-kanıtı aracı registries'de doğal bir boşluktur çünkü "ödeme"
   tool'ları genellikle *ödeme-yapma* (GPU/SaaS satın-alma) için tasarlanır,
   *ödeme-kanıtlama* için değil. Spec: <https://modelcontextprotocol.io/specification/2025-06-18>

**Sonuç:** Sester'ın `pay` + `verify_receipt` + `balance` + `history` araç-seti
ilk **ödeme-kanıtı MCP server**'ı olarak konumlanır — yalın ödeme-istemcisi
değil, denetim-aracı.

---

## 2. Farklılaştırma — neden bir ödeme-MCP'si değil bir kanıt-MCP'si

| | Tipik ödeme-MCP'leri | Sester MCP |
|---|---|---|
| Değer vaadi | "Ajanınla öde" | "Ajanının ödediğini **kanıtla**" |
| Alıcı tarafı | Sunucuya güven | **Sester kurulu değil** → sha256 ile doğrula |
| Sır yönetimi | API-anahtarı gerekir | `proof` secret'sız; sır yalnızca opsiyonel anchor için |
| Maliyet | Ana/mainnet gerekir | **$0 embedded mod**, testnet/anvil yok |
| Denetim | Sağlayıcı paneli | Açık `receipt.json` + `sester verify` + evidence-bundle |

---

## 3. Yayın-planı (ücretsiz tier'lar)

1. **Smithery** (<https://github.com/smithery-ai/cli>): `smithery mcp publish`
   (URL veya `.mcpb` bundle). Yapılandırma: `mcp/smithery.yaml`.
2. **Arcade**: aynı stdio komutu `python mcp/server.py`.
3. **Claude Desktop / Cursor config** — manuel stdio girişi:
   ```json
   {"mcpServers": {"sester": {"command": "python",
     "args": ["/path/to/Sester/mcp/server.py"],
     "env": {"SESTER_MCP_SECRET": "...", "SESTER_MCP_NODE_SECRET": "..."}}}}
   ```
4. **Doğrulama-kanalı**: her yayın için `tests/test_mcp.py` + README'deki
   el sıkışma örneği çalıştırılır (CI-dışı elle; yerel stdio).

---

## 4. Dürüst-not ve sınırlar

- "715 MCP / sıfır ödeme-kanıtı" sayısı **brifing-varsayımıdır**; bu oturumda
  Smithery registry API'si ile yeniden sayılmadı (API üzerinden arama
  denenmedi). Doğrulamak için: `smithery mcp search payment` /
  `smithery mcp search receipt`.
- Bu doküman **pazar-iddiası** belgeler; rakip-isim listesi içermez
  (süzülmemiş registry verisi yok).
- MCP registry'de gerçek boşluğun kalıcı olması beklenmemeli — bu, **zaman
  penceresi**dir; teknik değer, `verify_receipt`'in sıfır-güven
  yeniden-hesaplanabilirliğinde ve fail-closed doktrinindedir.
