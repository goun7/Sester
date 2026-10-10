"""sester.evidence._merkle dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (hashlib saf, dis cagri YOK).
Merkle-kok: ciftler sha256(a+b); tek-son-tekrar.
"""
import hashlib

import pytest

from sester.evidence import _merkle, GENESIS


def h(a, b):
    return hashlib.sha256((a + b).encode()).hexdigest()


# -- bos ---------------------------------------------------------------------------------

def test_empty_returns_genesis():
    assert _merkle([]) == GENESIS


def test_genesis_is_64_zeros():
    assert GENESIS == "0" * 64


def test_genesis_hex():
    assert len(GENESIS) == 64
    int(GENESIS, 16)


def test_empty_returns_str():
    assert isinstance(_merkle([]), str)


# -- tek-yaprak ---------------------------------------------------------------------------------

def test_single_leaf_passthrough():
    """tek-yaprak: while calismaz -> layer[0]"""
    assert _merkle(["a"]) == "a"


def test_single_hex_leaf():
    leaf = "ab" * 32
    assert _merkle([leaf]) == leaf


def test_single_returns_input_reference():
    s = "x"
    assert _merkle([s]) == s


def test_single_unicode():
    assert _merkle(["çğı"]) == "çğı"


# -- iki-yaprak ---------------------------------------------------------------------------------

def test_two_leaves():
    assert _merkle(["a", "b"]) == h("a", "b")


def test_two_leaves_order_matters():
    assert _merkle(["a", "b"]) != _merkle(["b", "a"])


def test_two_same():
    assert _merkle(["a", "a"]) == h("a", "a")


def test_two_hex():
    assert _merkle(["aa", "bb"]) == h("aa", "bb")


# -- dort-yaprak ---------------------------------------------------------------------------------

def test_four_leaves():
    l1, l2 = h("a", "b"), h("c", "d")
    assert _merkle(["a", "b", "c", "d"]) == h(l1, l2)


def test_four_leaves_balanced():
    leaves = [str(i) for i in range(4)]
    layer = [h(leaves[0], leaves[1]), h(leaves[2], leaves[3])]
    assert _merkle(leaves) == h(layer[0], layer[1])


# -- tek-son-tekrar ---------------------------------------------------------------------------------

def test_three_leaves_odd_dup():
    """3-yaprak: son tekrarlanir."""
    l = ["a", "b", "c"]
    l1, l2 = h("a", "b"), h("c", "c")
    assert _merkle(l) == h(l1, l2)


def test_five_leaves():
    l = ["a", "b", "c", "d", "e"]
    layer = [h("a", "b"), h("c", "d"), h("e", "e")]
    layer2 = [h(layer[0], layer[1]), h(layer[2], layer[2])]
    assert _merkle(l) == h(layer2[0], layer2[1])


def test_odd_dup_uses_last_value():
    """layer.append(layer[-1]) — son DEGER tekrarlanir."""
    l = ["x", "y", "z"]
    assert _merkle(l) == h(h("x", "y"), h("z", "z"))


def test_odd_does_not_mutate_input():
    l = ["a", "b", "c"]
    _merkle(l)
    assert l == ["a", "b", "c"]


def test_input_list_copied():
    """layer = list(leaves) — orijinal liste kopyalanir."""
    l = ["a", "b", "c"]
    before = list(l)
    _merkle(l)
    assert len(l) == len(before)


# -- guc-2 ---------------------------------------------------------------------------------

@pytest.mark.parametrize("n", [2, 4, 8, 16, 32])
def test_power_of_two(n):
    leaves = [f"leaf-{i}" for i in range(n)]
    layer = list(leaves)
    while len(layer) > 1:
        layer = [h(a, b) for a, b in zip(layer[::2], layer[1::2])]
    assert _merkle(leaves) == layer[0]


@pytest.mark.parametrize("n", [1, 2, 3, 5, 6, 7, 9, 10, 17])
def test_various_lengths(n):
    leaves = [f"l{i}" for i in range(n)]
    layer = list(leaves)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [h(a, b) for a, b in zip(layer[::2], layer[1::2])]
    assert _merkle(leaves) == layer[0]


# -- ozellikler ---------------------------------------------------------------------------------

def test_result_is_64_hex():
    r = _merkle(["a", "b"])
    assert len(r) == 64
    int(r, 16)


def test_result_str():
    assert isinstance(_merkle(["a", "b"]), str)


def test_deterministic():
    assert _merkle(["a", "b", "c"]) == _merkle(["a", "b", "c"])


def test_different_inputs_different_roots():
    assert _merkle(["a"]) != _merkle(["b"])


def test_concatenation_order_sensitive():
    """sha256(a+b) != sha256(b+a) — kardes-sira yer-degisince kok degisir."""
    assert _merkle(["a", "b"]) != _merkle(["b", "a"])
    assert _merkle(["a", "b", "c"]) != _merkle(["a", "c", "b"])


# -- unicode ---------------------------------------------------------------------------------

def test_unicode_leaves():
    assert _merkle(["ç", "ğ"]) == h("ç", "ğ")


def test_emoji_leaves():
    assert _merkle(["😀", "😎"]) == h("😀", "😎")


def test_turkish_sentence():
    leaves = ["merhaba dünya", "test çalıştı"]
    layer = [h(*leaves)]
    assert _merkle(leaves) == layer[0]


# -- cesitli-tipler ---------------------------------------------------------------------------------

def test_numeric_strings():
    assert _merkle(["1", "2"]) == h("1", "2")


def test_empty_string_leaves():
    assert _merkle(["", ""]) == h("", "")


def test_long_leaves():
    a, b = "x" * 1000, "y" * 1000
    assert _merkle([a, b]) == h(a, b)


def test_hex_leaves():
    leaves = [f"{i:064x}" for i in range(4)]
    layer = [h(leaves[0], leaves[1]), h(leaves[2], leaves[3])]
    assert _merkle(leaves) == h(layer[0], layer[1])


# -- GENESIS-karsilastirma ---------------------------------------------------------------------------------

def test_genesis_not_root_of_any():
    assert _merkle(["a", "b"]) != GENESIS


def test_genesis_only_for_empty():
    for n in (1, 2, 3):
        assert _merkle([str(i) for i in range(n)]) != GENESIS


# -- tekrar / performans ---------------------------------------------------------------------------------

def test_repeatable():
    for _ in range(5):
        assert _merkle(["a", "b", "c", "d"])


def test_large_list():
    leaves = [f"x{i}" for i in range(256)]
    layer = list(leaves)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [h(a, b) for a, b in zip(layer[::2], layer[1::2])]
    assert _merkle(leaves) == layer[0]


def test_very_large():
    leaves = [str(i) for i in range(1000)]
    assert isinstance(_merkle(leaves), str)


def test_independent_calls():
    r1 = _merkle(["a", "b"])
    r2 = _merkle(["a", "b"])
    assert r1 == r2


def test_single_append_changes_root():
    r1 = _merkle(["a", "b"])
    r2 = _merkle(["a", "b", "c"])
    assert r1 != r2
