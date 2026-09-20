"""K0 spec↔code senkronu — tri-product checklist'in YÖN-B makine-kilidi.

Ders (ERRATUM-K0.1/K0.2/K0.3 + Tamga E1/A1): **kodda-zorunlu-ama-spec'te-
yazmayan-kural** bağımsız-verifier'ı sessizce ayrıştırır. Tri-product
checklist bu boşluğu iki-yönlü-ölçerek yakalar; bu test **YÖN-B'yi kalıcı
yapar** — her normative needle K0_SHARED_ENVELOPE_SPEC.md'de aranır, bir kural
spec'ten düşerse RED düşer (code-only-kural-nüksetme-önleyicisi).

Tamga'nın Audit-19 düzeltmesiyle aynı dersün diğer-yüzü: orada negatif-kontrol
median'ın-arkasına-saklanmıştı, burada kural spec'in-arkasına-saklanabilir.
İki-yön-de-makine: spec'in-söylediği-kodda-zorunlu, kodun-zorunlu-kıldığı
spec'te-yazılı (test_spec_and_code_agree_on_taxonomy)."""

from pathlib import Path

import ast
import sys

import pytest
import re

SPEC = Path(__file__).resolve().parents[1] / "docs" / "K0_SHARED_ENVELOPE_SPEC.md"

# (id, needle, neden) — her satır bir normatif kuralın spec'te-kalıp-kalmadığını
# ölçer. Bir needle buradan ÇIKARILAMAZ: çıkarılırsa bu test RED düşer ve
# "code-only erratum" sınıfı geri-dönmüş olur.
NEEDLES = [
    ("S-1.1", "PREV", "zincir-önceki-proof bağı"),
    ("S-1.2", 'GENESIS = 64 × "0"', "ilk-olay sabit-genesis"),
    ("S-2.1", "enter the canonical preimage", "amount_minor preimage-DIŞI (K0.1)"),
    ("S-2.1b", "amount_minor", "minor-sütun adı spec'te"),
    ("S-2.2", "escalation_consumed", "K0.2 düzeltmesi-taksonomi mevcut"),
    ("S-2.2b", "facilitator_", "dinamik ön-ek ailesi spec'te"),
    ("S-2.3", "refund", "netting işareti (charge +, refund −)"),
    ("S-3.1", "replayed nonce permanently", "replay-koruması yükümlülüğü (K0.3)"),
    ("S-3.1b", "restarts", "restart-sonrası kalıcı-reddin spec'te"),
    ("S-3.2", "Fail loud", "fail-closed/paylaşık doktrin"),
    ("S-4.1", "anchor_id = SHA256", "anchor-bağlaması formülü"),
    ("S-4.1b", "merkle_root", "merkle-kökü binding"),
    ("S-4.2", "hard reject", "bilinmeyen *_version → red"),
]


@pytest.mark.parametrize("rid, needle, why", NEEDLES, ids=[n[0] for n in NEEDLES])
def test_k0_normative_needles_present(rid, needle, why):
    """YÖN-B: spec needle mevcut — düşerse RED (code-only-kural-nüksetme)."""
    text = SPEC.read_text(encoding="utf-8")
    assert needle in text, f"{rid} needle eksik ({why}): {needle!r}"


def test_spec_and_code_agree_on_taxonomy():
    """İki-yön-kilit: spec'in-saydığı her-değer kodun-zorunlu-kümesinde, ve
    kodun-zorunlu-kıldığı-taksonomi spec'te-belgeli. Aksi: spec↔kod ayrışması
    (tam olarak K0.2'nin-ilk-halindeki hata-sınıfı)."""
    from sester.ledger import EVENT_TYPES, is_known_event_type

    text = SPEC.read_text(encoding="utf-8")
    documented = ["charge_receipt", "refund", "permission_decision",
                  "escalation_parked", "escalation_approved", "escalation_denied",
                  "escalation_consumed", "protocol_intent", "settlement"]
    for v in documented:
        assert v in text, f"{v} spec'te-belgeli-değil (code-only-tehlikesi)"
        assert v in EVENT_TYPES, f"{v} kodda-zorunlu-değil (spec-only-tehlikesi)"
    # dinamik aile: spec'te-familye-yazılı, kod-da-kapalı-kind'larla-eşleşiyor
    assert "facilitator_" in text
    assert is_known_event_type("facilitator_batch") is True
    assert is_known_event_type("facilitator_bilinmeyen") is False


def _call_spans(text: str, opener: str):
    """`opener` ile-başlayan-çağrıların (start,end) aralıkları — basit
    parantez-eşleme. `.append(`/`_proof(` çağrı-sınırlarını-bulmak-için."""
    spans = []
    for m in re.finditer(re.escape(opener), text):
        i = m.end() - 1
        if i >= len(text) or text[i] != "(":
            continue
        depth = 0
        while i < len(text):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    spans.append((m.start(), i))
                    break
            i += 1
    return spans


def test_209_taxonomy_has_no_dead_entries():
    """E1(c) makine-karşılığı (Tamga-dersi): spec'in-liste-diği-her-değerin
    GERÇEK bir üreticisi olmalı — "listede-ama-corpus'ta-0" tuzağı. 2026-09-19'da
    `usage_event` tam-böyleydi: panel-etiketinden-varsayımsal-listeye-eklenmişti,
    hiçbir-üretim-yolu-yayıyordu (ölçüm aslında charge_receipt yazar). Üç-yönü-de
    kilitler: (a) her-değerin-kaynağı-var, (b) kaynak-dosya-mevcut, (c) needle
    dosyada-değil **gerçek-bir-yazım-çağrısının-içinde** — "dosyada-var-ama-o-bir
    yorum/parametre" yanlış-yeşilini-engeller (Tamga'nın-out(op="run") ve benim
    service.py:104-lines.append()-tuzağım-la-aynı-sınıf)."""
    from sester.ledger import (CALLER_CONTRACT_EVENT_TYPES, EVENT_TYPES,
                               EVENT_TYPE_SOURCES, EVENT_TYPE_FAMILIES)

    root = Path(__file__).resolve().parents[1]
    # (a) kapsama: statik-kümenin-her-değeri kaynak-yolu veya çağıran-sözleşme
    unaccounted = EVENT_TYPES - set(EVENT_TYPE_SOURCES) - CALLER_CONTRACT_EVENT_TYPES
    assert not unaccounted, f"ölü-girdi (üreticisiz-spec-değeri): {sorted(unaccounted)}"
    # (b)+(c) kaynak-mevcut VE yazım-çağrısı-içinde
    for value, (rel, needle) in EVENT_TYPE_SOURCES.items():
        path = root / rel
        assert path.exists(), f"{value}: kaynak-dosya yok: {rel}"
        text = path.read_text(encoding="utf-8")
        if needle.startswith("_proof("):
            # needle-kendisi-çağrı-formu — doğrudan-doğrula
            assert needle in text, f"{value}: çağrı-needle yok ({rel}): {needle!r}"
            continue
        assert _needle_in_call(text, needle), (
            f"{value}: needle bir-yazım-çağrısında-değil ({rel}): {needle!r} — "
            "yorum/parametre/payload-içinde-yanlış-eşleşme-riski")
    # aile-kind'ları-da-gerçek-emitter-çağrılarının-içinde-kanıtlanır
    svc = (root / "sester/facilitator_svc/service.py").read_text(encoding="utf-8")
    for kind in EVENT_TYPE_FAMILIES["facilitator_"]:
        assert _needle_in_call(svc, f'"{kind}"', opener="_proof("), (
            f"facilitator_{kind}: gerçek-bir-_proof-çağrısında-değil")
    # tenderix ailesi: escrow_*-kind'ları _to(STATE) çağrı-yerlerinden,
    # dispute_opened ise doğrudan sabit-emitter'dan
    s6 = (root / "scripts/s6_joint_run.py").read_text(encoding="utf-8")
    for kind in EVENT_TYPE_FAMILIES["tenderix_"]:
        if kind == "dispute_opened":
            assert _needle_in_call(s6, '"tenderix_dispute_opened"'), (
                "tenderix_dispute_opened: sabit-emitter yok")
        else:
            state = kind[len("escrow_"):].upper()
            assert _needle_in_call(s6, f'"{state}"', opener="_to("), (
                f"tenderix_{kind}: _to(\"{state}\") emitter'ı yok")


def _needle_in_call(text: str, needle: str, opener: str = ".append(") -> bool:
    """ needle, `opener` çağrılarından-en-az-birinin-içinde-mi? Tüm-eşleşmelere
    bakar (ilk-eşleşme bir-sözlük/yorum-içinde-olabilir — _64_TRANSITIONS gibi)."""
    spans = _call_spans(text, opener)
    start = 0
    while True:
        pos = text.find(needle, start)
        if pos == -1:
            return False
        if any(s[0] <= pos < s[1] for s in spans):
            return True
        start = pos + 1


# ---------------------------------------------------------- statik-emitter-tarama
# Tamga'nın emitter_verify.py (AT-049)-karşılığı, ters-yön: koddaki HER emitter
# çağrısının ilk-argümanı bilinen-bir-değer-olmalı. Çalışma-zamanı fail-closed
# (append) yalnızca BİR-TEST'İN-GÖRDÜĞÜ yolları-korur; bu-test KAPSAM-DIŞI
# yolları-da-yakalar — Tamga'nın run/migrate-net bulgusunun-sınıfı tam-buydu
# (hiçbir-test-o-yolu-koşmadığı-için fail-closed hiç-tetiklenmemişti).

_LEDGER_RECEIVERS = {"ledger", "led"}


def _resolve_value(node, consts) -> set[str] | None:
    """AST-değerini-sabitleştir: string / tuple / ternary / Name /
    Name.lower()-Call → değer-kümesi (çözülemezse None)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.Tuple):
        out: set[str] = set()
        for el in node.elts:
            v = _resolve_value(el, consts)
            if v is None:
                return None
            out |= v
        return out
    if isinstance(node, ast.IfExp):  # A if cond else B
        a, b = _resolve_value(node.body, consts), _resolve_value(node.orelse, consts)
        if a is None or b is None:
            return None
        return a | b
    if isinstance(node, ast.Name):
        return consts.get(node.id)  # None → çözülemedi (daha-sonra-fixpoint)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in {"lower", "upper"} and not node.args:
        base = _resolve_value(node.func.value, consts)
        if base is None:
            return None
        return {b.lower() if node.func.attr == "lower" else b.upper() for b in base}
    return None


def _bindings(tree):
    """(name, değer-node) bağları — atamalar VE fonksiyon-parametreleri-için
    çağrı-yeri-bağları (parametre → çağrıcılardan-sabit-argümanlar)."""
    out = []
    funcs = {n.name: n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    out.append((tgt.id, node.value))
                elif isinstance(tgt, ast.Tuple) and isinstance(node.value, ast.Tuple) \
                        and len(tgt.elts) == len(node.value.elts):
                    for t_el, v_el in zip(tgt.elts, node.value.elts):
                        if isinstance(t_el, ast.Name):
                            out.append((t_el.id, v_el))
        elif isinstance(node, ast.Call) and (
                (isinstance(node.func, ast.Name) and node.func.id in funcs)
                or (isinstance(node.func, ast.Attribute) and node.func.attr in funcs)):
            fname = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            params = [a.arg for a in funcs[fname].args.args
                      if a.arg not in ("self", "cls")]
            for i, arg in enumerate(node.args):
                if i < len(params):
                    out.append((params[i], arg))
    return out


def _module_const_map(tree) -> dict[str, set[str]]:
    """name → sabit-değer-kümesi. Fixpoint: Name-referansları ve çağrı-yeri
    parametreleri-aşamalı çözülür (APPROVED,DENIED="approved",... →
    status=APPROVED if approve else DENIED → escalation_{status})."""
    consts: dict[str, set[str]] = {}
    for _ in range(10):  # fixpoint — sabitlenene-kadar
        changed = False
        for name, node in _bindings(tree):
            v = _resolve_value(node, consts)
            if v and not v <= consts.get(name, set()):
                consts.setdefault(name, set()).update(v)
                changed = True
        if not changed:
            break
    return consts


def _resolve_joined(node, consts) -> set[str] | None:
    """f-string'i-sabitleştir: değer-kümesi (bir-parça-bile-çözülemezse None).
    .lower() gibi-adlandırımları-da-çözer (tenderix_escrow_{target.lower()})."""
    parts = [""]
    for v in node.values:
        if isinstance(v, ast.Constant):
            parts = [p + v.value for p in parts]
        elif isinstance(v, ast.FormattedValue):
            vals = _resolve_value(v.value, consts)
            if not vals:
                return None
            parts = [p + s for p in parts for s in vals]
        else:
            return None
    return set(parts)


def _emitter_calls(tree):
    """(çeşit, ilk-arg-node, kapsayan-fonk) — ledger/led.append() ve _proof().
    Alıcı-şekilleri: bare-name (ledger/led) VE attribute (self.ledger,
    self._ledger). list.append() gibi-alıcıları süzgeç-dışarı-tutar
    (Tamga'nın-lines.append(f"...")-/benim-service.py:104-tuzağı-sınıfı).
    Kapsayan-fonk: Starred (*a) iletişim-sarmalayıcılarını ayırt-etmek-için."""
    out = []
    stack: list[str] = []

    def _walk(n):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack.append(n.name)
        if isinstance(n, ast.Call) and n.args:
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr == "append":
                recv = f.value
                if isinstance(recv, ast.Attribute):
                    recv_ok = recv.attr in _LEDGER_RECEIVERS  # self.ledger
                elif isinstance(recv, ast.Name):
                    recv_ok = recv.id in _LEDGER_RECEIVERS  # ledger / led
                else:
                    recv_ok = False
                if recv_ok:
                    out.append(("append", n.args[0], stack[-1] if stack else ""))
            elif isinstance(f, ast.Name) and f.id == "_proof":
                out.append(("proof", n.args[0], stack[-1] if stack else ""))
        for c in ast.iter_child_nodes(n):
            _walk(c)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack.pop()

    _walk(tree)
    return out


def test_210_all_emitters_are_listed():
    """Tamga-emitter_verify-karşılığı, statik-yön: HER-emitter-biliniyor-mu?
    Kapsam-dışı-bir-yol-bilinmeyen-değer-yayarsa, append-fail-closed-koşulmadığı
    için sessizce-geçer — bu-test-o-boşluğu-kapatır (kod-taraması, test-koşmaya
    gerek-yok). Dinamik-yapılar fixpoint-çözümü-ile-kanıtlanır: aile-emitter'ları
    (facilitator_{kind} ← _proof-çağrı-yerleri; tenderix_escrow_{state.lower()} ←
    _to-çağrı-yerleri) ve escalation_{status} ← APPROVED/DENIED-ternary."""
    from sester.ledger import (CALLER_CONTRACT_EVENT_TYPES, EVENT_TYPES,
                               EVENT_TYPE_FAMILIES, is_known_event_type)

    root = Path(__file__).resolve().parents[1]
    known_append = EVENT_TYPES | CALLER_CONTRACT_EVENT_TYPES
    family_kinds = {k for kinds in EVENT_TYPE_FAMILIES.values() for k in kinds}
    problems = []
    for rel in ("sester", "examples", "scripts"):
        for py in sorted((root / rel).rglob("*.py")):
            tree = ast.parse(py.read_text(encoding="utf-8"))
            consts = _module_const_map(tree)
            for kind, arg, func in _emitter_calls(tree):
                if kind == "proof":
                    v = _resolve_value(arg, consts)
                    if v is None:
                        problems.append(f"{py}: _proof çözülemez-dinamik-argüman")
                    elif not v <= family_kinds:
                        problems.append(f"{py}: _proof bilinmeyen-kind: {sorted(v)}")
                    continue
                # append
                if isinstance(arg, ast.Starred):
                    # *a iletişim-sarmalayıcısı — emitter-değil, forwarder;
                    # yalnızca kapsayan-fonk-dağıtıcı (def append(self,*a)) ise kabul
                    if func != "append":
                        problems.append(f"{py}: Starred-append forwarder-değil ({func})")
                    continue
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if arg.value not in known_append and not is_known_event_type(arg.value):
                        problems.append(
                            f"{py}: sabit-emitter listede-değil: {arg.value!r}")
                elif isinstance(arg, ast.JoinedStr):
                    combos = _resolve_joined(arg, consts)
                    if combos is None:
                        problems.append(f"{py}: f-string-emitter çözülemedi")
                    else:
                        bad = {c for c in combos if not is_known_event_type(c)
                               and c not in known_append}
                        if bad:
                            problems.append(
                                f"{py}: f-string-emitter listede-değil: {sorted(bad)}")
                else:
                    problems.append(
                        f"{py}: çözülemez-emitter-şekli ({type(arg).__name__})")
    assert not problems, ("yayılan-ama-listede-olmayan-değerler:\n  "
                          + "\n  ".join(problems))


def test_211_s6_joint_run_is_covered():
    """Kapsam-boşluğu-kapanışı: s6_joint_run.py (tenderix-ailesinin-emit-yeri)
    HIÇBIR-testte-koşulmuyordu — test_210'ün-keşfi-tam-olarak-bu-yüzden-çoğaldı:
    fail-closed-append bir-gün-tenderix'i-kırarsa hiçbir-test-RED-vermiyordu.
    Artık-koşuluyor: tenderix-olayları gerçek-zincire-düşüyor ve s6'ın-kendi
    verify_bundle/verify_chain-kontrolleri-yeşil (rc=0)."""
    import importlib
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        mod = importlib.import_module("s6_joint_run")
        assert mod.run_joint() == 0, "S6 ortak-koşum RED-düştü"
    finally:
        sys.path.remove(str(scripts_dir))
        sys.modules.pop("s6_joint_run", None)
