# Güvenlik Politikası (SECURITY)SESTER bir **fail-closed** ticaret-katmanıdır; güvenlik-bulguları birinci-sınıf
kabul-edilir ve gizlilikle işlenir.

## Bildirim-kanalı
Lütfen **public issue AÇMAYIN**. GitHub Security Advisory kullanın:
https://github.com/goun7/sester/security/advisories/new

## Kapsam (öncelikli ilgi alanları)

- Replay/nonce-aşımı (`seen_nonces` tablosu, restart-davranışı)
- Kota-atlatma (minor-unit sayaç, günlük-sıfırlama, refund-muhasebesi)
- JWS/atribüt-doktrini: `key_resolver` atlatması, gövde-bağı (body-binding)
  kazıması, alg-downgrade (`alg: none`), AP2/ACP/UCP zarf-sahteliği
- Kanıt-zinciri bütünlüğü (HMAC-mühür, hash-koruyan migrasyon, keccak-batch)
- Politika fail-closed bozukluğu (bozuk-dosya → DENY_ALL; S3 24h gevşetme-gate'i)

## Kapsam-dışı

- Demo-amacıyla sabitlenmiş demo-secret'lar (`examples/`, `scripts/`)
- Zayıf-anahtar kullanımı kullanan entegratör-kurulumları

## Sürüm-desteği

Yalnız en-son minor sürüm güvenlik-yaması alır (0.x disiplini);
KARAR-kaydına bağlanan breaking-değişiklikler CHANGELOG'dan izlenir.
