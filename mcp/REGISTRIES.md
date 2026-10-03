# MCP Registry Kayıt Rehberi — Sester

**Durum:** dosyalar HAZIR. **Kayıt YAPILMADI** — kullanıcı onayı bekleniyor.
Maliyet: **$0** (yalnızca ücretsiz tier'lar).

---

## 1. Smithery (öncelik)

Smithery, Arcade.dev'e katıldı (2026):
<https://arcade.dev/blog/smithery-joins-arcade>

**İki yayın yolu** (<https://smithery.ai/docs/build/publish>):

### A) Local — MCPB Bundle (bizim için uygun, stdio server)
```bash
npm install -g smithery@latest          # Node.js 20+
smithery auth login
# bundle paketle (.mcpb) sonra:
smithery mcp publish ./sester.mcpb -n <org>/sester
```
- Yapılandırma hazırdır: [`smithery.yaml`](smithery.yaml)
- Manifest: [`mcp.json`](mcp.json)
- Smithery server'ı tarayıp tool listesini çıkarır (initialize + tools/list).

### B) URL — Streamable HTTP + OAuth (kendi host'unuz)
```bash
# 1) Sester'ı HTTP uç noktası olarak yayınla (Streamable HTTP transport)
# 2) https://smithery.ai/new → HTTPS URL gir → yayınlama akışını tamamla
```
- OAuth gerekirse Client ID Metadata Documents ile otomatik.
- Tarama başarısız olursa statik kart:
  `/.well-known/mcp/server-card.json`

**Yerel deneme (kayıtsız):**
```bash
smithery mcp add ./mcp/server.py --id sester
smithery tool list sester
smithery tool call sester pay '{"agent":"demo","resource":"/weather","amount":0.05}'
```

### Smithery'de ne olacak (kanıtlanmış boşluk)
Smithery'nin kendi sayfası JS-rendered olduğundan server sayısı
**belirsiz**. Ancak Glama'da `receipt` + Payments & Billing kategorisinde
yalnızca **9 server** var (2026-09-28) ve en yakın rakip (`x402-receipt-verifier`)
**offline-doğrulanamaz** ve kendi platformuyla sınırlı. Konum:
`docs/arastirma/mcp-pazari.md` §2.3.

---

## 2. Glama.ai

- Directory: <https://glama.ai/mcp/servers> (**93,546 server**, 2026-09-28)
- **"Add Server"** formu: <https://glama.ai/mcp/servers> → "Add Server"
- GitHub repo URL'si + README yeter; Glama README'yi tarayıp tool'ları çıkarır.
- Kategoriler (önerilen): `Payments & Billing`, `Finance`, `Autonomous Agents`
- API ile programatik liste: `GET /v1/servers` —
  referans: <https://glama.ai/mcp/reference>

**Kayıt sonrası anahtarlar:** Glama "quality/maintenance" notu verir (A–F).
README'nin MCP bölümü + `mcp.json` bu notu yükseltir.

---

## 3. mcp.so

- Submit: <https://mcp.so/submit?type=server> (Repository URL + Name)
- **Ücretsiz tier:** form gönderimi → review süreci. **$39 ödeme YAPILMAYACAK**
  ($39 opsiyonel: anında yayın + verified badge + featured + dofollow link).
- Site kendi iddiası (belirsiz): DR 72, 2.2M ziyaretçi/12ay, 266K aylık aktif.
- Açık kaynaklı directory: <https://github.com/chatmcp/mcp-directory>

---

## 4. Punkpeye awesome-mcp-servers (GitHub list)

- Repo: <https://github.com/punkpeye/awesome-mcp-servers>
- Kayıt = **PR açmak** (ücretsiz, topluluk review'u).
- README'ye tek satırlık entry eklenir:
  `- [Sester](https://github.com/goun7/Sester) - Agent payment-proof tools: pay, verify_receipt, balance, history.`
- Mevcut listede "Payments" veya "Verification" bölümüne bakılmalı.

---

## 5. Manuel stdio config (yayın öncesi, herhangi bir MCP client)

```json
{
  "mcpServers": {
    "sester": {
      "command": "python",
      "args": ["/path/to/Sester/mcp/server.py"],
      "env": {
        "SESTER_MCP_SECRET": "üretimde-zorunlu",
        "SESTER_MCP_NODE_SECRET": "üretimde-zorunlu"
      }
    }
  }
}
```

---

## 6. Kayıt Öncesi Checklist

- [x] MCP server stdio'da çalışıyor (initialize + tools/list + tools/call)
- [x] `mcp/smithery.yaml` hazır
- [x] `mcp/mcp.json` hazır
- [x] `mcp/README.md` var (kurulum + tool listesi + örnek)
- [x] README.md'de MCP bölümü var
- [x] Pazar/boşluk araştırması: `docs/arastirma/mcp-pazari.md`
- [ ] **Kullanıcı onayı** → Smithery publish
- [ ] **Kullanıcı onayı** → Glama "Add Server"
- [ ] **Kullanıcı onayı** → mcp.so submit (ücretsiz tier)
- [ ] **Kullanıcı onayı** → Punkpeye PR
- [ ] Yayın sonrası: README'lere registry linkleri ekle
- [ ] Yayın sonrası: `docs/arastirma/mcp-pazari.md`'e gerçek install sayıları

**Not:** API anahtarları bu dokümanda YOK; tüm anahtarlar environment'te
tutulur ve asla ekrana yazılmaz.
