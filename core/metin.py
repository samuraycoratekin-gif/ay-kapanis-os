# -*- coding: utf-8 -*-
"""
Metin yardimcilari - tek dogru kaynak (single source of truth).

Projede uc ayri normalize varyanti vardi (mizan_oku._nrm Turkce-duyarli,
kdv_analiz._norm regex-strip -> Turkce kaybediyordu, banka_analiz._tr_upper).
Bu modul hepsini birlestirir. Turkce karakter kaybi kaynakli eslesme
hatalarini onlemek icin TUM normalizasyon buradan gecmelidir.
"""
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
    '1.234,56' -> 1234.56 ; '1234.56' -> 1234.56 ; 1234 -> 1234.0"""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    ham = str(v).strip()
    s = ham.replace(".", "").replace(",", ".") if "," in ham else ham
    try:
        return float(s)
    except ValueError:
        return None
