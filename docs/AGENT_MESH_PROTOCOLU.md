# AGENT-MESH PROTOKOLÜ — kardeş-proje ajan-koordinasyonu (v1, 2026-09-13)

> Taraflar: **63-Sester** · **64-Tenderix** · **TamgaProtocol** · **Veridict**
> Amaç: ajanlar arası **mesaj-taşıyıcılığı kaldırmak** — koordinasyon iki
> mekanizmayla otomatikleşir: (1) **HAT DEFTERİ** (ortak kayıt-defteri,
> `post-commit` hook'ları yazar), (2) **repo-içi guard'lar** (sözleşme-satırları
> commit-anında fail-loud denetlenir; drift içeri girmeden bloklanır).

## 1) Kurulum (bir-kerelik; idempotent)

```bash
bash /home/gokun/projects/01_unicorn/63-Sester/scripts/install_hooks.sh
```

Kurucu her repo'ya iki hook yazar (`.git/hooks/` — izlenmez, makine-yerel):

| Hook | Ne yapar | Bloklama |
|---|---|---|
| `pre-commit` | repo'nun guard-script'ini koşar (sözleşme-denetimi) | RED → commit BLOKLANIR |
| `post-commit` | commit-bilgisini HAT DEFTERİ'ne ekler | ASLA bloklamaz |

Mevcut marker'sız hook'lar EZİLMEZ (kullanıcının hook'u korunur); marker:
`# AGENT-MESH`.

## 2) Sözleşme-matrisi (her guard neyi korur)

| Repo | Guard | Korunan sözleşme | Kaynak |
|---|---|---|---|
| 63-Sester | `guard_sester.py` | sürüm-senkronu (pyproject==`__version__`), DONUK `source:"sikke"` üretimi; gözlem: kardeş K1-alıcısı çift-ad-okuma | `ESKI_KIMLIK.md`, K0 §5 |
| 64-Tenderix | `guard_tenderix.py` | bridge_version=2: `RAILS` kanonik `sester_*`, `RAIL_ALIASES` çift-ad-okuma, `LIVE_DISABLED_UNTIL_PSP_CERT` | `63_SESTER_ALINAN_NOT.md` |
| TamgaProtocol | `guard_tamga.py` | **anti-revert**: K1-alıcısı `sikke|pugio` kabul, bilinmeyen RED, tamper RED (stage-edilmiş içerik test edilir) | K0 §5 okuma-uyumu |
| Veridict | `guard_veridict.py` | K3 selftest: temiz→PASS, kurcalanmış→RED | K0 §6 |

Guard-disiplin: guard **kendi tarafının kusurunu bloklar**; **karşı-tarafın
driftini yalnız WARN'lar** + HAT DEFTERİ'ne drift-satırı düşer (karşı-repo
fail-loud'u bize değil onlara ait).

## 3) Drift-playbook (mesaj-taşıyıcı YOK)

1. Commit-anında guard RED → kendi-drift → **düzelt, sonra commit**.
   `--no-verify` **YASAKTIR** (tek istisna: kullanıcının yazılı emri).
2. Test/suite karşı-drift yakalarsa (örn. test_74) → kendi-tarafın guard'ı
   sonraki commit'te WARN + defter-e drift-satırı düşer → **driftin sahibi
   defteri okuyup düzeltir**.
3. Manuel olay (karar, teyit, uyarı, nota) → HAT DEFTERİ §Manuel-günlüğe
   tek-satır (Tarih | Kim | Olay).
4. Her ajan oturuma **READ-FIRST** ile başlar: HAT DEFTERİ son-20-satır.

## 4) HAT DEFTERİ yazım-kuralı (post-commit)

Satır-biçimi: `| YYYY-MM-DD HH:MM | <repo> | <short-sha> | <konu-ilksatırı> |`
— append-only, asla yeniden-yazılmaz; otomatik-bölüm ile manuel-bölüm ayrıdır.

## 5) İletişim-önce kuralı (Tamga-ratifikasyonu, 2026-09-13)

> "Patches arrive through a message first, working tree second." —
> TamgaProtocol kabul-notu (commit f6ee3b7); 63 tarafı KABUL ediyor.

K1/K3 gibi **karşı-repo dosyalarına** dokunulacaksa sıra şudur:
1. Kısa spec-notu (ne, neden, hangi kaynak-belgeyle) → HAT DEFTERİ §Manuel +
   karşı-tarafa ilet;
2. Karşı-taraf ya kendi yazar ya da patch'i spec-e dayanarak kabul eder —
   çalışma-kopyası-önce **değil**; revert-doğru davranıştır (fail-loud iki-yönlü).
3. Kabul olduktan sonra: karşı-taraf kendi tızağını (örn. AT-024) işler;
   63-tarafı guard'ı drifti gözlemlemeye devam eder.

Tarihçe-düzeltmesi: 63'ün patch-yorumundaki "bridge_version=2 çift-ad-okuma"
ifadesi spec-başlığı-yansımasıydı — K0 anchor-zarfı **v1'de kalır**, versiyon-
kapısı bağımsızdır (Tamga doğru düzeltti; 63 artefaktlarında ifadeler
senkronlandı: `bridge_receivers/`, `tests/test_payee_registry.py`, K0 §5).

## 6) Sınırlar (dürüstlük)

- Hook'lar makine-yereldir (`.git/` izlenmez) — taze-clone'da kurucu bir-kez
  koşulur; CI'da hook-yok, sözleşme CI-testlerinde de sabit (çift-katman).
- Guard'lar pür stdlib; ağ-çağrısı yapmaz; 30s timeout'lu subprocess-yalnız.
- Defter ortak-dizindedir (projects-kökü) — backup sorumluluğu kullanıcıda.
