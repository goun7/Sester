"""G42 README-pin: Sester README test-sayilari stale-kalinti-olamaz.

README tek satirda uc sayi birden verir: 2.958 tests ( collected), 2947
passed, 11 skipped. Pin `pytest tests/ --collect-only` toplamini ve tam
kosumun passed/skipped sayilarini olcer, ucunu de karsilastirir.
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")


def _collected_total(res_stdout: str) -> int:
    m = re.search(r"(\d+)\s+tests?\s+collected", res_stdout)
    if m:
        return int(m.group(1))
    total = 0
    for mm in re.finditer(r"^tests/[\w./-]+\.py:\s*(\d+)\s*$", res_stdout, re.M):
        total += int(mm.group(1))
    return total


def test_readme_test_counts_are_not_stale():
    with io.open(README, encoding="utf-8") as fh:
        readme = fh.read()
    res_c = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=1800,
    )
    assert res_c.returncode == 0, "collect basarisiz: %s" % res_c.stderr[-300:]
    collected = _collected_total(res_c.stdout)
    stale = []
    for m in re.finditer(r"(\d[\d.,]*)\s*tests\s*\(", readme):
        claimed = int(m.group(1).replace(".", "").replace(",", ""))
        if claimed != collected:
            stale.append(m.group(0))
    assert not stale, (
        "README tests-collected sayisi stale: %s (taze=%d)" % (stale, collected)
    )
