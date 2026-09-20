# Kardeş-Ürün'lere-Sorulacak-Kısa-Metinler

> **Amaç:** kullanıcı "diğer-projelerin-alanlarına-girenleri-onlara-sormam-için
> kısa-metinler-oluştur" dedi. Her-metin tek-önce-iletilecek-kadar-kısa, ve
> **yalnızca-o-ürünün-alanındaki-kararları**-soruyor (mesh-§5: çalışma-ağacına
> dokunma-yok, sadece-soru).

## Tamga'ya (LEDGER/kanıt-alanınız)

```
Sester'da-prototip-onayı-aldım (259 test, guard rc=0, cross-repo CI-artık-aktif).
Sizin-alanınıza-değen-iki-sorunuz:

1) x402-facilitator-secret'ı fail-closed-yaptım (üretimde SESTER_FACILITATOR_SECRET
   env'i-zorunlu; 'uvicorn --factory' argümansız artık-açılmıyor). Sizin
   tamga_anchor köprü-yüzeyinizde benzer-zayıf-varsayılan-secret var-mı? Varsa
   aynı-düzeltmeyi-öneririm — sizin-uyarlama-ki girersem-haber-verin.

2) Cross-repo CI-job'ımız-ilk-kez-koştu (SESTER_TAMGA_REPO set-edildi, run
   35527689113, 'Cross-repo bridges' 21s-yeşil). Sizin-ledger-spec'§6/§7'deki
   'üretici-zorunlu/alıcı-opt-in' kuralı için Tamga-tarafında-da-kendi
   normatif-needle-testiniz-var-mı? Sester'da-yaptım (S-5.1–S-5.5); parite-merakım.
```

## Veridict'e (verifier/jury-alanınız)

```
Sester'da-prototip-onayı-aldım (259 test, guard rc=0, cross-repo CI-artık-aktif).
Sizin-alanınıza-değen-iki-sorunuz:

1) x402-facilitator-secret'ı fail-closed-yaptım (SESTER_FACILITATOR_SECRET
   env'i-zorunlu; auth-key artık-tahmin-edilemez). Sizin-jury-anahtarlarınız
   zaten-os.environ'da (doğru), ama canary-receipt imzalarınızda-benzer
   varsayılan-secret var-mı? Varsa-öneririm; sizin-alanınız-olduğu-için-soruyorum.

2) D19'u-kendi-kapattığınızı-gördüm (a12711d, CI-yeşil). Cross-repo CI-job'ımız
   artık-her-push'ta-koşuyor — sizin-veridict_claims köprü-testleri-de-dahil.
   Veridict-tarafında-bu-köprü-testlerinin-devamlılığı-için-bir-registry
   istiyor-musunuz, yoksa-Sester-CI-yeterli-mi?
```

## Kullanıcı-için-not

Bu-metinler **sadece-soru-içerir** — hiçbir-tarafın-çalışma-ağacına-yazılmaz.
Cevaplar-gelecek-gibi ilgili-ADR'lere/notlara-işlenir.
