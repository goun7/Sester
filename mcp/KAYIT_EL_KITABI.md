# MCP Registry Kayıt El Kitabı — Sester + Tamga (kullanıcı için 2 dakika)

> **Tarih:** 2026-10-18 · **Durum:** Her-iki-sunucu KODU-TEST-EDİLDİ ve
> bundle'hazır. Tek-eksik **tarayıcı-OAuth login** — bu bir kişinin yapması
> gereken 2-dakikalık adım.

---

## 0. NEDEN BU DOSYA VAR

Ben (agent) `smithery mcp publish` komutunu çalıştırdım ama Smithery
**tarayıcı-OAuth** istiyor — bir API-key veya `smithery auth login`deki
tarayıcı akışı. Bu, kullanıcının yapacağı şey. Bu dosya **kullanıcının
sırası geldiğinde elle çalıştıracağı** tam-komutları içerir.

**Önceden-ölçülmüş gerçek (tekrar-ölçmeye-gerek-yok):**
- sester MCP: initialize → tools/list → `pay` gerçek-çağrı → receipt +
  chain_head döndü, `balance` 0.05 harcamış gösterdi (2026-10-18)
- tamga MCP: initialize → tools/list (5 araç) → 8/8 pytest yeşil,
  TAM-SUIT 3096/3096 rc=0 (2026-10-18, 108.51 s)

---

## 1. SESTER — Smithery'ye yayınla ( öncelik)

### 1.1 Login (bir-kez, tarayıcı)

```bash
export PATH="$HOME/.local/npm-global/bin:$PATH"    # smithery 1.2.0 kurulu
cd /home/gokun/projects/00_TAMGA-MESH/sester
smithery auth login
```

Bu, bir tarayıcı açacak (veya bir URL basacak):
```
https://smithery.ai/auth/cli?s=<session-id>
```
Tarayıcıda GitHub/Google ile giriş yap. Komut **"Logged in"** basana kadar
beklesin.

### 1.2 Bundle'ı yayınla

```bash
smithery mcp publish ./mcp/sester.mcpb -n goun7/sester
```

**Beklenen:** Smithery server'ı bundle'ı tarayıp tool listesini
çıkaracak (initialize + tools/list   — bizde   zaten-ölçüldü, 4 araç:
pay/verify_receipt/balance/history) ve yayınlayacak.

### 1.3 Doğrulama (yayın-sonrası)

```bash
smithery mcp list 2>/dev/null | grep -i sester
# veya tarayıcı: https://smithery.ai/server/goun7/sester
```

---

## 2. TAMGA — Smithery'ye yayınla

Aynı-akış, tamga için ( sunucu yazıldı, test-edildi, pushlandı: commit 45f0f75):

```bash
cd /home/gokun/projects/00_TAMGA-MESH/tamga
smithery mcp publish ./mcp/tamga.mcpb -n goun7/tamga
```

**Araçlar (5):** verify_ledger, ledger_head, verify_attestation,
verify_charge, verify_bundle.

---

## 3. LOGIN-İSTEMEYEN alternatifler ( ben-yapabilirim — kullanıcıya-soru-sorma)

Bu üç kanal **OAuth-login istemez**, ama **insan-onayı** gerektirir
( PR açmak, form-göndermek). Bunları **kullanıcı-sırasına-bırakıyoruz**:

| Kanal | Ne-gerekiyor | Maliyet |
|---|---|---|
| Glama.ai | "Add Server" formu ( GitHub-repo-URL + README) | $0 |
| mcp.so | submit formu ( ücretsiz-tier, review-süreci) | $0 |
| punkpeye/awesome-mcp-servers | GitHub PR ( bir-satır-README-entry) | $0 |

**Neden-yapmıyorum:** Bunların her-biri **kullanıcı-hesabından** yapılırsa
anlamlı ( PR Nikon凄dir; form-domain-kredibilitesi-ister). Agent-olarak
kullanıcı-adına-pull-request-açmak **onay-sız** doğru-değil.

---

## 4. ZATEN-YAPILAN ( tekrar-yapma)

| Adım | Durum | Kanıt |
|---|---|---|
| sester MCP sunucusu | ✅ çalışıyor | initialize+tools/list+pay-çağrısı (2026-10-18) |
| sester.mcpb bundle | ✅ hazır | `mcp/sester.mcpb/` ( server.py + .mcp.json) |
| tamga MCP sunucusu | ✅ yazıldı+test-edildi | commit 45f0f75, 8/8+3096/3096 rc=0 |
| tamga.mcpb bundle | ✅ hazır | `mcp/tamga.mcpb/` |
| smithery CLI | ✅ kurulu | smithery 1.2.0, `~/.local/npm-global/bin` |
| verify-mcp-çağrıları | ✅ gerçek-protokol-üzerinden | MCP 2025-06-18 cevabı |

**Yapılmadı (neden):** `smithery mcp publish` — OAuth-login-gerekli,
non-TTY'de **readline-çökmesi** ( `ERR_USE_AFTER_CLOSE`) veriyor.
Tarayıcı-adımı kullanıcı-yapacak.

---

*Hazırlayan: agent · Kullanıcı-için-el-kitabı · 2026-10-18*
