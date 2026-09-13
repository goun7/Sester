"""Pytest paylaşılan-fixtures/env — demo-modülü izolasyonu.

demo_api (sester.demo_api) modül-düzeyinde ESC_DB ve demo-ledger açar;
testler canlı sunucuyla AYNI dosyalara yazarsa kilit-çakışması olur
(özellikle WAL-olmayan eskalasyon DB'si). Bu yüzden demo-DB'leri
oturum-başına tmp-yola alınır — conftest, test-modüllerinden ÖNCE
çalıştığı için env, modül-import'undan önce ayarlanmış olur.
"""

from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="sester-test-")
os.environ.setdefault("SESTER_ESCALATION_DB", os.path.join(_TMP, "esc-test.sqlite3"))
os.environ.setdefault("SESTER_DEMO_LEDGER_DB", os.path.join(_TMP, "demo-test.sqlite3"))
