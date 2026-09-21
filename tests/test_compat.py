"""Geri-uyum takma-adları (v0.4 kimlik-göçü) — canlılık-kanıtı.

compat.py, v0.5'te-kaldırma-kararı-değerlendirilecek-takma-adları-tutar
(ADR §deprekasyon-politikası). Bu-test onların hâlâ-import-edilebilir-olduğunu
ve doğru-sınıfa-işaret-ettiklerini-ölçer — bir-takma-ad kırılırsa-RED (eski-
import'lu-harici-kod-sessizce-bozulmuş-olur)."""
from __future__ import annotations


def test_sikke_alias_points_at_sester_meter():
    """`SikkeMeter` → `SesterMeter` (kimlik-göçü Pugio→Sikke→Sester)."""
    from sester.compat import SikkeMeter
    from sester.middleware import SesterMeter
    assert SikkeMeter is SesterMeter, "takma-ad-hedefinden-kopmuş"


def test_compat_module_is_alias_only():
    """Takma-ad-modülü-iş-içermemeli (sadece-re-export). v0.5-değerlendirmesi
    için-kanıt: kaldırma-kararı-modül-büyüdükçe-zorlaşır."""
    import inspect
    import sester.compat as c
    members = [n for n, _ in inspect.getmembers(c, inspect.isclass)
               if not n.startswith("__")]
    # SikkeMeter-re-export'u-member-olarak-görünür-ama-iş-değil
    assert not inspect.isfunction(getattr(c, "SikkeMeter", None)), \
        "compat'ta-fonksiyol-bulunmamalı (sadece-re-export)"
