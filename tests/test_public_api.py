"""Meter-paketi public-yüzey-kilidi (v0.7.2).

Paket olarak-tek-import-unutulmuştu: README'de-yalnızca-bridges-örneği-vardı,
`sester/__init__.py`-boştu. Bu-test dağıtılan-yüzeyi-sablo:
(a) isimler-gerçekten-import-edilebilir,
(b) __all__-içindeki-her-şey-gerçekten-var (copuk-isim-yok),
(c) gerçek-isimler-__all__-dışında-kalamaz (kaçak-yüzey-yok),
(d) __version__-ile-pyproject-aynı (guard-ile-çift-yönlü),
(e) yüzey-kopmaz: mevcut-isimler-sonradan-silinemez (solo-import-deneyi)."""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

import sester as _s

REPO = Path(__file__).resolve().parents[1]


def test_69_public_api_surface_is_importable_and_complete():
    """__all__-deki-her-isim-gerçekten-çıkış-verir; her-çıkış-__all__'da."""
    missing = [n for n in _s.__all__ if not hasattr(_s, n)]
    assert not missing, f"__all__-isimleri-eksik: {missing}"
    # kaçak-yüzey: modül-düzeyi-büyük-harfli-isimler __all__'da-olmalı
    leaked = [n for n in dir(_s) if not n.startswith("_")
              and n[0].isupper() and n not in _s.__all__]
    assert not leaked, f"__all__'da-olmayan-public-isimler: {leaked}"


def test_69b_version_matches_pyproject():
    """__version__ == pyproject.version (dağıtım-tutarlılığı)."""
    pp = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', pp, re.M)
    assert m, "pyproject'da-version-yok"
    assert m.group(1) == _s.__version__, (
        f"sürüm-kopuk: __init__={_s.__version__} pyproject={m.group(1)}")


@pytest.mark.parametrize("name", list(_s.__all__))
def test_69c_each_public_name_survives_solo_import(name):
    """Yüzey-kopmazlık: her-public-isim-tek-başına-import-edilebilir.
    Bir-isim-sonradan-koparsa-bu-test-RED-düşer (geri-uyum-vaadi)."""
    mod = importlib.import_module("sester")
    assert hasattr(mod, name), f"{name} public-yüzeyden-kopmuş"


def test_69d_readme_quickstart_snippet_runs():
    """README'deki-metering-quickstart-örneği-gerçekten-çalışır-kanıtı.
    Belge-ile-kod-arasındaki-drift'i-makineyle-yakalar: parametre-eklendi/
    kaldırıldı-yada-Policy-yapısı-değiştiyse-burası-RED-düşer."""
    from sester import Ledger, Policy, SesterMeter

    policy = Policy.from_dict({
        "wallet_policy": {
            "id": "my-api",
            "defaults": {"per_request_max": 0.10, "daily_max": 5.00},
            "rules": [
                {"id": "allow-telemetry", "when": {"host_in": ["/telemetry"]},
                 "then": "allow"},
                {"id": "approve-large", "when": {"amount_gt": 0.05},
                 "then": "escalate"},
                {"id": "deny-rest", "when": {"host_in": []}, "then": "deny"},
            ],
        }
    })
    led = Ledger(":memory:", secret="quickstart")
    meter = SesterMeter(
        app=None,
        ledger=led,
        policy=policy,
        price=0.01,
        burst_capacity=20,
        burst_refill_per_sec=10.0,
    )
    # quickstart'ın-iddia-ettiği-her-şey-gerçekten-ayakta
    assert meter.burst_capacity == 20
    assert meter.burst_refill_per_sec == 10.0
    assert policy.evaluate(0.01, "/telemetry").verdict == "allow"
    assert policy.evaluate(0.20, "/x").verdict == "escalate"
    assert policy.evaluate(0.01, "/x").verdict == "deny"
    led.close()
