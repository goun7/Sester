# SESTER — Para-kazanma Senaryosu v1 (2026-09-13)

> Konum: **AI-ajan trafiğini ödeyen API-satıcıları için metering+politika katmanı.**
> Kitle: API'lerini AI-ajanlarına açan (veya açmak isteyip fatura-mantığı olmayan) satıcılar.
> Kayıt: çekirdek Apache-2.0 kalır — benimseme-önce doktrini (VITRIN_REHBERI +
> adoption_log kill-criterion disiplini). Gelir, benimsenen katmanın üstündeki
> doğal-yükseltme noktalarından alınır.

## Gelir-hatları (öncelik sırasıyla)

| # | Hat | Fiyat-çapası | Neden SESTER'da doğal | Ölçüt (kill/tut) |
|---|-----|--------------|----------------------|------------------|
| 1 | **Hosted facilitator** (x402 settle-as-a-service) | işlem başına **%1 + \$0.005**; ayda ilk 10k işlem bedava | Facilitator 402-akışının doğal-boğum noktası; `settlement.py` (keccak-batch) buraya kanıt-dokur | 3. ay sonunda ≥3 ödeyen satıcı |
| 2 | **Kanıt-arşivi / denetim** (81-MERGEN köprüsü) | satıcı başına **\$99/ay** + saklanan makbuz başına \$0.001 | Kanıt-bundle + tamga-çıpası zaten var; finans/sağlık-tikayet uyum-alıcısı | 6. ayda ≥1 kurumsal-pilot |
| 3 | **Enterprise self-host lisansı** | düğüm başına **\$499/ay** | S3 imzalı-politik + PG + onay-paneli kurumsal-istek listesi; kod açık kalır, destek/Sözleşme-ücretli | pilot→ödeme dönüşümü %20+ |
| 4 | **On-chain batch servisi** | batch başına gas + **%0.1** | `build_settlement_batch` çıktısı tek-tx'e indirger; yalnız on-chain-kesinlik isteyene | lane 1 alıcısının ≥%10'u talep eder |
| 5 | **Sabit-fiyat bağlayıcı paketler** (protokol/protokol) | **€2–3k** bağlayıcı | AP2/ACP/UCP/x402 kurulumu tekrar-edilebilir iş | çeyrekte ≥2 paket |

## Neden çekirdek ücretsiz (bilinçli karar)

1. **Adoption-önce:** benimseme-sayacı olmayan satıcı-hattı yoktur; 0 bağımlılıklı
   kurulum + 181-testlik gövde, vitrin-funnel'inin tek motoru.
2. **Komşuluk-güveni:** x402/AP2/ACP/UCP ekosistemlerinde açık-kod referans-
   uygulama olmak, lanes 1–2'nin satış-konusudur (kapalı-fork'ta olmaz).
3. **Rekabet-savunması:** savunulabilir katman kod değil, **çalışan facilitator +
   kanıt-arşivi + benimseme-verisi**dir.

## Yürütme-sırası (yayınla kilitle)

1. (Şimdi) private repo → monetization/repo-detay optimum → public-e hazır.
2. Public geçiş + `VITRIN_REHBERI` 3 kurulum → adoption_log'a satıcı-funnel'i kolonu.
3. Lane 1 MVP: facilitator'ı tek-bölge hosted'a al (mevcut `sester/facilitator.py`
   çekirdeği); faturalama = SESTER'nun kendi metering'i (dogfood — satış-demosu).
   → **KODLANDI (2026-09-13): `sester/facilitator_svc/` + `docs/S5_FACILITATOR_MILESTONE.md`**
   — verify/settle/refund + satıcı-metering (free-band+%1+$0.005, kanıt-olaylı)
   + settlement-batch; S6 ortak-sözleşmesi: `docs/S6_JOINT_ACCEPTANCE.md`
   (test_186–201 kodlu; koşu-kanıtı publish-gate'te).
4. Lane 2 MVP: evidence-bundle REST + aylık otomatik tamga-çıpası.

## Riskler / savlar

- **İsim:** kimlik-dizisi Pugio → Sikke → **Sester** (bkz. `ESKI_KIMLIK.md`);
  PyPI/Crates/NPM/.ai/.io taramaları %100 temiz (2026-09-13) — dağıtım-adı
  `sester`, README ilk-satırı netliği (checklist §5).
- **Protokol-kayması** → adaptör-tezi 4 kez doğrulandı (SPEC_FARK v3); UCP dahil
  dördü de tek-çekirdekte — kayma riski metre-katmanını değiştirmez.
- **Gelir-olmaz senaryosu** → kill-criterion'ları vurgu-yapar: hat tutmazsa sadece o
  hat kapanır; çekirdek açık-kod yolculuğuna zarar gelmez.
