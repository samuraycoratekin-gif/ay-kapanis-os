# -*- coding: utf-8 -*-
"""
Sir kasasi - ERP baglanti sirlarini (WS sifre, API secret) diskte SIFRELI
saklamak icin. Saf standart kutuphane; ek bagimlilik yok.

Sema: encrypt-then-MAC.
  - Anahtar turetme: ortam degiskeni KASA_ANAHTARI (yoksa PLATFORM_PAROLA).
  - Akis sifresi: SHA-256 sayac (CTR) modu uretec ile keystream, veriyle XOR.
  - Butunluk: HMAC-SHA256 (nonce + sifreli veri uzerinde).
Token = base64( nonce[16] + mac[32] + sifreli ).

NOT: AES stdlib'de olmadigindan SHA256-CTR stream cipher kullanildi; bu
"at-rest" sir korumasi icin yeterli ve kanitlanabilir bir kurulumdur. Asil
parolalar yine hicbir yerde duz saklanmaz.
"""
import os, hmac, hashlib, base64


def _anahtar() -> bytes:
    k = (os.environ.get("KASA_ANAHTARI")
         or os.environ.get("PLATFORM_PAROLA")
         or "ay-kapanis-yerel-gelistirme")
    # anahtari sabit boya cekmek icin bir kez ozetle
    return hashlib.sha256(k.encode("utf-8")).digest()


def _keystream(key: bytes, nonce: bytes, n: int) -> bytes:
    out = bytearray()
    ctr = 0
    while len(out) < n:
        out += hashlib.sha256(key + nonce + ctr.to_bytes(8, "big")).digest()
        ctr += 1
    return bytes(out[:n])


def sifrele(metin: str) -> str:
    key = _anahtar()
    nonce = os.urandom(16)
    data = metin.encode("utf-8")
    ks = _keystream(key, nonce, len(data))
    enc = bytes(a ^ b for a, b in zip(data, ks))
    mac = hmac.new(key, nonce + enc, hashlib.sha256).digest()
    return base64.b64encode(nonce + mac + enc).decode("ascii")


def coz(token: str) -> str:
    raw = base64.b64decode(token.encode("ascii"))
    nonce, mac, enc = raw[:16], raw[16:48], raw[48:]
    key = _anahtar()
    beklenen = hmac.new(key, nonce + enc, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, beklenen):
        raise ValueError("Sir butunluk dogrulamasi basarisiz (anahtar degismis olabilir).")
    ks = _keystream(key, nonce, len(enc))
    return bytes(a ^ b for a, b in zip(enc, ks)).decode("utf-8")
