# MCP Server Pazarı 2026 — Dağıtım ve Rakip Analizi

**Tarih:** 2026-09-28 (canlı registry taraması ile)
**Amaç:** 4 MCP server'ımız (Kredent, Sester, Veridict, AnswRank) için pazar
konumunu **gerçek verilerle** belirlemek; brifingin "payment-proof MCP yok"
iddiasını **doğrulamak veya düzeltmek**.

> **Dürüst-not (önce):** Bu dokümandaki her sayı ve her rakip ismi
> **2026-09-28 tarihinde canlı olarak fetch edilen registry sayfalarından
> alınmıştır.** "Belirsiz" etiketli değerler ise doğrulanamamıştır ve
> brifing-varsayımı olarak kalmıştır. Bu doküman pazar-iddiası belgeler;
> finansal tavsiye değildir.

---

## 0. Yönetici Özeti — İDDİA

| # | İddia | Kanıt | Durum |
|---|---|---|---|
| 1 | MCP server pazarı büyüyor, 2026'da on-binlerce server var | Glama: **93,546 server** (canlı, 2026-09-28) | ✅ **DOĞRULANDI** |
| 2 | Brifing: "Smithery 715 MCP, payment-proof YOK" | Canlı Smithery `/servers` JS-rendered + login duvarı | ⚠️ **BELİRSİZ** (sayı yeniden sayılamadı) |
| 3 | "MCP registry'lerinde payment-proof/receipt çözümü YOK" | Glama canlı arama: ≥6 receipt/proof player mevcut | ❌ **GEÇERSİZ** — pazar hareket etti |
| 4 | **Güncel boşluk:** *offline-verifiable, asymmetric, platform-bağımsız* receipt | En yakın rakibin kendi README'si: "not offline-verifiable", tek-platform | ✅ **DOĞRULANDI** (rakip dokümanından) |

**Sonuç:** "İlk ve tek payment-proof MCP" iddiası **sürdürülemez**. Defansif
konum: *"offline doğrulanabilen, platform bağımsız, $0 embedded payment-proof
ledger"* — bu dar pencere hâlâ açık ve kanıtlanabilir.

---

## 1. Pazar Büyüklüğü — Doğrulanmış Sayılar

### 1.1 Glama Registry (canlı, fetch: 2026-09-28 ~22:20 UTC)

- **Toplam: 93,546 MCP server** (sayfa üzerinde "Updated 2026-09-28 22:25")
  - Araştırma süresince **canlı büyüme gözlendi**: 93,542 → 93,544 → 93,546
    (4 server eklendi ~7 dakika içinde). Bu, sayının gerçek-zamanlı olduğunu
    ve pazarın aktif büyüdüğünü gösterir.
- Kaynak: <https://glama.ai/mcp/servers>

**Kategori dağılımı (query'siz ana sayfa):**

| Kategori | Sayı |
|---|---|
| Python (dil) | 39,139 |
| Remote-capable | 38,898 |
| TypeScript (dil) | 33,352 |
| Local-only | 33,247 |
| Tools capability | 32,316 |
| Developer Tools | 21,819 |
| **Autonomous Agents** | **6,441** |
| Finance | 6,246 |
| App Automation | 6,348 |
| Security & IAM | 4,418 |
| Agent Orchestration | 4,558 |
| Knowledge & Memory | 5,839 |

**Bizim kategorilerimizde sorgu-bazlı sayılar:**

| Sorgu | Payments & Billing | Finance | Security | Autonomous Agents |
|---|---|---|---|---|
| `payment` | **414** | 342 | 51 | 84 |
| `receipt` | 9 | 42 | 31 | 31 |
| `agent identity` | — | 390 | 773 | 1,964 |

> **Yorum:** `payment` sorgusunda 414 server "Payments & Billing" içinde —
> yani *ödeme yapma* araçları bol. `receipt` sorgusunda yalnızca 9 server
> "Payments & Billing" kategorisinde. **Miktarsal olarak receipt-ledger hâlâ
> niş**; ama sıfır DEĞİL (§3).

### 1.2 Smithery (Arcade.dev)

- **Durum:** Smithery, Arcade.dev'e katıldı — duyuru:
  <https://arcade.dev/blog/smithery-joins-arcade>
- **Server sayısı: BELİRSİZ.** `https://smithery.ai/servers` sayfası
  JS-rendered'dır ve login yönlendirmesi içerir; statik fetch ile toplam
  sayı okunamadı. Brifingdeki "~715 MCP" sayısı **bu oturumda
  doğrulanamadı** (belirsiz).
- **Yayınlama modeli (docs'tan doğrulandı):** artık GitHub-repo-hosting
  değil, iki yol:
  1. **URL** — kendi HTTPS uç noktanız (Streamable HTTP transport, OAuth
     destekli), Smithery Gateway proxy'ler. Giriş: <https://smithery.ai/new>
  2. **Local (MCPB Bundle)** — `.mcpb` bundle artifact'i ile lokal stdio
     server yayınlanabilir.
- Kaynaklar: <https://smithery.ai/docs/build> ·
  <https://smithery.ai/docs/build/publish> ·
  <https://smithery.ai/docs/concepts/cli>

### 1.3 mcp.so

- **Dizin + submit formu:** <https://mcp.so/submit?type=server>
- **Ücretlendirme (sayfadan):** "Paid submission **$39** one-time publishing
  fee — Publish immediately without review, Verified badge, Featured and
  priority placement, Dofollow project link".
  - ✅ **Ücretsiz yol da mevcut** (review süreciyle); $39 opsiyonel
    hızlandırma. **Para harcanmayacak** — ücretsiz tier kullanılacak.
- **Trafiği (site kendi iddiası, BELİRSİZ):** DR 72, 2.2M unique
  visitors/12mo, 6M pageviews/12mo, 266K monthly active users.
- Açık kaynaklı directory kodu: <https://github.com/chatmcp/mcp-directory>

### 1.4 Punkpeye awesome-mcp-servers

- GitHub listesi: <https://github.com/punkpeye/awesome-mcp-servers>
- PR-tabanlı topluluk listesi; kayıt = PR açmak. Ücretsiz.

### 1.5 Büyüme-oranı: BELİRSİZ

MCP server pazarının **yıllık büyüme yüzdesi** için bu oturumda doğrulanabilir
bir birincil kaynak (registry API historicals, analizci raporu) fetch
edilemedi. Tek kanıt **canlı artış** (§1.1: ~4 server / 7 dk). Büyüme oranı
için "belirsiz" denir; abartılı bir CAGR iddia EDİLMEZ.

---

## 2. AI-Agent Ödeme MCP'leri — Kim Var, Kim Yok

### 2.1 Ödeme-YAPAN MCP'ler (bizim değiliz)

Bunlar "ajanınla öde" vaadi; Sester/Veridict'in alanı DEĞİL:

| Server | Ne yapar | Güncel |
|---|---|---|
| [lfwin-payment-mcp](https://glama.ai/mcp/servers/litsen/lfwin-payment-mcp) | Sipariş oluştur, ödeme durumu, iade | 2026-06-03 |
| [SIBS Payment MCP](https://glama.ai/mcp/servers/RobsonAdvancula/sibs-payment-mcp) | Ödeme gateway (checkout, refund, Multibanco) | 2026-09-07 |
| [Signal402 Payment Guard](https://glama.ai/mcp/servers/zedili/Signal402-Amazon-Developer-Hackathon) | x402 satın-alma + insan onay/bütçe kontrolü | 2026-09-07 |
| [x402 MCP Payment](https://glama.ai/mcp/servers/motok2031/mcpx402chatgpt) | x402 ödeme | (sayfa) |

**x402 güvenlik connector'ları (ilgili ama farklı):**
[x402-payment-safety](https://glama.ai/mcp/connectors/io.github.AgentTanuki/x402-payment-safety),
[MandateShield AI Payment Evidence](https://glama.ai/mcp/connectors/com.mandateshield/payment-authority),
[Black_Wall x402 Payment Guardrail](https://glama.ai/mcp/connectors/com.blackwalltier.mcp/black-wall-x402-payment-guardrail),
[XGuard](https://glama.ai/mcp/connectors/io.github.moelayyan90/xguard)

### 2.2 Ödeme-KANITLAYAN MCP'ler — EN YAKIN RAKİPLER (brifing yanlıştı)

**Bunlar var.** Brifingin "payment-proof/receipt-ledger çözümü YOK" iddiası
**geçersizdir** — kayıt 2026-09-28'de en az 6 oyuncu gösteriyor:

| Server / Connector | Vaat | Zayıflık (kendi dokümanlarından) | Güncel |
|---|---|---|---|
| [**x402-receipt-verifier**](https://glama.ai/mcp/servers/nexus-mcp-infra/x402-receipt-verifier) (nexus-mcp-infra) | x402 ödeme loglarını teslimat loglarıyla denetler, **signed receipt** verir | **HMAC-SHA256 → offline doğrulanamaz**; key rotation tüm receipt'leri geçersiz kılar; **yalnızca NEXUS'un kendi asset'leri**; korelasyon **zaman-pencere heuristic'i** (hard-link değil); $0.02/doğrulama ücreti | 2026-09-03 |
| [SCVD General Store](https://glama.ai/mcp/connectors/store.scvd/general-store) | "Evidence observatory for agentic commerce": x402 preflight, receipt checks, settlement attestations | Connector (2,113 bağlantı) | — |
| [attestify-os](https://glama.ai/mcp/connectors/io.github.attestifyagent/attestify-os) | Governed agent execution: x402 payments, budgets, receipts, verification, audit | Connector | — |
| [ReceiptRail](https://glama.ai/mcp/connectors/io.github.xka0085-byte/receiptrail) | On-chain x402 delivery receipts, **Solana**, hash-locked | Zincir-bağımlı | — |
| [EVIDIQ Notary MCP](https://glama.ai/mcp/servers/evidiq/evidiq-notary-mcp) | AI inference'lar için kriptografik receipt, on-chain proof, x402 | Inference-odaklı | 2026-08-09 |
| [ailabra-agent-profit-ledger](https://glama.ai/mcp/servers/JSJFIN/agentapi) | Ajan P&L + signed operational reports, x402 micropayments | Muhasebe-odaklı | 2026-07-28 |
| [AgentIndex](https://glama.ai/mcp/connectors/io.github.cognivis/agentindex) | Trust scores + on-chain payment receipts x402 için | Connector | — |
| [A2A Replay Receipt](https://glama.ai/mcp/servers/clauxel/a2a-replay-receipt-mcp) | A2A failure replay + receipt issuance | Hata-tekrar alanı | 2026-05-20 |

### 2.3 En yakın rakibin kendi itirafı (kanıt)

`x402-receipt-verifier` README'si (fetch 2026-09-28) açıkça yazar:

> "The signed receipt … is an **HMAC-SHA256** … over the canonical JSON
> encoding of `receipt`, keyed by `NEXUS_RECEIPT_SIGNING_KEY`. This is
> **not an offline-verifiable signature** (that would need asymmetric crypto
> + a published public key — deliberately left out)… **Rotating
> `NEXUS_RECEIPT_SIGNING_KEY` invalidates every receipt** issued under the
> old key."

ve:

> "**Scope, on purpose:** only covers NEXUS's own already-deployed x402
> assets … Auditing a third party's payment claims against a third party's
> logs was the original, broader idea … and was explicitly flagged there as
> carrying legal/dispute-liability risk."

**Bu, bizim konumumuzu kanıtlar:** rakip (a) asimetrik crypto kullanmıyor,
(b) offline değil, (c) tek-platform. Sester ve Veridict ise Ed25519 +
content-addressed + **receipt tek başına doğrulanır** (bu oturumda stdio
JSON-RPC üzerinden initialize → tools/list → tools/call ile **kanıtlandı**,
bkz. §5).

---

## 3. Agent Kimlik MCP'leri — Kredent İçin

`agent identity` sorgusu (Glama, 2026-09-28) — rakipler VAR:

| Server | Vaat | Kredent'e göre farkı |
|---|---|---|
| [Agent Identity MCP Server](https://glama.ai/mcp/servers/AiAgentKarl/agent-identity-mcp-server) | Identity + trust scores + scoped tokens | Trust-score **SaaS kutu**; Kredent ise **deterministic, recomputable** formül |
| [Agent Identity Protocol (AIP)](https://glama.ai/mcp/servers/faalantir/mcp-agent-identity) | Crypto identity + signing | En yakın rakip; 10 ay güncellenmemiş (2025-11-30) |
| [ZeroID Agent Identity](https://glama.ai/mcp/servers/clauxel/zeroid-agent-identity-mcp) | Accountable identities + receipt export | 4 ay güncellenmemiş |
| [agent-identity-control-plane](https://glama.ai/mcp/servers/ZayLinux26/agent-identity-control-plane) | OAuth 2.1 resource server, policy-as-code | Kimlik-sağlayıcı değil, yetki-katmanı |
| [agent-identity-mcp](https://glama.ai/mcp/servers/flovoice53-tech/agent-identity-mcp) | Throwaway test identity (email/phone) | Test aracı; kalıcı kimlik değil |
| [Agent Identity Trust MCP](https://glama.ai/mcp/servers/CSOAI-ORG/agent-identity-trust-mcp) | Trust tools | 73 PyPI install; detay belirsiz |
| [viridis-agent-fleet](https://glama.ai/mcp/servers/jdhart81/viridis-agent-fleet) | Fleet identity registry | Fleet-yönetim |

**Kredent'in niş boşluğu:** W3C `did:key` (self-resolving, registry yok) +
Ed25519/JCS (RFC 8785/8032) + **offline doğrulama** + itibarın **auditable
formülü** (`score = base × integrity × volume_damping`). Rakiplerin çoğu ya
SaaS trust-score (şeffaf değil) ya OAuth-katmanı; "self-resolving DID +
offline attestation + recomputable reputation" üçlüsü birlikte niş.

---

## 4. AnswRank İçin — AEO/GEO MCP Alanı

`Agent Ready` (Glama, 2026-09-07, "AI agent readability scanner, 0–100
score") en yakın analog; **llms.txt/robots/JSON-LD üretimi + 5-model citation
testi** kombinasyonu AnswRank'in farklılaştırıcı tarafıdır. Bu oturumda
AEO/GEO sorgusu için derin tarama yapılmadı — **belirsiz** olarak işaretlenir;
yayın sonrası `smithery mcp search` / Glama sorgusu ile tamamlanmalı.

---

## 5. Bizim 4 MCP Server'ımız — Doğrulanmış Durum

**Doğrulama yöntemi:** her server stdio subprocess olarak başlatıldı,
JSON-RPC 2.0 üzerinden `initialize` → `notifications/initialized` →
`ping` → `tools/list` → `tools/call` çalıştırıldı (2026-09-28).

| Repo | MCP server | Tools | Protocol | Sonuç |
|---|---|---|---|---|
| goun7/Kredent | `kredent/mcp_server.py` (entry `kredent-mcp`) | `create_identity`, `attest`, `verify`, `reputation` | 2025-06-18 | ✅ PASS |
| goun7/Sester | `mcp/server.py` (stdlib) | `pay`, `verify_receipt`, `balance`, `history` | 2025-06-18 | ✅ PASS |
| goun7/Veridict | `mcp/veridict_receipt_mcp/server.py` | `issue`, `verify`, `revoke`, `list` | 2025-06-18 | ✅ PASS |
| goun7/AnswRank | `answrank/mcp/server.py` | `answrank_audit`, `answrank_citations`, `answrank_generate_fixes` | 2024-11-05/2025-06-18 | ✅ PASS |
| goun7/Swarmax | **YOK** | — | — | ❌ MCP server bulunamadı |

**Swarmax notu:** repo'nun `src/`, `scripts/`, `docs/` ve pyproject
entry-point'larında MCP server yoktur (eval/gözlemlenebilirlik framework'ü).
"4 MCP server" brifingi Swarmax için geçerli değildir; 4 çalışan server
yukarıdakilerdir.

**Ortak farklılaştırıcı (kanıt):** her 4 server da **$0, testnet/mainnet
yok, API anahtarı yok** çalışır; Sester/Veridict receipt'leri **offline ve
secret'sız** doğrulanır.

---

## 6. Güncellenmiş Pazar Konumu (iletilebilir)

**ESKİ (yanlış):** "MCP registry'lerinde payment-proof çözümü yok, biz
ilkiz."

**YENİ (kanıtlı):**

> "AI-agent ödeme-kanıtı alanı **oluşuyor** — en az 6 oyuncu var. Ama hâlâ
> açık olan pencere şu: **receipt'in tek başına, offline, asimetrik-imzalı
> ve herhangi bir platforma bağlı olmadan doğrulanabilmesi.** En yakın
> rakip (x402-receipt-verifier) kendi README'sinde 'offline-verifiable
> değil' ve 'yalnızca kendi asset'lerimiz' diyor. Sester ve Veridict ise
> Ed25519 imzasını receipt'in içine gömer — alıcı tarafında ne Sester
> kurulumu ne node-secret gerekir; `sha256` ile yeniden hesaplar."

**Üç konum cümlesi (registry açıklamaları için):**

1. **Sester:** "Agents pay, anyone proves. Node-cosigned receipts with
   zero-trust offline verification — no Sester install required to verify."
2. **Veridict:** "Signed proof-of-done. One self-contained receipt file;
   content hash + ed25519 recompute under your own hand, no ledger, no
   network."
3. **Kredent:** "did:key identity and offline-verifiable attestation for
   agents. Reputation is a published formula, not a platform score."

---

## 7. Kaynak Listesi (tümü 2026-09-28'de fetch edildi)

**Registry'ler:**
- Glama ana: <https://glama.ai/mcp/servers>
- Glama payment arama: <https://glama.ai/mcp/servers?query=payment>
- Glama receipt arama: <https://glama.ai/mcp/servers?query=receipt>
- Glama agent identity: <https://glama.ai/mcp/servers?query=agent+identity>
- Smithery docs: <https://smithery.ai/docs> · build: <https://smithery.ai/docs/build>
- Smithery publish: <https://smithery.ai/docs/build/publish> · CLI: <https://smithery.ai/docs/concepts/cli>
- Smithery yeni server: <https://smithery.ai/new>
- mcp.so submit: <https://mcp.so/submit?type=server>
- Punkpeye list: <https://github.com/punkpeye/awesome-mcp-servers>
- Arcade birleşme: <https://arcade.dev/blog/smithery-joins-arcade>

**Rakip detayları:**
- x402-receipt-verifier: <https://glama.ai/mcp/servers/nexus-mcp-infra/x402-receipt-verifier>
- EVIDIQ Notary: <https://glama.ai/mcp/servers/evidiq/evidiq-notary-mcp>
- ailabra-agent-profit-ledger: <https://glama.ai/mcp/servers/JSJFIN/agentapi>

**Spesifikasyonlar:**
- MCP 2025-06-18: <https://modelcontextprotocol.io/specification/2025-06-18>
- x402: <https://github.com/x402-foundation/x402>

---

## 8. Belirsizlik ve Sonraki Adımlar

**BELİRSİZ (bu oturumda doğrulanamadı):**
- Smithery toplam server sayısı (JS-rendered + login) — "715" sayısı
- MCP pazar yıllık büyüme yüzdesi (birincil kaynak yok)
- mcp.so trafik iddiaları (site-self-report)
- AEO/GEO MCP rakip taramasının derinliği (yapılmadı)
- x402-receipt-verifier'ın gerçek kullanım hacmi (sadece README var)

**Sonraki adımlar (kullanıcı onayı sonrası):**
1. `smithery mcp search payment` / `receipt` ile Smithery tarayınca §1.2
   sayısı netleşir
2. Glama API (`GET /v1/servers`, <https://glama.ai/mcp/reference>) ile
   kategori sayıları programatik teyit edilir
3. 4 server için hazırlanan `smithery.yaml` + `mcp.json` ile yayına geçilir
4. Yayın sonrası bu dokümana gerçek install/erişim sayıları eklenir
