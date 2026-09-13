"""SESTER facilitator_svc — S5 hosted-facilitator MVP (v0.5.0).

MONETIZATION lane-1 (docs/MONETIZATION.md): x402 verify/settle-as-a-service
+ satıcı-metering'i (dogfood — facilitator kendi ilacıyla ölçülür) +
settlement-batch entegrasyonu (sester/settlement.py).

Sınırlar (docs/S5_FACILITATOR_MILESTONE.md §0, §5):
  · non-custodial — anahtar toplanmaz; yalnız doğrulama+kanıt
  · fail-closed — doğrulama-olamazsa rejected/unknown; asla açık-kapı
  · çekirdek 0-bağımlılık kalır: fastapi/uvicorn yalnız bu pakette
    (`pip install 'sester[facilitator]'`)

Kullanım:
    uvicorn sester.facilitator_svc.app:create_app --factory --port 8453
"""

from .app import FacilitatorService, create_app

__all__ = ["FacilitatorService", "create_app"]
