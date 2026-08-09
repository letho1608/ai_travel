import unicodedata

_VIETNAMESE_D = str.maketrans({"đ": "d", "Đ": "D"})


def ascii_fold(value: str) -> str:
    value = value.translate(_VIETNAMESE_D)
    decomposed = unicodedata.normalize("NFD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.encode("ascii", "ignore").decode("ascii").lower()
