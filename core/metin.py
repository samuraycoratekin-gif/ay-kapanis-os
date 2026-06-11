# -*- coding: utf-8 -*-
"""
Metin yardimcilari - tek dogru kaynak (single source of truth).

Projede uc ayri normalize varyanti vardi (mizan_oku._nrm Turkce-duyarli,
kdv_analiz._norm regex-strip -> Turkce kaybediyordu, banka_analiz._tr_upper).
Bu modul hepsini birlestirir. Turkce karakter kaybi kaynakli eslesme
hatalarini onlemek icin TUM normalizasyon buradan gecmelidir.
"""
import re
import unicodedata

_TR = str.maketrans({
    "ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G",
    "ü": "u", "Ü": "U", "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
})


def nrm(s):
    """Eslesme anahtari: buyuk harf, Turkce/aksan sadelestir, alnum disini at.

    'İşçilik Gideri' -> 'ISCILIKGIDERI'. Bosluk, noktalama, tire silinir.
    Karsilastirma/anahtar uretimi icin; goruntuleme icin DEGIL."""
    if s is None:
        return ""
    s = str(s).strip().translate(_TR)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return "".join(ch for ch in s.upper() if ch.isalnum())


def tr_upper(s):
    """Sadece Turkce-duyarli BUYUK harf (alnum filtresi YOK, bosluk korunur).
    Ekranda gosterilecek ama buyutulecek metinler icin."""
    if s is None:
        return ""
    return str(s).translate(_TR).upper()


def sayi(v):
    """TL/sayi metnini float'a cevirir; cozulemezse None.
    '1.234,56' -> 1234.56 ; '1234.56' -> 1234.56 ; 1234 -> 1234.0
    '1.234' -> 1234 (virgul yoksa ve nokta 3'lu grup deseni ise BINLIK sayilir)
    '(1.234,56)' -> -1234.56 (muhasebe parantez negatifi) ; '12,50 TL' -> 12.5"""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    ham = str(v).strip()
    negatif = ham.startswith("(") and ham.endswith(")")
    if negatif:
        ham = ham[1:-1].strip()
    # sondaki para birimi etiketi ve bosluk turlerini at ("1.234,56 TL", "12 ₺")
    ham = re.sub(r"(?i)\s*(tl|try|try\.|₺)\s*$", "", ham.replace("\xa0", " ")).strip()
    ham = ham.replace(" ", "")
    if "," in ham:
        s = ham.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"[+-]?\d{1,3}(\.\d{3})+", ham):
        s = ham.replace(".", "")        # "1.234" / "1.234.567" -> binlik ayraci
    else:
        s = ham
    try:
        f = float(s)
    except ValueError:
        return None
    return -f if negatif else f
