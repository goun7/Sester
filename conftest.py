"""Pytest paylaşılan-fixtures/env — demo-modülü izolasyonu.

demo_api (pugio.demo_api) modül-düzeyinde ESC_DB ve demo-ledger açar;
testler canlı sunucuyla AYNI dosyalara yazarsa kilit-çakışması olur
(özellikle WAL-olmayan eskalasyon DB'si). Bu yüzden demo-DB'leri
oturum-başına tmp-yola alınır — conftest, test-modüllerinden ÖNCE
çalıştığı için env, modül-import'undan önce ayarlanmış olur.
"""

from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="pugio-test-")
os.environ.setdefault("PUGIO_ESCALATION_DB", os.path.join(_TMP, "esc-test.sqlite3"))
os.environ.setdefault("PUGIO_DEMO_LEDGER_DB", os.path.join(_TMP, "demo-test.sqlite3"))
