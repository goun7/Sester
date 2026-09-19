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
