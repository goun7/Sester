# SESTER MCP Server — ödeme-kanıtı araçları AI ajanları için

Model Context Protocol (**2025-06-18**) sunucusu. AI ajanları ödeme yapabilir,
aldıkları **node-cosigned receipt**'i bağımsızca doğrulayabilir. Saf-stdlib
Python — `mcp/server.py` tek dosya, ağır bağımlılık YOK.

MCP registry'lerinde **ödeme-kanıtı/receipt-ledger çözümü yoktu**; bu sunucu o
boşluğu doldurur (bkz. `../docs/arastirma/`).

## Araçlar

| Araç | Ne yapar | Girdi |
|---|---|---|
| `pay` | Ajan adına ödeme → **node-cosigned receipt** | `agent`, `amount`, `resource` |
| `verify_receipt` | Receipt'i **bağımsız** doğrula (alıcı tarafı) | `receipt` (JSON) |
| `balance` | Günlük harcama / kota / kalan | `agent` |
| `history` | Kanıt-zinciri olayları | `agent?`, `limit?` |

`verify_receipt` alıcı tarafındır: ne Sester kurulumu ne node-secret gerekir —
`proof` alanı `sha256` ile yeniden hesaplanır. "Ödendi" iddiasını üçüncü bir
taraf **kanıtlayabilir**; x402 facilitator'larının açık boşluğu (USENIX Sec
2026, `docs/arastirma/01_x402_guvenlik_aciklari.md`).

## Çalıştır — 30 saniye, $0

```bash
# 1) Bağımlılık YOK (stdlib). Repo kökünden:
export SESTER_MCP_SECRET=demo-secret-üretim-değil
export SESTER_MCP_NODE_SECRET=demo-node-key
python mcp/server.py                    # stdio JSON-RPC

# 2) Bir MCP istemcisinin bağlamında (ör. Claude Desktop config):
#    "command": "python", "args": ["<repo>/mcp/server.py"],
#    "env": {"SESTER_MCP_SECRET": "...", "SESTER_MCP_NODE_SECRET": "..."}
```

El sıkışmayı elle denemek:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"pay","arguments":{"agent":"demo","resource":"/weather","amount":0.05}}}' \
| python mcp/server.py
```

Çıktı bir `receipt` JSON'dur; `sester verify` ile komut-satırında doğrularsınız.

## Modlar

- **embedded (varsayılan)** — lokal SQLite kanıt-zinciri. Anahtar/testnet/mainnet
  YOK; `$0` ile başlanır. Kota: `SESTER_MCP_QUOTA` (varsayılan 5.00).
- **remote** (`SESTER_MCP_ENDPOINT`) — gerçek bir Sester-korumalı API'ye
  x402 HMAC ödemesi yapar (gerçek zincir). `SESTER_MCP_REMOTE_SECRET` gerekir.

## Çevre değişkenleri

| Değişken | Anlamı |
|---|---|
| `SESTER_MCP_DB` | Ledger yolu (varsayılan `sester-mcp.sqlite3`) |
| `SESTER_MCP_SECRET` | Ledger mührü — üretimde ZORUNLU; boşsa uyarır+demo ile çalışır |
| `SESTER_MCP_NODE_SECRET` | Node-cosign anahtarı; boşsa receipt cosign'siz (asıl kanıt yine de secret'sız doğrulanır) |
| `SESTER_MCP_NODE_ID` | Node kimliği → `receipt.iss` |
| `SESTER_MCP_QUOTA` | Ajan-başına günlük kota |
| `SESTER_MCP_ENDPOINT` | Remote mod URL'si |
| `SESTER_MCP_REMOTE_SECRET` | Remote modda sunucu ile paylaşılan sır |
| `SESTER_MCP_CURRENCY` | Para birimi etiketi (varsayılan `USDC-sim`) |

## Registry'ye yayınla

Smithery (Node.js 20+):

```bash
npm install -g smithery@latest
smithery mcp publish https://<sunucu-url> -n <org>/sester     # URL olarak
# veya bundle: smithery mcp publish ./sester.mcpb -n <org>/sester
```

Yapılandırma şeması `mcp/smithery.yaml`'dedir (stdio `startCommand` + env).
Arcade için aynı stdio komutu `python mcp/server.py` kullanır.

## Protokol uyumu

- JSON-RPC 2.0 over stdio, satır-başına bir mesaj
- `initialize` → `protocolVersion: "2025-06-18"`, `capabilities.tools`
- `notifications/initialized` → yanıt YOK
- `tools/list`, `tools/call` (`content[].text` + `isError`), `ping`
- Bilinmeyen metod → `-32601`; bilinmeyen araç → `-32602`
- Spec: <https://modelcontextprotocol.io/specification/2025-06-18>

## Test

```bash
.venv/bin/python -m pytest tests/test_mcp.py -q
```
