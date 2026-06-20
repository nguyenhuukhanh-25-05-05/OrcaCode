"""Test syllable-aware Telex engine."""
from core.tui.widgets import _TelexEngine

def test(word, key, expected):
    result, ok = _TelexEngine.process_tone(word, key)
    status = "PASS" if ok and result == expected else "FAIL"
    print(f"  {status}: '{word}' + '{key}' -> '{result}' (expected '{expected}')")
    assert ok and result == expected, f"FAILED: {word}+{key} = {result}, expected {expected}"

def test_dia(prev, curr, expected):
    result = _TelexEngine.process_dia(prev, curr)
    status = "PASS" if result == expected else "FAIL"
    print(f"  {status}: '{prev}'+'{curr}' -> '{result}' (expected '{expected}')")
    assert result == expected

print("=== Diacritics ===")
test_dia('a', 'a', '\u00e2')
test_dia('e', 'e', '\u00ea')
test_dia('o', 'o', '\u00f4')
test_dia('d', 'd', '\u0111')
test_dia('a', 'w', '\u0103')
test_dia('o', 'w', '\u01a1')
test_dia('u', 'w', '\u01b0')

print("\n=== Open syllables (tone on penultimate vowel) ===")
test('chao', 'f', 'ch\u00e0o')
test('chao', 's', 'ch\u00e1o')
test('hoi', 'r', 'h\u1ecfi')  # hoi -> vowels o,i -> penultimate o -> h?i
test('tai', 'f', 't\u00e0i')
test('chia', 'f', 'ch\u00eca')

print("\n=== Closed syllables (tone on last vowel) ===")
test('cac', 's', 'c\u00e1c')
test('tat', 's', 't\u00e1t')
test('dep', 'j', 'd\u1eb9p')  # wait, d is not dd...

print("\n=== With diacritics ===")
# tât + s -> tất (tone on â)
test('t\u00e2t', 's', 't\u1ea5t')
# mu\u00f4n + s -> mu\u1ed1n
test('mu\u00f4n', 's', 'mu\u1ed1n')
# vi\u00eat + s -> vi\u1ebft
test('vi\u00eat', 's', 'vi\u1ebft')

print("\n=== Special open syllables (oa, oe, ue -> tone on 2nd vowel) ===")
test('hoa', 'f', 'ho\u00e0')  # hoa + f -> hoà (tone on a)
test('hoe', 's', 'ho\u00e9')

print("\n=== gi/qu initial clusters ===")
test('gia', 'f', 'gi\u00e0')
test('qua', 's', 'qu\u00e1')
test('quy', 's', 'qu\u00fd')

print("\n=== Single vowel ===")
test('ba', 'j', 'b\u1ea1')
test('me', 's', 'm\u00e9')

print("\n=== Already toned vowel (re-tone) ===")
test('ch\u00e0o', 's', 'ch\u00e1o')
test('ch\u00e1o', 'f', 'ch\u00e0o')

print("\nAll tests passed!")
