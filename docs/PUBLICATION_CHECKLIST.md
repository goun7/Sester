# SESTER — Yayın-Kontrol Listesi (sester 0.5.0)

> Amaç: gerçek yayını (GitHub + PyPI) tek oturumda hatasız yapabilmek.
> Aşağıdaki her madde ya ✅ tamamlandı ya da ☐ kullanıcı-eylemi.
> Tarih: 2026-09-13 · Kimlik: **SIKKE → SESTER** (bkz. `ESKI_KIMLIK.md`)
> Hazırlık durumu: **KAPI YEŞİL + PRIVATE PUSH TAMAM (2026-09-13): 3. koşum sıfır
> RED; commit 995374f → github.com/goun7/sikke (private) — kalan: rename + PyPI**

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

## 2) GitHub — ✅ private yayında (github.com/goun7/sikke → rename: sester)

- [x] `git init` + private push — **v0.5.0 CANLI: commit 995374f (2026-09-13,
      101 dosya, +4909); uzak-ad `goun7/sikke` (0.3.1-dönemi adı — rename-adımı
      bunu hedefler)**
- [x] CI yapılandırması: bridges-job kardeş-repo variable'larına bağlı (doğru-skip)
- [ ] **Kullanıcı-eylemi:** GitHub fatura/spending-limit düzelt → `gh run rerun`
      (son CI: billing engeli — kod-hatası değil)
- [ ] **Tek-komut:** `PUSH=1 REPO_RENAME=1 bash scripts/publish_gate.sh`
      → `gh repo edit goun7/sikke --name sester` + About/topics (commit/CI
      geçmişi korunur; değişiklik-yoksa `commit yok — devam` der, rename yine koşar)
- [ ] **Repo-ayarları (rename-ötesi):** `docs/GITHUB_SETTINGS_CHECKLIST.md`
      — social-preview/avatar, release-tag, branch-koruma, security-özellikleri,
      workflow-permissions, homepage (PyPI-sonrası)
- [ ] About/topics: description *"x402-style metering, quota, fail-closed policy
      and hash-chain receipts for AI-agent APIs — one ASGI middleware"*;
      topics: `x402` `ai-agents` `metering` `payments` `asgi-middleware` `fintech`
- [ ] Sosyal-önizleme: Settings → Social preview → `.github/assets/og.png`
      (kapı-adımı 4 üretilir; 1280×640); repo-avatar: `.github/assets/avatar.png`
- [ ] Release: tag `v0.5.0` + not olarak `CHANGELOG.md` §0.5.0
- [x] **(Tek-seçim) Eski-repo stratejisi: A) Rename (SEÇİLDİ).** `PUSH=1
      REPO_RENAME=1` aynı repo'yu (995374f geçmişiyle) `goun7/sikke` →
      `goun7/sester`'a çevirir; B) sil+taze-aç gereksiz (geçmiş zaten push'landı —
      kanıt-değeridir)

## 3) PyPI — ☐ kullanıcı-eşik-kararı + kullanıcı-eylemi

> **Lisans-eşiği (2026-09-13):** PyPI-dağıtım + Apache-2.0 LICENSE = **kaynak-açık
> olur** — bu bir yan-etki değil, lisansın tanımıdır; GitHub-private kalmak bunu
> değiştirmez. İki meşru yol (karar kullanıcıya ait):
> **A) Açık (mevcut yapılandırma):** Apache-2.0 kalsın — benimseme, görünürlük
> ve katkı kazanılır; çekirdek fork'a-açık kalır (koruma telif + topluluk'tur).
> **B) Kapalı-çekirdek:** `sester` çekirdeği PyPI'dan çekilir; yalnız
> entegrasyon-istemcisi (istekte-bulunan zarf üreticisi, sınırlı SDK,
> Apache/MIT) yayında kalır — doğrulanabilir-kanıt katmanı (hash-chain,
> fail-closed) müşteri-yanı güveni taşır ve kapalı-senaryoda SATIŞ-ARGINI'DIR.
> Değişiklik ~35 dk (pyproject + README + kapı-yeniden-koşumu).
- [ ] **Eşik-kararı:** §3 A mı B mi? (A ise aşağıdaki adımlar aynen koşar;
      B ise önce çekirdek-çekilmesi yapılır)
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
- Kaynak-yüzeyi (2026-09-13): kablo/README/CHANGELOG/SEED GitHub'ta sester-pure
  (repo-adı dışında; önceki-kimlik referansları bilinçli-kalıcı — ESKI_KIMLIK.md
  sözlük + denetim-kanıtı). PyPI-eşiği (§3 A/B kararı) çözülmeden upload YOK.
- Kardeş-repolar (Tamga/Veridict) yayınlansın istiyorsak bridges-job'un
  değişkenleri (SESTER_TAMGA_REPO / SESTER_VERIDICT_REPO) o repoların
  yayınlanmasından SONRA ayarlanmalı (aksi halde checkout-hatası).
- Eski `sikke` dağıtım-adı yayınlansın istenirse: tombstone-sürüm (0.4.0.post1)
  `pip install sikke` → "renamed to sester" mesajıyla yayınlanabilir (opsiyonel).
