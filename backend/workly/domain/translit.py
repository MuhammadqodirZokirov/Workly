"""O'zbek lotin → kirill transliteratsiyasi (TZ: kirill matnlar avtomatik chiqadi, qo'lda tekshiriladi)."""

import re

_APOSTROPHES = "'ʻʼ‘’`"

_DIGRAPHS = {
    "o'": "ў",
    "g'": "ғ",
    "sh": "ш",
    "ch": "ч",
    "yo": "ё",
    "yu": "ю",
    "ya": "я",
    "ye": "е",
}
_SINGLE = {
    "a": "а",
    "b": "б",
    "d": "д",
    "e": "е",
    "f": "ф",
    "g": "г",
    "h": "ҳ",
    "i": "и",
    "j": "ж",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "q": "қ",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "v": "в",
    "x": "х",
    "y": "й",
    "z": "з",
    "c": "с",
    "w": "в",
}


def _case(src: str, dst: str) -> str:
    return dst.upper() if src[0].isupper() else dst


def latin_to_cyrillic(text: str) -> str:
    text = re.sub(f"[{_APOSTROPHES}]", "'", text)
    out: list[str] = []
    i = 0
    while i < len(text):
        pair = text[i : i + 2]
        low = pair.lower()
        word_start = i == 0 or not text[i - 1].isalpha()
        if low in _DIGRAPHS:
            out.append(_case(pair, _DIGRAPHS[low]))
            i += 2
            continue
        ch = text[i]
        lc = ch.lower()
        if lc == "e" and word_start:
            out.append(_case(ch, "э"))
        elif ch == "'":
            out.append("ъ")  # tutuq belgisi: ta'mir → таъмир
        elif lc in _SINGLE:
            out.append(_case(ch, _SINGLE[lc]))
        else:
            out.append(ch)
        i += 1
    return "".join(out)
