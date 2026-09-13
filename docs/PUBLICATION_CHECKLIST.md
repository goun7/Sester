# SESTER — Yayın-Kontrol Listesi (sester 0.5.0)

> Amaç: gerçek yayını (GitHub + PyPI) tek oturumda hatasız yapabilmek.
> Aşağıdaki her madde ya ✅ tamamlandı ya da ☐ kullanıcı-eylemi.
> Tarih: 2026-09-13 · Kimlik: **SIKKE → SESTER** (bkz. `ESKI_KIMLIK.md`)
> Hazırlık durumu: **dry-run tamam (0.3.x'te twine PASSED); 0.5.0 tek-komut-kapı hazır**
> (yerel-kapı: `bash scripts/publish_gate.sh` — canlı-E2E dahil)

## 1) Artefakt-hazırlığı — ✅ TAMAM (0.5.0 inşa-adımıyla)

- [x] Sürüm-bump: `sester/__init__.py`, `pyproject.toml` → **0.5.0** (senkron)
- [x] `CHANGELOG.md` — … / 0.4.0 / **0.5.0** (Keep-a-Changelog; S5+S6 girişleri)
- [x] Kimlik-göçü: paket `sikke` → `sester`; donuk kablo-alanları (pugio0,
      pugio_bundle_version, pugio_evidence_bundle, source:sikke) KORUNDU
- [x] Lisans: Apache-2.0 (`LICENSE`) + `pyproject license-files`
- [x] Paket-adı teyidi: **`sester`** — PyPI/Crates/NPM/.ai/.io taramaları %100 temiz (2026-09-13)
- [x] CI: `.github/workflows/ci.yml` (py3.11→3.14 + bridges-job kardeş-repo variable'larıyla)
- [x] **Tek-komut kapı YEŞİL (2026-09-13, 3. koşum):** 202+14 (SQLite) ·
      211+5 (PG, sıfır-skip) · S1/S2 KABUL · marka-PNG · build+twine PASSED
      (sester-0.5.0) · canlı-E2E T0–T10 **21/21**. Push için: `PUSH=1`;
      repo-rename+About için: `PUSH=1 REPO_RENAME=1`.

## 2) GitHub — ✅ private aktif (goun7/pugio-meter → sester)

- [x] `git init` + ilk commit + private push (pugio-meter adıyla, 0.3.1)
- [x] CI yapılandırması: bridges-job kardeş-repo variable'larına bağlı (doğru-skip)
- [ ] **Kullanıcı-eylemi:** GitHub fatura/spending-limit düzelt → `gh run rerun`
      (son CI: billing engeli — kod-hatası değil)
- [ ] **Kullanıcı-eylemi:** repo adı `goun7/pugio-meter` → **`goun7/sester`**
      (GitHub → Settings → General → Rename; URL-eski-ad otomatik-yönlendirir)
- [ ] About/topics: description *"x402-style metering, quota, fail-closed policy
      and hash-chain receipts for AI-agent APIs — one ASGI middleware"*;
      topics: `x402` `ai-agents` `metering` `payments` `asgi-middleware` `fintech`
- [ ] Sosyal-önizleme: Settings → Social preview → `.github/assets/og.png`
      (kapı-adımı 4 üretilir; 1280×640); repo-avatar: `.github/assets/avatar.png`
- [ ] Release: tag `v0.5.0` + not olarak `CHANGELOG.md` §0.5.0
- [ ] **(Tek-seçim) Eski-repo stratejisi** — yalnız yerel-kapı yeşilden sonra:
      **A) Rename (önerilir):** `REPO_RENAME=1 bash scripts/publish_gate.sh` aynı
      repo'yu `goun7/sester`'a çevirir — commit/CI geçmişi korunur, eski-URL
      otomatik-yönlendirir. **B) Sil + taze-aç:** `gh repo delete goun7/pugio-meter`
      (delete_repo yetkisi + yazılı onay ister; eski CI-run/issue geçmişi gider)
      → `PUSH=1 bash scripts/publish_gate.sh` ile goun7/sester'a taze push.
      A önerilir: geçmiş, kanıt-değeridir.

## 3) PyPI — ☐ kullanıcı-eylemi

- [ ] PyPI hesabı + 2FA doğrulanmış olsun
- [ ] `twine upload dist/sester-0.5.0*` (API-token ile; `--repository pypi`)
- [ ] Yayın-sonrası teyit: `pip install sester` (temiz venv) + `pip index versions sester`
- [ ] Sürüm-sonrası: `sester/__init__.py` + `pyproject.toml` → `0.5.1.dev0`

## 4) Yayın-sonrası doğrulama — ☐

- [ ] CI yeşil (GitHub Actions: test-matrisi + bridges)
- [ ] `pip install "sester[evm]"` + `"sester[jws]"` + `"sester[pg]"` extras'ları ayrı ayrı kurulur
- [ ] Showcase-rehberi ilk-kurulum: `docs/VITRIN_REHBERI.md` akışı birebir koşar
- [ ] `docs/adoption_log.md`'e yayın-satırı eklenir (benimseme-sayacı başlar)

## 5) Riskler / notlar

- Donuk kablo-alanları (pugio0, pugio_bundle_version, pugio_evidence_bundle,
  source:sikke) **v2'ye kadar değişmez** (ESKI_KIMLIK.md): kardeş-repo alıcıları
  bu değerleri bekler — README'de açıkça belgelenmiştir.
- Twine-upload **geri-alınamaz** (PyPI tek-yönlü): sürüm-no bir kez daha doğrulanmalı.
- Kardeş-repolar (Tamga/Veridict) yayınlansın istiyorsak bridges-job'un
  değişkenleri (SESTER_TAMGA_REPO / SESTER_VERIDICT_REPO) o repoların
  yayınlanmasından SONRA ayarlanmalı (aksi halde checkout-hatası).
- Eski `sikke` dağıtım-adı yayınlansın istenirse: tombstone-sürüm (0.4.0.post1)
  `pip install sikke` → "renamed to sester" mesajıyla yayınlanabilir (opsiyonel).
