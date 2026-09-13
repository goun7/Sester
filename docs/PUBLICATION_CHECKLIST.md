# PUGIO — Yayın-Kontrol Listesi (pugio-meter 0.3.0)

> Amaç: gerçek yayını (GitHub + PyPI) tek oturumda hatasız yapabilmek.
> Aşağıdaki her madde ya ✅ tamamlandı ya da ☐ kullanıcı-eylemi.
> Tarih: 2026-09-12 · Hazırlık durumu: **dry-run tamam, yayınlamaya hazır**

## 1) Artefakt-hazırlığı — ✅ TAMAM

- [x] Sürüm-bump: `pugio/__init__.py`, `pyproject.toml` → **0.3.0** (senkron)
- [x] `CHANGELOG.md` — 0.1.0 / 0.2.0 / 0.3.0 (Keep-a-Changelog)
- [x] Sürüm-notları: `docs/RELEASE_NOTES_v0.2.0.md` (0.3.0 notları CHANGELOG §0.3.0'da)
- [x] `twine check dist/*` → **PASSED** (wheel + sdist)
- [x] Wheel smoke-install (temiz venv): import + ACP akışı + **sıfır zorunlu-bağımlılık** teyidi
- [x] Lisans: Apache-2.0 (`LICENSE`) + `pyproject license-files`
- [x] Paket-adı teyidi: PyPI'da `pugio` alındı → dağıtım-adı **`pugio-meter`** (boş-teyitli, 2026-09-12)
- [x] CI: `.github/workflows/ci.yml` (py3.11→3.14 + bridges-job kardeş-repo variable'larıyla)

## 2) GitHub — ☐ kullanıcı-eylemi (karar: yayını kullanıcı yapıyor)

- [ ] GitHub'da repo aç: `pugio` (public; description: *"x402-style metering, quota, fail-closed policy and hash-chain receipts for AI-agent APIs — one ASGI middleware"*)
- [ ] `git init` + ilk commit (önerecek isimlendirme: `feat: pugio-meter v0.3.0 — protocol adapters, escalation, signed policy, PG backend`)
- [ ] `git remote add origin git@github.com:<kullanıcı>/pugio.git && git push -u origin main`
- [ ] Repo variable'ları (Settings → Secrets and variables → Actions → Variables):
      `PUGIO_TAMGA_REPO`, `PUGIO_VERIDICT_REPO` — bridges-job etkinleşir
- [ ] Release: tag `v0.3.0` + not olarak `CHANGELOG.md` §0.3.0

## 3) PyPI — ☐ kullanıcı-eylemi

- [ ] PyPI hesabı + 2FA doğrulanmış olsun
- [ ] `twine upload dist/pugio_meter-0.3.0*` (API-token ile; `--repository pypi`)
- [ ] Yayın-sonrası teyit: `pip install pugio-meter` (temiz venv) + `pip index versions pugio-meter`
- [ ] Sürüm-sonrası: `pugio/__init__.py` + `pyproject.toml` → `0.3.1.dev0` (dev-göstergesi)

## 4) Yayın-sonrası doğrulama — ☐

- [ ] CI yeşil (GitHub Actions: test-matrisi + bridges)
- [ ] `pip install "pugio-meter[evm]"` + `"pugio-meter[jws]"` + `"pugio-meter[pg]"` extras'ları ayrı ayrı kurulur
- [ ] Showcase-rehberi ilk-kurulum: `docs/VITRIN_REHBERI.md` akışı birebir koşar
- [ ] `docs/adoption_log.md`'e yayın-satırı eklenir (benimseme-sayacı başlar)

## 5) Riskler / notlar

- PyPI'da `pugio` adı ilgisiz bir ETL-motorunda — isim-karışıklığı için README ilk-satırında "import: `pugio`, package: `pugio-meter`" netliği var.
- Twine-upload **geri-alınamaz** (PyPI tek-yönlü): sürüm-no bir kez daha doğrulanmalı (0.3.0 her iki dosyada da — teyitli).
- Kardeş-repolar (Tamga/Veridict) yayınlansın istiyorsak bridges-job'un değişkenleri o repoların yayınlanmasından SONRA ayarlanmalı (aksi halde checkout-hatası).
