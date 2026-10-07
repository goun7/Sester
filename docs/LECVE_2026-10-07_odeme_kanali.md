# LEÇVE — Academic grounding ek (2026-10-07): ödeme kanalları

> **README'ye eklenecek literatür ekidir.** Mevcut `README.md` içeriğine
> **dokunulmamıştır**; bu dosya `docs/` altında YENİ dosya olarak teslim
> edilmiştir (goal: doc bağlarını genişlet).
>
> **FP0:** aşağıdaki her alıntı `web_fetch` ile **HTTP-200 + tam başlık birebir
> eşleşmesi** ile doğrulanmıştır. Uydurma alıntı yoktur. Kanıt:
> [`orkestrasyon/docs/fp0_arxiv_manifest_2026-10-07.json`](../../00_TAMGA-MESH/orkestrasyon/docs/fp0_arxiv_manifest_2026-10-07.json).

---

## Academic grounding — 2026-09-22..2026-10-07 penceresi (payment-channels)

Sester'in "pooled liquidity, local enforcement" (birikmiş likidite, yerel
zorunluluk) okuması, ödeme-kanalı literatürüyle doğrudan örtüşüyor:

- **Sluice: Global Invariant, Local Enforcement for Pooled Payment-Channel
  Liquidity** ([arXiv:2609.29975](https://arxiv.org/abs/2609.29975),
  Wu/Sun/Guo/Zhu/Chen, cs.CR, 24 Sep 2026) — Lightning Network'te bir yönlendirme
  düğümü likiditesini kanallar arasında dağıtır;Sluice bu dağıtımı **küresel bir
  değişmezlik (global invariant) ile yerel zorunluluk (local enforcement)** olarak
  yeniden çerçeveleyerek, her düğümün kendi yerel kural setini küresel
  güvenlik özelliğini bozmadan uygulamasını sağlar. Sester'in metering katmanı
  aynı iki-katmanlı yapıya sahiptir: **küresel** kanıt, alıcının bağımsız olarak
  yeniden hesaplayabildiği hash-zinciridir (`sester verify`, saf `sha256`);
  **yerel** zorunluluk, düğümün sahip imzalı politikasıdır (sıkılaşma anında,
  gevşeme 24 saat gecikmeli). **Fark:** Sluice bunu bir yönlendirme ağı için
  kanal likidite denklemleriyle yapar — Sester ödeme kanalı yönetmez; onun
  yerine "küresel değişmezlik + yerel zorunluluk" ayrımını **makbuzun
  doğrulanabilirliği** eksenine taşır: alıcı, facilitator'a asla güvenmeden
  bir borçlandırmayı kanıtlar. Sluice, Sester'in okumasının ödeme-kanalı
  literatüründeki en yakın karşılığıdır ve onun "yerel zorunluluk" kavramını
  Sester'in `seen_nonces` fail-closed kapanışında somutlaşan desene
  bağlar.

---

*Bu ek, `README.md`'nin "Academic grounding" bölümüne eklenmek üzere
hazırlanmıştır.*
