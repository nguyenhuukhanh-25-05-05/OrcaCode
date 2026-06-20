"""Quick test for syllable-aware Telex engine."""
from core.tui.widgets import _TelexEngine

# Test basic diacritics
assert _TelexEngine.process_dia('a', 'a') == '\u00e2'  # aa -> â
assert _TelexEngine.process_dia('e', 'e') == '\u00ea'  # ee -> ê
assert _TelexEngine.process_dia('o', 'o') == '\u00f4'  # oo -> ô
assert _TelexEngine.process_dia('d', 'd') == '\u0111'  # dd -> đ
assert _TelexEngine.process_dia('a', 'w') == '\u0103'  # aw -> ă
assert _TelexEngine.process_dia('o', 'w') == '\u01a1'  # ow -> ơ
assert _TelexEngine.process_dia('u', 'w') == '\u01b0'  # uw -> ư

# Test open syllables (tone on penultimate vowel)
assert _TelexEngine.process_tone('chao', 'f')[0] == 'ch\u00e0o'  # chao + f -> chào
assert _TelexEngine.process_tone('hoa', 'f')[0] == 'ho\u00e0'  # hoa + f -> hoà
assert _TelexEngine.process_tone('chia', 'f')[0] == 'ch\u00eca'  # chia + f -> chìa
assert _TelexEngine.process_tone('tai', 'f')[0] == 't\u00e0i'  # tai + f -> tài

# Test closed syllables (tone on last vowel)
assert _TelexEngine.process_tone('cac', 's')[0] == 'c\u00e1c'  # cac + s -> các
assert _TelexEngine.process_tone('tat', 's')[0] == 't\u00e1t'  # tat + s -> tát
assert _TelexEngine.process_tone('dep', 'j')[0] == 'd\u1eb9p'  # dep + j -> dẹp

# Test with existing diacritics
assert _TelexEngine.process_tone('\u00e2t', 's')[0] == '\u1ea5t'  # ât + s -> ất
assert _TelexEngine.process_tone('\u00e0o', 's')[0] == '\u00e1o'  # ào + s -> áo

print("All tests passed!")
