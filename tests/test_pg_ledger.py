"""SESTER PgLedger testleri — DB gerektirmeyen doğrulama yüzeyi.

Kapsanan modül: sester/pg_ledger.py.

PostgreSQL'i gerektiren fonksiyonlar (append, verify_chain, ...) bu
testlerin dışındadır — onlar için canlı-postgres integration testleri
gerekir (CI'da çalışır). Burada test edilen:

1. **__init__ güvenlik-doğrulaması** — dev-secret uyarısı +
   SESTER_REQUIRE_SECURE_SECRET ile fail-closed (AT-179-BULGU-2)
2. **DSN zorunluluğu** — dsn/env yoksa RuntimeError
3. **_connect bağımlılık-doğrulaması** — psycopg yoksa net hata mesajı

Bunlar, veritabanı olmadan bile PgLedger'ın güvenlik-davranışını
sabitler: üretimde zayıf-secret ile başlaması mümkün olmamalıdır.
"""

from __future__ import annotations

import os
import unittest
import warnings
from unittest import mock

from sester.pg_ledger import PgLedger, _connect

GOOD_SECRET = "a" * 40


class TestPgLedgerInit(unittest.TestCase):
    """__init__: DSN zorunlu + secret güvenlik-doğrulaması."""

    def setUp(self):
        # DSN env kirliligini temizle
        self._old = os.environ.pop("SESTER_PG_DSN", None)

    def tearDown(self):
        if self._old is not None:
            os.environ["SESTER_PG_DSN"] = self._old

    def test_missing_dsn_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            PgLedger(secret=GOOD_SECRET)
        self.assertIn("SESTER_PG_DSN", str(ctx.exception))

    def test_dsn_arg_works(self):
        """dsn argümaniyla kurulum calisir (baglanti lazy'dir)."""
        led = PgLedger(dsn="dbname=test", secret=GOOD_SECRET)
        self.assertEqual(led.dsn, "dbname=test")

    def test_dsn_env_works(self):
        os.environ["SESTER_PG_DSN"] = "dbname=envtest"
        led = PgLedger(secret=GOOD_SECRET)
        self.assertEqual(led.dsn, "dbname=envtest")

    def test_dsn_arg_overrides_env(self):
        os.environ["SESTER_PG_DSN"] = "dbname=envtest"
        led = PgLedger(dsn="dbname=argtest", secret=GOOD_SECRET)
        self.assertEqual(led.dsn, "dbname=argtest")

    def test_db_path_accepted_for_parity(self):
        """db_path Ledger-parite için kabul edilir (DSN asıl kaynaktır)."""
        led = PgLedger(db_path="/tmp/ignored.db", dsn="dbname=t",
                       secret=GOOD_SECRET)
        self.assertEqual(led.dsn, "dbname=t")


class TestPgLedgerSecretSecurity(unittest.TestCase):
    """AT-179-BULGU-2: zayıf-secret uyarısı + fail-closed."""

    def setUp(self):
        self._old = os.environ.get("SESTER_REQUIRE_SECURE_SECRET")
        os.environ.pop("SESTER_REQUIRE_SECURE_SECRET", None)
        os.environ.pop("SESTER_PG_DSN", None)

    def tearDown(self):
        if self._old is not None:
            os.environ["SESTER_REQUIRE_SECURE_SECRET"] = self._old
        else:
            os.environ.pop("SESTER_REQUIRE_SECURE_SECRET", None)

    def test_dev_secret_warns(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            PgLedger(dsn="dbname=t", secret="dev-secret")
        self.assertTrue(any("insecure-secret" in str(x.message) for x in w))

    def test_empty_secret_warns(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            PgLedger(dsn="dbname=t", secret="")
        self.assertTrue(any("insecure-secret" in str(x.message) for x in w))

    def test_dev_secret_fail_closed_when_required(self):
        """SESTER_REQUIRE_SECURE_SECRET=1 → bilinen-değer reddedilir."""
        with mock.patch.dict(os.environ,
                             {"SESTER_REQUIRE_SECURE_SECRET": "1",
                              "SESTER_PG_DSN": "dbname=t"}):
            with warnings.catch_warnings():
                # uyaridan sonra ValueError gelmeli; uyariyi error'a
                # ceviren pytest filterwarnings'i devre disi birak
                warnings.simplefilter("ignore", UserWarning)
                with self.assertRaises(ValueError) as ctx:
                    PgLedger(dsn="dbname=t", secret="dev-secret")
        self.assertIn("insecure-secret-fail-closed", str(ctx.exception))

    def test_strong_secret_no_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            PgLedger(dsn="dbname=t", secret=GOOD_SECRET)
        self.assertFalse(any("insecure-secret" in str(x.message) for x in w))


class TestConnectDependency(unittest.TestCase):
    """_connect: psycopg yoksa net hata mesajı."""

    def test_no_driver_raises_runtimeerror(self):
        with mock.patch("builtins.__import__", side_effect=ImportError):
            with self.assertRaises(RuntimeError) as ctx:
                _connect("dbname=t")
        self.assertIn("psycopg", str(ctx.exception))

    def test_error_mentions_install_command(self):
        with mock.patch("builtins.__import__", side_effect=ImportError):
            with self.assertRaises(RuntimeError) as ctx:
                _connect("dbname=t")
        self.assertIn("pip install", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
