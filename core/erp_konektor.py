# -*- coding: utf-8 -*-
"""
ERP konektor katmani - desteklenen muhasebe programlari, kurulum sihirbazinda
istenecek baglanti alanlari (sema) ve baglanti testi tek noktada.

Tasarim: motor degismez; ERP yalniz "veriyi getiren baska bir kaynak". Her ERP
icin alan semasi UI'a verilir; kullanici kendi hesabinin bilgisini girer (API'yi
"ogrenmez", sadece Luca/saglayicidan aldigi kimligi yapistirir).

Su an: alan semasi + GERCEK erisilebilirlik testi (endpoint'e ulasilabiliyor mu)
hazir. Protokol/kimlik dogrulamasinin tam hali (mizan cekme) ilgili ERP'nin API
dokumani baglaninca `cek_*` fonksiyonlari ile doldurulacak (orn. Luca WS/SOAP).

Alan tipi:
  text  -> normal metin
  sifre -> parola alani; SIR sayilir, diske sifreli yazilir, geri donulmez.
"""
import socket
import urllib.request
import urllib.error
from urllib.parse import urlparse


# Sir sayilan (sifrelenecek, ekranda bir daha gosterilmeyecek) alan tipleri.
SIR_TIPLERI = {"sifre"}


SEMALAR = {
    "luca": {
        "ad": "Luca",
        "yontem": "api",
        # Luca'nin iki dunyasi farkli kimlik ister -> paket secimi.
        "paketler": [
            {"kod": "malimusavir", "ad": "Mali Müşavir (Web Servis)",
             "alanlar": [
                 {"ad": "endpoint", "etiket": "Servis adresi (endpoint)",
                  "tip": "text", "ipucu": "https://... veya 192.168.1.x:8080/ws"},
                 {"ad": "kullanici", "etiket": "WS Kullanıcı Adı", "tip": "text"},
                 {"ad": "sifre", "etiket": "WS Şifre", "tip": "sifre"},
             ]},
            {"kod": "koza", "ad": "Koza / NET (REST)",
             "alanlar": [
                 {"ad": "endpoint", "etiket": "API adresi",
                  "tip": "text", "ipucu": "https://api.luca.com.tr/..."},
                 {"ad": "api_key", "etiket": "API Key", "tip": "text"},
                 {"ad": "api_secret", "etiket": "API Secret", "tip": "sifre"},
             ]},
        ],
    },
    "parasut": {
        "ad": "Paraşüt",
        "yontem": "oauth",
        "alanlar": [
            {"ad": "client_id", "etiket": "Client ID", "tip": "text"},
            {"ad": "client_secret", "etiket": "Client Secret", "tip": "sifre"},
        ],
        "not": "Paraşüt'e Bağlan butonu yetki ekranına yönlendirir (yakında).",
    },
    "logo":   {"ad": "Logo (Tiger / GO)", "yontem": "yakinda"},
    "mikro":  {"ad": "Mikro", "yontem": "yakinda"},
    "netsis": {"ad": "Netsis", "yontem": "yakinda"},
    "dosya":  {"ad": "Dosya Yükleme (Excel / CSV)", "yontem": "dosya"},
}


def semalar_listesi():
    """Sihirbaz icin: kod + ad + yontem (+ varsa paket/alan semasi)."""
    out = []
    for kod, v in SEMALAR.items():
        kayit = {"kod": kod, "ad": v["ad"], "yontem": v["yontem"]}
        if "paketler" in v:
            kayit["paketler"] = v["paketler"]
        if "alanlar" in v:
            kayit["alanlar"] = v["alanlar"]
        if "not" in v:
            kayit["not"] = v["not"]
        out.append(kayit)
    return out


def sir_alanlari(erp, paket=None):
    """Verilen ERP/paket icin SIR sayilan alan adlari (sifrelenecekler)."""
    v = SEMALAR.get(erp) or {}
    alanlar = []
    if "paketler" in v:
        for p in v["paketler"]:
            if paket is None or p["kod"] == paket:
                alanlar = p["alanlar"]
                if paket is not None:
                    break
    else:
        alanlar = v.get("alanlar", [])
    return {a["ad"] for a in alanlar if a.get("tip") in SIR_TIPLERI}


def _ozel_ip_mi(host):
    """Yerel/ozel ag adresi mi? (on-prem uyarisi icin kaba kontrol.)"""
    if host in ("localhost", "127.0.0.1", "::1"):
        return True
    parcalar = host.split(".")
    if len(parcalar) == 4 and all(p.isdigit() for p in parcalar):
        a, b = int(parcalar[0]), int(parcalar[1])
        if a == 10:
            return True
        if a == 192 and b == 168:
            return True
        if a == 172 and 16 <= b <= 31:
            return True
    return False


def _adres_coz(endpoint):
    """endpoint string'inden (host, port, sema) cikar."""
    e = (endpoint or "").strip()
    if not e:
        return None, None, None
    if "://" not in e:
        e = "//" + e          # urlparse host:port ayirabilsin
    u = urlparse(e, scheme="http")
    host = u.hostname
    port = u.port or (443 if u.scheme == "https" else 80)
    return host, port, u.scheme


def baglanti_test(erp, paket, bilgi):
    """Endpoint'e GERCEK erisilebilirlik testi.

    Donus: {ok, mesaj, detay}. Protokol/kimlik dogrulamasi (mizan cekme) ilgili
    ERP API dokumani baglaninca eklenecek; bu asamada ulasilabilirligi olcer ki
    on-prem (yerel sunucu) sorunu daha kurulumda ortaya ciksin.
    """
    v = SEMALAR.get(erp) or {}
    yontem = v.get("yontem")

    if yontem == "dosya":
        return {"ok": True, "mesaj": "Dosya yöntemi — bağlantı testi gerekmez."}
    if yontem == "yakinda":
        return {"ok": False, "mesaj": f"{v.get('ad', erp)} bağlantısı yakında. "
                "Şimdilik Dosya Yükleme ile başlayabilirsiniz."}

    endpoint = (bilgi or {}).get("endpoint") or ""
    if yontem == "oauth" and not endpoint:
        return {"ok": False, "mesaj": "OAuth yetkilendirme akışı API anahtarı "
                "geldiğinde devreye girecek (yakında)."}
    if not endpoint:
        return {"ok": False, "mesaj": "Servis adresi (endpoint) girilmeli."}

    host, port, sema = _adres_coz(endpoint)
    if not host:
        return {"ok": False, "mesaj": "Servis adresi çözümlenemedi; biçimi kontrol edin."}

    onprem = _ozel_ip_mi(host)
    # Once HTTP(S) ile dene; HTTP yaniti (401/404 dahil) = adrese ulasildi demek.
    url = endpoint if "://" in endpoint else f"{sema}://{endpoint}"
    try:
        istek = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(istek, timeout=6)
        return {"ok": True, "mesaj": "Adrese ulaşıldı. (Şifre/protokol doğrulaması "
                "Luca API dokümanı bağlanınca tamamlanacak.)"}
    except urllib.error.HTTPError:
        # Sunucu cevap verdi (yetki/yol hatasi) -> adres ulasilabilir.
        return {"ok": True, "mesaj": "Adrese ulaşıldı (sunucu yanıt verdi). "
                "Şifre/protokol doğrulaması API dokümanıyla tamamlanacak."}
    except Exception:
        pass

    # HTTP olmadi; ham TCP baglanti dene.
    try:
        with socket.create_connection((host, port), timeout=6):
            return {"ok": True, "mesaj": f"{host}:{port} adresine TCP bağlantı kuruldu. "
                    "Protokol doğrulaması API dokümanıyla tamamlanacak."}
    except Exception as e:
        ek = ""
        if onprem:
            ek = (" Bu adres yerel ağ (on-prem) görünüyor; buluttaki uygulama "
                  "ofis içi sunucuya doğrudan erişemez — yerel köprü gerekir.")
        return {"ok": False, "mesaj": f"Adrese ulaşılamadı ({host}:{port}).{ek}",
                "detay": str(e)}
