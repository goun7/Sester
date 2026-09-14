"""SESTER geri-uyum takma-adları — v0.4 kimlik-göçü (Pugio→Sikke→Sester).

Eski-import'lu harici-kod kırılmasın: sınıf-adı takma-adları burada yaşar.
Yeni-kod bunları KULLANMAZ (sadece `sester.middleware.SesterMeter`).
Kaldırma-kararı: v0.5'te değerlendirilir (architecture decision record §deprekasyon-politikası).
"""

from .middleware import SesterMeter as SikkeMeter  # noqa: F401
