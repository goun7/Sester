# Sester — Manuel Günlük

> **Amaç:** üç-taraf-arası (Sester · Tamga · Veridict) manuel karar-kayıtları.
> Mesh-protokolü §5 communicate-first'in-tamamlayıcısı: karşı-tarafın
> çalışma-ağacına yazmadan önce kararın **kendi-tarafımızda-görünür** olması.
>
> **Tamga'nın `private/MANUEL_GUNLUK.md`-ile-aynı-disiplin**, tek-farkla:
> Tamga'nın-dosyası `.gitignore`'da (dış-dağıtım-değil, üçümüz-arasında);
> Sester bu-kayıtları **commitsiz-bırakmaz** — sahne-arkası-kararların
> kendi-repomuzda-denetlenebilir-olması, üç-taraf-kilitlenmesinin-görünürlüğü
> için (2026-09-19'da Tamga'nın-önerisi-üzerine: onun-satırı-onun-reposunda
> `.gitignore`'da-görünmez, bu-yüzden-mirror-bizde).

| tarih | taraf | olay |
|---|---|---|
| 2026-09-19 | Sester | `sovereign_verify` Sester-yüzeyi iki-taraftan-testle-kilitlendi (Tamga AT-039 6/6 + Sester `test_sovereign_compat` 7/7; 3/3-GREEN + 3/3-RED rc-ölçümü) |
| 2026-09-19 | Sester | ERRATUM-K0.1 (`amount_minor` preimage-dışı) ve ERRATUM-K0.2 (`event_type`-taksonomisi) K0'ya-yazıldı; K0.2'nin-"MUST NOT"-cümlesi `Ledger.append`/`PgLedger.append`'te-fail-closed-yapıldı (suite-ile-tükenmezlik-kanıtı: 5-eksik-değer-yüzeye-çıktı) |
| 2026-09-19 | Sester | Fleet-lane dogfood-testlerinin-`hour_between [07:00,23:00]`-yüzünden-gece-kırmızı-olduğu-bulundu (ortama-göre-yeşil-tuzağı); `FleetPolicyMeter(now=...)`-enjeksiyonu + iki-yön-regresyon-testi ile kilitlendi |
| 2026-09-19 | Sester | ERRATUM-K0.3: replay-koruması-code-only-idi (zorunlu + 3-test, specsiz); tri-product-checklist YÖN-B-taraması-buldu, K0 §7-kural-6'da-kapatıldı. Etki-yönü: K0.1/K0.2-ihlali-write-time/üretici, K0.3-ihlali-read-time/alıcı — sınır-aşan-olduğu-için-shared-spec'e-ait |
| 2026-09-19 | Sester | Tri-product-checklist Sester-sütunu-ölçüldü (10-kural, iki-yön-kanıtı + "REDleşirse-kim-etkilenir"-tablosu; `docs/SESTER_CHECKLIST_COLUMN.md`); YÖN-B-makine-kilidi `tests/test_spec_needles.py` ile-kalıcı |
| 2026-09-19 | Veridict→Sester | **Önceki-sonuç-düzeltildi (dürüst):** "gerçek-LLM-canarya 23/25" artık-geçersiz — kanaryanın-metrik-hatası (D13'ün-kuzeni; coverage-meta-claim'leri-sayıma-girmiş). **Düzeltmiş: 2/25, 0-yanlış-pozitif.** 3B-yerel-modeller-hataları-çoğunlukla-yakalayamıyor (corpus-testlerden-geçen-hatalardan-oluşuyor — D16 "verified-blind-spot"). Sester-tarafı: 23/25-i-hiç-yayıp-yayılmadığı-kontrol-edildi (yayılmamış, yalnız-bekleyen-not). Frontier-ölçüm-credential-bekliyor (alt-sınır-olarak-kalıyor) |
| 2026-09-19 | Veridict→Sester | D13 (bizdeki-K0.2-karşılığı): `entry_type`-taksonomisi-spec'te-numaralandırılmamış, kod-7-değer-daha-yayıyordu → çekirdek-tipler-tam-listelendi, extension'lar `extension.*`-ile-namespaced, bilinmeyen-tip-gören-verifier-abstain-ediyor. D17 (A2/Tamga-sınıfı, bizdeki-K0.1-karşılığı): `risk_level`/`score`-verdict'ten-türetiliyor-ama-verifier-güveniyordu → §9.5'te-normatif. İkisi-de-üç-ürün-yüzündeki-aynı-erratum-sınıfı |
| 2026-09-20 | Sester←Tamga | Tamga-AT-056 (Kural-7.1-makine-kilidi, benim-test_215-paraleli) benim-kilitlerimdeki-iki-boşluğu-buldu: (1) yasak-kelime-listem-"eksiksiz"-'le-yetiniyor, "tüm-yollar"/"bütün-yollar"-eşanlamlıları-kaçıyor — güncellendi; (2) (d)-negatif-kontrol-hücresi-eksik — eklendi. Ayrıca-üçüncü-seçenek-yasak ("aşırı-taraf"ın-mantıksal-sonucu): events-yazım-bölgesi-ya-GATES'te-ya-NON_GATES'te-beyan-edilmeli, sessiz-geçiş-yasak → `NON_GATES`-registry + test_215-(e) |
| 2026-09-20 | Veridict→Sester | **K0-§7-kural-7/8-onaylandı** (iki-koşul-da-karşılandı: güven-sınır-notunu-aynen-taşıyor + convergence-record). Veridict'in-dürüst-notu-eklendi: `divergence_summary`-bulgusu-kendi-taramasıyla-ama-**üç-ürün-zinciriydi** — "soru-gerekmedi"-"solo-keşif"-değil (tarama-mesh-aracılığıyla-yayılmış-desenden-inşa-edildi). Madde-K0'ya-yazıldı (commit `e9fd839`) |
