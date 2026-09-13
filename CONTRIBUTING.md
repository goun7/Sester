# SESTER'ya Katkı (CONTRIBUTING)

Kısa ve sert kurallar — SESTER bir **fail-closed** ticaret-katmanıdır; PR'lar da
aynı disiplinle değerlendirilir.

## Geliştirme-kurulumu

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest tests/ -q          # 207 test + 9 PG-legi — hepsi yeşil olmadan PR açmayın
```

Postgres-parite bacakları (isteğe bağlı):

```bash
docker run -d --name sester-pg -e POSTGRES_PASSWORD=sester -p 5499:5432 postgres:16-alpine
export SESTER_PG_DSN="host=127.0.0.1 port=5499 dbname=postgres user=postgres password=sester"
pytest tests/test_pg_parity.py tests/test_minor_unit.py -q
```

## Sert kurallar

1. **Fail-closed bozulmaz.** Her yeni ret-yolu RED (açık-hata) üretir; sessiz-geçiş
   (fail-open) kabulü olan her PR reddedilir.
2. **K0 zarfı donmuştur.** `canonical_line` / kanıt-bundle şeması değişmez;
   uyumluluk-gerekçesi olmadan şema-PR'ı alınmaz (bkz. `docs/K0_SHARED_ENVELOPE_SPEC.md`).
   Aynı şekilde donuk kablo-alanları (`pugio0`, `pugio_bundle_version`,
   `pugio_evidence_bundle`, `source:sikke`) v2'ye kadar korunur (bkz. `ESKI_KIMLIK.md`).
3. **Test-önce.** Hata-bulucu testlerin geçmişi var (test_148 güvenlik-boşluğu,
   test_158 parite) — davranış-düzeltmeleri önce testle gelir.
4. **Sıfır zorunlu-bağımlılık.** Çekirdek yalnız stdlib; ağır-bağımlılık extras'a
   (`[evm]`, `[jws]`, `[pg]`, `[demo]`) gider.
5. **Secret'lar testlere girmez**; demo-anahtarlar/DB'ler env-override ile izole edilir.

## Sürüm-dili

- SemVer + Keep-a-Changelog; davranış-değişikliği olmadan `CHANGELOG.md`'siz PR yok.
- Sınır-ötesi (breaking) değişiklik: KARAR-kaydı ister (bkz. `KARAR_63B.md` biçimi).
