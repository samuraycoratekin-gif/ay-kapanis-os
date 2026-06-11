# -*- coding: utf-8 -*-
"""
Ay Kapanis OS - yerel web uygulamasi (sifir kurulum).

Python stdlib http.server uzerinde calisir; Flask/pandas GEREKMEZ.
(Akilli Mutabakat demosuyla ayni desen.)

Iki katman:
  KATMAN 1  Ofis Panosu      /            -> tum musteriler
  KATMAN 2  Kapanis Kokpiti  /kokpit      -> tek musteri, modul menusu

Asama 0: cok-musteri iskelet + modul registry + durum JSON.
Moduller henuz placeholder; Asama 1'den itibaren ic dolar.

Calistirma: baslat.bat  (ya da: python app.py)  ->  http://localhost:5050
"""
import os, sys, json, base64, threading, webbrowser, secrets, http.cookies, time
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from core import depo
from core import kiraci
from core import cari_analiz
from core import ayarlar
from core import kasa
from core import erp_konektor
from core import moduller as M
from moduller.mutabakat import app_logic as mutabakat   # gomulu Akilli Mutabakat modulu

M.yukle_hepsi()                      # moduller/ icindeki tum modulleri kaydet
AKTIF_DONEM = "2026-05"              # varsayilan donem (Haziran'da Mayis kapanisi yapilir)
DONEMLER = ["2026-06", "2026-05", "2026-04", "2026-03",
            "2026-02", "2026-01"]    # secilebilir donemler

TPL = os.path.join(HERE, "templates")
STATIC = os.path.join(HERE, "static")

# --------------------------------------------------------------------------- #
# Giris (auth) — cok-kiracili: her ofis/sirket kendi eposta+parolasiyla girer.
# Parolalar kiraci.py'de pbkdf2 ile hash'li tutulur (duz parola saklanmaz).
# Oturum token'i -> kiraci_id eslemesi process bellektedir (_OTURUMLAR).
# GIRIS_PAROLASI env'i artik yalniz ilk varsayilan kiracinin seed parolasi.
# --------------------------------------------------------------------------- #
GIRIS_PAROLASI = os.environ.get("GIRIS_PAROLASI", "")
BULUT = bool(os.environ.get("PORT"))

# --- Oturum suresi (otomatik dusme) ----------------------------------------- #
# Oturum jetonu -> {kid?, baslangic, son}. Iki sinir: BOSTA (islem yoksa) ve
# AZAMI (mutlak ust sinir). Gecince jeton dusurulur, yeniden giris istenir.
OTURUM_BOSTA_SN = int(os.environ.get("OTURUM_BOSTA_SN", 2 * 3600))    # 2 saat islemsizlik
OTURUM_AZAMI_SN = int(os.environ.get("OTURUM_AZAMI_SN", 12 * 3600))   # 12 saat mutlak
# "Beni Hatirla" isaretliyse genisletilmis sinirlar (cerez Max-Age = azami).
HATIRLA_BOSTA_SN = int(os.environ.get("HATIRLA_BOSTA_SN", 7 * 24 * 3600))    # 7 gun
HATIRLA_AZAMI_SN = int(os.environ.get("HATIRLA_AZAMI_SN", 30 * 24 * 3600))   # 30 gun
_OTURUMLAR = {}                       # {token: {"kid","baslangic","son","bosta","azami"}}

# --- Giris deneme sinirlama (brute-force korumasi) -------------------------- #
# IP basina art arda hatali girisler; esik asilinca o IP kisa sure kilitlenir.
GIRIS_AZAMI_DENEME = int(os.environ.get("GIRIS_AZAMI_DENEME", 8))
GIRIS_KILIT_SN = int(os.environ.get("GIRIS_KILIT_SN", 300))           # 5 dk kilit
_GIRIS_DENEME = {}                    # {ip: {"sayi":int, "kilit":ts}}

# Platform sahibi (saglayici): tum kiracilarin ustunde, kayit defterini yonetir.
# Kimligi env'den gelir; hicbir kiraci bu kapidan giremez. Oturum'u AYRI tutulur
# ki kiraci veri kapsamina (depo) hic dokunmasin.
PLATFORM_EPOSTA = os.environ.get("PLATFORM_EPOSTA", "patron@aykapanis.local")
PLATFORM_PAROLA = os.environ.get("PLATFORM_PAROLA", "patron1234")
_PLATFORM_OTURUMLAR = {}              # {token: {"baslangic":ts,"son":ts}}


def _token_al(handler):
    ck = http.cookies.SimpleCookie(handler.headers.get("Cookie", ""))
    t = ck.get("oturum")
    return t.value if t else None


def _oturum_suresi_doldu(o, now):
    bosta = o.get("bosta", OTURUM_BOSTA_SN)
    azami = o.get("azami", OTURUM_AZAMI_SN)
    return (now - o["son"] > bosta) or (now - o["baslangic"] > azami)


def _oturum_kiraci(handler):
    """Cerezdeki token'dan kiraci_id'yi cozer; suresi dolduysa dusurur -> None."""
    t = _token_al(handler)
    o = _OTURUMLAR.get(t) if t else None
    if not o:
        return None
    now = time.time()
    if _oturum_suresi_doldu(o, now):
        _OTURUMLAR.pop(t, None)
        return None
    o["son"] = now                    # kayan pencere: her erisimde tazele
    return o["kid"]


def _platform_mi(handler):
    """Istek platform sahibi oturumuna mi ait? (sure kontrollu)"""
    t = _token_al(handler)
    o = _PLATFORM_OTURUMLAR.get(t) if t else None
    if not o:
        return False
    now = time.time()
    if _oturum_suresi_doldu(o, now):
        _PLATFORM_OTURUMLAR.pop(t, None)
        return False
    o["son"] = now
    return True


def _platform_dogrula(eposta, parola):
    """Env'deki platform kimligiyle sabit-zamanli karsilastirma."""
    e = secrets.compare_digest((eposta or "").strip().lower(), PLATFORM_EPOSTA.lower())
    p = secrets.compare_digest((parola or ""), PLATFORM_PAROLA)
    return e and p


def _oturum_gecerli(handler):
    return _oturum_kiraci(handler) is not None


def _istemci_ip(handler):
    """Gercek istemci IP'si — Railway/proxy arkasinda X-Forwarded-For ilk deger."""
    xff = handler.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return handler.client_address[0]


def _giris_kilit_kalan(ip, now):
    """IP kilitliyse kalan saniye; degilse 0."""
    d = _GIRIS_DENEME.get(ip)
    if d and d.get("kilit", 0) > now:
        return int(d["kilit"] - now)
    return 0


def _giris_basarisiz(ip, now):
    d = _GIRIS_DENEME.setdefault(ip, {"sayi": 0, "kilit": 0})
    d["sayi"] += 1
    if d["sayi"] >= GIRIS_AZAMI_DENEME:
        d["kilit"] = now + GIRIS_KILIT_SN
        d["sayi"] = 0                  # kilit doldugunda taze say


def _giris_basarili(ip):
    _GIRIS_DENEME.pop(ip, None)


def _giris_sayfa(hata=False, kilit=0):
    ofis_adi = ayarlar.oku().get("ofis_adi", "Ay Kapanış OS")
    if kilit:
        dk = max(1, (int(kilit) + 59) // 60)
        uyari = ('<div class="alert-message"><i class="fa-solid fa-lock"></i> '
                 f'Çok fazla hatalı deneme. Lütfen {dk} dakika sonra tekrar deneyin.</div>')
    elif hata:
        uyari = ('<div class="alert-message"><i class="fa-solid fa-circle-exclamation"></i> '
                 'Şifre hatalı, tekrar deneyin.</div>')
    else:
        uyari = ""
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Giriş — {ofis_adi}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    :root {{
      --bg-dark: #0e1d3d;
      --bg-card: rgba(23, 37, 68, 0.55);
      --border-card: rgba(255, 255, 255, 0.08);
      --accent-cyan: #14b8a6;
      --accent-rose: #f43f5e;
      --accent-emerald: #10b981;
      --accent-gold: #f59e0b;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
    }}
    
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    
    body {{
      font-family: 'Inter', sans-serif;
      background-color: var(--bg-dark);
      color: var(--text-main);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      overflow-x: hidden;
      position: relative;
    }}
    
    .glow-orb {{
      position: absolute;
      border-radius: 50%;
      filter: blur(100px);
      z-index: 0;
      opacity: 0.20;
      animation: float 20s infinite alternate ease-in-out;
    }}
    .orb-1 {{
      width: 400px;
      height: 400px;
      background: var(--accent-cyan);
      top: -100px;
      left: -100px;
    }}
    .orb-2 {{
      width: 500px;
      height: 500px;
      background: #6366f1;
      bottom: -150px;
      right: -150px;
      animation-delay: -5s;
    }}
    
    @keyframes float {{
      0% {{ transform: translate(0, 0) scale(1); }}
      100% {{ transform: translate(80px, 50px) scale(1.1); }}
    }}
    
    .login-container {{
      width: 100%;
      max-width: 440px;
      padding: 24px;
      z-index: 10;
      position: relative;
    }}
    
    .brand-section {{
      text-align: center;
      margin-bottom: 24px;
    }}
    .brand-logo {{
      font-family: 'Outfit', sans-serif;
      font-size: 28px;
      font-weight: 800;
      letter-spacing: -0.5px;
      background: linear-gradient(135deg, #fff 30%, var(--accent-cyan));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 6px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
    }}
    .brand-logo i {{
      -webkit-text-fill-color: var(--accent-cyan);
    }}
    .brand-subtitle {{
      font-size: 14px;
      color: var(--text-muted);
    }}
    
    .login-card {{
      background: var(--bg-card);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid var(--border-card);
      border-radius: 20px;
      padding: 32px;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
      margin-bottom: 24px;
    }}
    
    .input-group {{
      margin-bottom: 20px;
      position: relative;
    }}
    
    .input-label {{
      display: block;
      font-size: 13px;
      font-weight: 500;
      color: var(--text-muted);
      margin-bottom: 8px;
      font-family: 'Outfit', sans-serif;
    }}
    
    .input-wrapper {{
      position: relative;
      display: flex;
      align-items: center;
      width: 100%;
    }}
    
    .input-field {{
      width: 100%;
      padding: 12px 40px 12px 14px;
      background: rgba(7, 10, 19, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 10px;
      color: var(--text-main);
      font-family: inherit;
      font-size: 15px;
      transition: all 0.3s ease;
    }}
    .input-field:focus {{
      outline: none;
      border-color: var(--accent-cyan);
      box-shadow: 0 0 12px rgba(20, 184, 166, 0.25);
    }}
    
    select.input-field {{
      appearance: none;
      -webkit-appearance: none;
      background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: right 14px center;
      background-size: 16px;
      cursor: pointer;
    }}
    select.input-field option {{
      background: #0f172a;
      color: var(--text-main);
    }}
    
    .eye-toggle {{
      position: absolute;
      right: 14px;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 14px;
      transition: color 0.2s ease;
    }}
    .eye-toggle:hover {{
      color: var(--text-main);
    }}
    
    .remember-me {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: var(--text-muted);
      cursor: pointer;
      margin-bottom: 24px;
      user-select: none;
    }}
    .remember-me input {{
      accent-color: var(--accent-cyan);
      cursor: pointer;
    }}
    
    .submit-btn {{
      width: 100%;
      padding: 12px;
      background: linear-gradient(135deg, var(--accent-cyan), #0d9488);
      border: none;
      border-radius: 10px;
      color: #fff;
      font-family: 'Outfit', sans-serif;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.3s ease;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 8px;
    }}
    .submit-btn:hover {{
      transform: translateY(-1px);
      box-shadow: 0 8px 20px rgba(20, 184, 166, 0.3);
    }}
    .submit-btn:active {{
      transform: translateY(1px);
    }}
    
    .spinner {{
      display: none;
      width: 16px;
      height: 16px;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-radius: 50%;
      border-top-color: #fff;
      animation: spin 0.8s linear infinite;
    }}
    @keyframes spin {{
      to {{ transform: rotate(360deg); }}
    }}
    
    .alert-message {{
      background: rgba(244, 63, 94, 0.15);
      border: 1px solid rgba(244, 63, 94, 0.3);
      color: #fda4af;
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 13px;
      margin-top: 16px;
      text-align: center;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }}
    
    .features-section {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-top: 8px;
    }}
    .feature-card {{
      background: rgba(15, 23, 42, 0.3);
      border: 1px solid rgba(255, 255, 255, 0.04);
      border-radius: 12px;
      padding: 12px 8px;
      text-align: center;
      transition: all 0.3s ease;
    }}
    .feature-card:hover {{
      background: rgba(15, 23, 42, 0.45);
      border-color: rgba(20, 184, 166, 0.15);
    }}
    .feature-card i {{
      font-size: 16px;
      margin-bottom: 6px;
      display: block;
    }}
    .feature-card i.cyan {{ color: var(--accent-cyan); }}
    .feature-card i.emerald {{ color: var(--accent-emerald); }}
    .feature-card i.gold {{ color: var(--accent-gold); }}
    
    .feature-card h4 {{
      font-family: 'Outfit', sans-serif;
      font-size: 11px;
      font-weight: 700;
      margin-bottom: 2px;
    }}
    .feature-card p {{
      font-size: 9px;
      color: var(--text-muted);
      line-height: 1.2;
    }}
    
    footer {{
      text-align: center;
      margin-top: 24px;
      font-size: 11px;
      color: var(--text-muted);
      opacity: 0.7;
    }}
  </style>
</head>
<body>
  <div class="glow-orb orb-1"></div>
  <div class="glow-orb orb-2"></div>
  
  <div class="login-container">
    <div class="brand-section">
      <div class="brand-logo"><i class="fa-solid fa-compass-drafting"></i> {ofis_adi}</div>
      <div class="brand-subtitle">Dönem Kapanış Otomasyon Portalı</div>
    </div>
    
    <div class="login-card">
      <form id="login-form" method="POST" action="/giris">
        <div class="input-group">
          <label class="input-label" for="eposta">E-posta</label>
          <div class="input-wrapper">
            <input class="input-field" type="email" id="eposta" name="eposta" placeholder="ofis@firma.com" autocomplete="username" required>
          </div>
        </div>

        <div class="input-group">
          <label class="input-label" for="parola">Şifre</label>
          <div class="input-wrapper">
            <input class="input-field" type="password" id="parola" name="parola" placeholder="Ofis/şirket şifreniz" autocomplete="current-password" required>
            <i class="fa-solid fa-eye eye-toggle" id="toggle-password" title="Şifreyi Göster/Gizle"></i>
          </div>
        </div>
        
        <label class="remember-me">
          <input type="checkbox" name="beni_hatirla" checked>
          Beni Hatırla (30 gün)
        </label>
        
        <button class="submit-btn" type="submit" id="submit-btn">
          <span class="spinner" id="btn-spinner"></span>
          <span id="btn-text">Sisteme Giriş Yap</span>
        </button>
      </form>
      
      {uyari}
    </div>
    
    <div class="features-section">
      <div class="feature-card">
        <i class="fa-solid fa-calendar-check cyan"></i>
        <h4>Ay Kapanış OS</h4>
        <p>13 kontrol modülüyle aylık kapanış: mizan, cari, KDV-tevkifat, banka</p>
      </div>
      <div class="feature-card">
        <i class="fa-solid fa-scale-balanced emerald"></i>
        <h4>Akıllı Mutabakat</h4>
        <p>GİB öncelikli 3 aşamalı cari mutabakat ve otomatik fark analizi</p>
      </div>
      <div class="feature-card">
        <i class="fa-solid fa-shield-halved gold"></i>
        <h4>Yasal Kanıt & Güvenlik</h4>
        <p>Hash zincirli değiştirilemez kayıt, rol bazlı onay ve oturum kilidi</p>
      </div>
    </div>
    
    <footer>
      <p>{ofis_adi} &copy; 2026 · veri güvenliği protokolleriyle korunmaktadır</p>
    </footer>
  </div>
  
  <script>
    const passInput = document.getElementById('parola');
    const togglePass = document.getElementById('toggle-password');
    const form = document.getElementById('login-form');
    const btn = document.getElementById('submit-btn');
    const spinner = document.getElementById('btn-spinner');
    const btnText = document.getElementById('btn-text');

    togglePass.addEventListener('click', () => {{
      const type = passInput.getAttribute('type') === 'password' ? 'text' : 'password';
      passInput.setAttribute('type', type);
      togglePass.classList.toggle('fa-eye');
      togglePass.classList.toggle('fa-eye-slash');
    }});
    
    form.addEventListener('submit', () => {{
      btn.disabled = true;
      btn.style.opacity = '0.8';
      btn.style.cursor = 'not-allowed';
      spinner.style.display = 'inline-block';
      btnText.innerText = 'Bağlanıyor...';
    }});
  </script>
</body>
</html>"""


# --------------------------------------------------------------------------- #
# API fonksiyonlari (hepsi JSON/dict dondurur)
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Platform yonetimi - kiraci (ofis/sirket) kayit defteri arayuzu.
# Yalnizca platform sahibi oturumu erisir (do_GET/do_POST'ta _platform_mi gate).
# --------------------------------------------------------------------------- #
def api_kiracilar():
    """Tum kiracilarin ozeti (parola_hash gizli)."""
    out = []
    for k in kiraci.kiracilari_getir():
        tip = k.get("tip", "ofis")
        out.append({
            "id": k["id"], "unvan": k.get("unvan", ""),
            "tip": tip, "tip_ad": kiraci.TIPLER.get(tip, tip),
            "eposta": k.get("eposta", ""), "paket": k.get("paket", ""),
            "moduller": kiraci.kiraci_moduller(k["id"]),
            "aktif": bool(k.get("aktif", True)), "olusturma": k.get("olusturma", ""),
        })
    return {"kiracilar": out, "tipler": kiraci.TIPLER, "moduller": kiraci.MODULLER}


def api_kiraci_ekle(body):
    """Yeni kiraci (ofis/sirket) olusturur + giris kimligi tanimlar."""
    unvan = (body.get("unvan") or "").strip()
    eposta = (body.get("eposta") or "").strip()
    parola = (body.get("parola") or "").strip()
    tip = body.get("tip") or "ofis"
    paket = (body.get("paket") or "pilot").strip() or "pilot"
    moduller = body.get("moduller")   # ["ay_kapanis","mutabakat"] - bos ise varsayilan
    if not unvan:
        return {"hata": "Ünvan zorunlu."}
    if len(parola) < 4:
        return {"hata": "Parola en az 4 karakter olmalı."}
    try:
        k = kiraci.kiraci_ekle(unvan, eposta, parola, tip=tip, paket=paket,
                               moduller=moduller)
    except ValueError as e:
        return {"hata": str(e)}
    return {"ok": True, "kiraci": {"id": k["id"], "unvan": k["unvan"],
                                   "eposta": k["eposta"], "tip": k["tip"],
                                   "moduller": kiraci.kiraci_moduller(k["id"])}}


def api_kiraci_moduller(body):
    """Kiracinin sahip oldugu modulleri gunceller (capraz satis: mutabakat'i ac/kapa)."""
    k = kiraci.kiraci_moduller_ayarla(body.get("id"), body.get("moduller") or [])
    if not k:
        return {"hata": "Kiracı bulunamadı."}
    return {"ok": True, "moduller": kiraci.kiraci_moduller(k["id"])}


def api_kiraci_durum(body):
    """Kiraciyi aktif/pasif yapar (pasif kiraci giris yapamaz)."""
    k = kiraci.kiraci_durum_ayarla(body.get("id"), bool(body.get("aktif")))
    if not k:
        return {"hata": "Kiracı bulunamadı."}
    return {"ok": True, "aktif": k["aktif"]}


def api_kiraci_parola(body):
    """Kiraci giris parolasini sifirlar."""
    yeni = (body.get("parola") or "").strip()
    if len(yeni) < 4:
        return {"hata": "Parola en az 4 karakter olmalı."}
    k = kiraci.kiraci_parola_guncelle(body.get("id"), yeni)
    if not k:
        return {"hata": "Kiracı bulunamadı."}
    return {"ok": True}


def api_kiraci_sil(body):
    """Kiraciyi KALICI siler (platform sahibi). Cifte koruma: kiraci PASIF
    olmali (kiraci.kiraci_sil iceride dogrular) + unvan AYNEN yazilmali.
    Silinen kiracinin acik oturumlari da dusurulur."""
    k = kiraci.kiraci_getir(body.get("id"))
    if not k:
        return {"hata": "Kiracı bulunamadı."}
    beklenen = (k.get("unvan") or "").strip()
    yazilan = (body.get("onay_unvan") or "").strip()
    if not beklenen or yazilan != beklenen:
        return {"hata": "Onay için kiracı ünvanını aynen yazmalısınız."}
    r = kiraci.kiraci_sil(k["id"])
    if r.get("ok"):
        for t in [t for t, o in list(_OTURUMLAR.items()) if o.get("kid") == k["id"]]:
            _OTURUMLAR.pop(t, None)
    return r


# --------------------------------------------------------------------------- #
# Kurulum (onboarding) - yeni kiracinin ilk girisinde calisir.
# Desteklenen ERP'ler, baglanti alan semasi ve baglanti testi core/erp_konektor
# icinde merkezilestirildi. ERP = motora veri besleyen baska bir kaynak.
# --------------------------------------------------------------------------- #
# Baglama yontemi insan-okunur aciklamasi (sihirbazda gosterilir).
BAGLANTI_ACIKLAMA = {
    "api": "Luca/saglayicidan aldiginiz baglanti bilgilerini girersiniz; "
           "sifre/secret SIFRELI saklanir, asla geri gosterilmez, koda/git'e gitmez.",
    "oauth": "Saglayici yetki ekranindan baglanirsiniz; sifreniz bizde tutulmaz.",
    "yakinda": "Bu programin otomatik baglantisi yakinda. Su an Dosya Yukleme ile "
               "hemen baslayabilirsiniz.",
    "dosya": "Mizan/Excel/CSV dosyalarini yukleyerek calisirsiniz — en hizli "
             "ve en guvenli baslangic, ek baglanti gerekmez.",
}


def _kurulum_gerekli():
    """Aktif kiracida hic personel yoksa kurulum sihirbazi gerekir.
    (varsayilan/eski kiracilar zaten kullaniciya sahip oldugundan muaf.)"""
    return not depo.kullanicilari_getir()


def api_kurulum_bilgi():
    """Sihirbaz icin kiraci bilgisi + ERP secenekleri (alan semasiyla)."""
    k = kiraci.kiraci_getir(depo.aktif_kiraci()) or {}
    tip = k.get("tip", "ofis")
    return {
        "tip": tip,
        "tip_ad": kiraci.TIPLER.get(tip, "Ofis"),
        "unvan": k.get("unvan", ""),
        "erp_secenekleri": erp_konektor.semalar_listesi(),
        "baglanti_aciklama": BAGLANTI_ACIKLAMA,
    }


def _erp_bilgi_ayir(erp, paket, bilgi):
    """Girilen baglanti alanlarini SIR (sifrelenecek) ve OZET (gosterilebilir)
    olarak ayirir. Sir alanlar kasa ile sifrelenir, ozet duz saklanir."""
    bilgi = bilgi or {}
    sir_adlar = erp_konektor.sir_alanlari(erp, paket)
    ozet, sir = {}, {}
    for ad, deger in bilgi.items():
        if ad in sir_adlar:
            sir[ad] = deger
        else:
            ozet[ad] = deger
    sifreli = kasa.sifrele(json.dumps(sir, ensure_ascii=False)) if sir else ""
    return ozet, sifreli


def api_erp_test(body):
    """Kurulum sirasinda 'Baglantiyi Test Et' — endpoint'e gercek erisim denemesi."""
    erp = (body.get("erp_tipi") or "").strip()
    paket = (body.get("erp_paket") or "").strip() or None
    bilgi = body.get("bilgi") or {}
    return erp_konektor.baglanti_test(erp, paket, bilgi)


def api_kurulum(body):
    """Yeni kiracinin tek-seferlik kurulumu: ofis adi + yonetici + ERP + baglanti.
    Yalniz henuz hic kullanici yokken calisir (tekrar calismaz)."""
    if depo.kullanicilari_getir():
        return {"hata": "Kurulum zaten tamamlanmış."}
    ofis_adi = (body.get("ofis_adi") or "").strip()
    yonetici_ad = (body.get("yonetici_ad") or "").strip()
    erp = body.get("erp_tipi") or "dosya"
    paket = (body.get("erp_paket") or "").strip()
    bilgi = body.get("bilgi") or {}
    if not yonetici_ad:
        return {"hata": "Yönetici adı zorunlu."}
    sema = erp_konektor.SEMALAR.get(erp)
    if not sema:
        erp, sema = "dosya", erp_konektor.SEMALAR["dosya"]
    # Ilk yoneticiyi ac ve aktif kullanici yap.
    k = depo.kullanici_ekle(yonetici_ad, "yonetici")
    depo.aktif_kullanici_ayarla(k["id"])
    # Baglanti bilgisini SIR/OZET olarak ayir, siri sifrele.
    ozet, sifreli = _erp_bilgi_ayir(erp, paket or None, bilgi)
    # Kiraci-izole ayarlara kurulum bilgisini yaz.
    yeni = dict(ayarlar.oku())
    yeni["ofis_adi"] = ofis_adi or yeni.get("ofis_adi", "Ay Kapanış OS")
    yeni["erp_tipi"] = erp
    yeni["erp_paket"] = paket
    yeni["erp_baglanti"] = sema["yontem"]
    yeni["erp_baglanti_ozet"] = ozet
    yeni["erp_kimlik_sifreli"] = sifreli
    yeni["kurulum_tamam"] = True
    ayarlar.yaz(yeni)
    return {"ok": True}


def api_ofis(donem=None):
    """Ofis panosu: AKTIF musteriler + secili donem ozetleri; arsivdekiler ayri."""
    donem = donem or AKTIF_DONEM
    kodlar = M.kodlar()
    out, arsiv = [], []
    for m in depo.musterileri_getir():
        if not m.get("aktif", True):
            arsiv.append({"id": m["id"], "unvan": m.get("unvan", ""),
                          "erp_tipi": m.get("erp_tipi", ""),
                          "olusturma": m.get("olusturma", "")})
            continue
        d = depo.donem_getir(m["id"], donem, kodlar)
        bulgu = sum(x.get("bulgu_sayisi", 0) for x in d["moduller"].values())
        out.append({**m, "genel_ilerleme": d["genel_ilerleme"],
                    "bulgu": bulgu, "son_tarih": d.get("son_tarih")})
    # Bu kiracinin sahip oldugu URUN modulleri (ay_kapanis/mutabakat) - sekme gosterimi icin.
    urun_kodlar = kiraci.kiraci_moduller(depo.aktif_kiraci())
    return {"donem": donem, "donemler": DONEMLER, "musteriler": out,
            "arsiv": arsiv,
            "urun_moduller": urun_kodlar,
            "urun_modul_adlar": {k: kiraci.MODULLER[k] for k in urun_kodlar}}


# Platforma gercekten bagli (calisir) urun modulleri. Digerleri "yakinda" placeholder.
HAZIR_URUNLER = {"ay_kapanis", "mutabakat"}
URUN_URL = {"ay_kapanis": "/ay-kapanis", "mutabakat": "/mutabakat/ofis"}


def api_urunler():
    """Aktif kiracinin sahip oldugu urun modulleri (giris sonrasi secim ekrani)."""
    kodlar = kiraci.kiraci_moduller(depo.aktif_kiraci())
    a = ayarlar.oku()
    urunler = [{"kod": k, "ad": kiraci.MODULLER.get(k, k),
                "hazir": k in HAZIR_URUNLER, "url": URUN_URL.get(k, "")}
               for k in kodlar]
    return {"ofis_adi": a.get("ofis_adi", "Ay Kapanış OS"), "urunler": urunler}


def api_kokpit(musteri_id, donem):
    m = depo.musteri_getir(musteri_id)
    if not m:
        return {"hata": "Musteri bulunamadi."}
    durum = depo.donem_getir(musteri_id, donem, M.kodlar())
    moduller = [{"kod": x.kod, "ad": x.ad, "ikon": x.ikon,
                 "grup": M.grup_kod(x.kod), "grup_ad": M.grup_ad(x.kod)} for x in M.liste()]
    return {"musteri": m, "donem": donem, "donemler": DONEMLER, "durum": durum, "moduller": moduller,
            "kilitli": bool(durum.get("kilitli")),
            "kilit_kullanici": durum.get("kilit_kullanici", ""),
            "aktif_kullanici": depo.aktif_kullanici()}


def api_kullanicilar():
    return {"kullanicilar": depo.kullanicilari_getir(),
            "aktif": depo.aktif_kullanici(), "roller": depo.ROLLER}


def api_kullanici_listesi():
    return {"kullanicilar": [{"id": k["id"], "ad": k["ad"]} for k in depo.kullanicilari_getir()]}


def api_aktif_kullanici(body):
    k = depo.aktif_kullanici_ayarla(body.get("id"))
    if not k:
        return {"hata": "Kullanıcı bulunamadı."}
    return {"ok": True, "aktif": k}


def api_kullanici_ekle(body):
    """Kiraci icine yeni personel ekler. Yalniz Ofis Yoneticisi."""
    if not depo.yonetici_mi():
        return {"hata": "Kullanıcı ekleme yetkisi yalnızca Ofis Yöneticisinde."}
    ad = (body.get("ad") or "").strip()
    rol = body.get("rol") or "eleman"
    if not ad:
        return {"hata": "Ad zorunlu."}
    if rol not in depo.ROLLER:
        return {"hata": "Geçersiz rol."}
    k = depo.kullanici_ekle(ad, rol)
    return {"ok": True, "kullanici": k}


def api_kullanici_rol(body):
    """Personelin rolunu degistirir. Yalniz Ofis Yoneticisi."""
    if not depo.yonetici_mi():
        return {"hata": "Rol değiştirme yetkisi yalnızca Ofis Yöneticisinde."}
    k = depo.kullanici_rol_guncelle(body.get("id"), body.get("rol"))
    if not k:
        return {"hata": "Kullanıcı bulunamadı veya geçersiz rol."}
    return {"ok": True, "kullanici": k}


def api_kullanici_sil(body):
    """Personeli siler. Yalniz Ofis Yoneticisi; son yonetici silinemez."""
    if not depo.yonetici_mi():
        return {"hata": "Kullanıcı silme yetkisi yalnızca Ofis Yöneticisinde."}
    return depo.kullanici_sil(body.get("id"))


def api_donem_kilit(body):
    """Donemi kilitler/acar. Sadece mudur yetkili."""
    if not depo.yetkili_mi("kilit"):
        return {"hata": "Dönem kilitleme yetkisi yalnızca Muhasebe Müdüründe."}
    musteri_id = body.get("m"); donem = body.get("d")
    kilitli = bool(body.get("kilitli"))
    k = depo.aktif_kullanici()
    depo.donem_kilit_ayarla(musteri_id, donem, kilitli, k["ad"] if k else "")
    return {"ok": True, "kilitli": kilitli}


def api_modul(musteri_id, donem, kod):
    mod = M.getir(kod)
    if not mod:
        return {"hata": "Modul bulunamadi."}
    sonuc = mod.calistir(musteri_id, donem)
    return {"html": mod.panel_html(sonuc)}


def _ayar_sansur(a):
    """API yanitlarinda sifreli ERP kimligi geri donmez (geri donusu de yok;
    yalniz sunucu icinde cozulur). Diskteki kayit etkilenmez."""
    a = dict(a)
    a.pop("erp_kimlik_sifreli", None)
    return a


def api_ayarlar_oku():
    return {"ok": True, "ayarlar": _ayar_sansur(ayarlar.oku()),
            "varsayilan": _ayar_sansur(ayarlar.VARSAYILAN)}


def _sayi(v, vars):
    try:
        return float(v)
    except (TypeError, ValueError):
        return vars


def api_ayarlar_yaz(body):
    """Ofis genelindeki esik/listeleri gunceller. Yalniz bilinen alanlar
    yazilir; tipler dogrulanir. Son onay kullanicida — bu yalniz tarama
    esiklerini ayarlar, otomatik kayit YOK."""
    if not depo.yetkili_mi("kilit"):
        return {"hata": "Ayarları değiştirme yetkisi yalnızca Muhasebe Müdüründe."}
    mevcut = ayarlar.oku()
    yeni = dict(mevcut)

    zh = body.get("zorunlu_hesaplar")
    if isinstance(zh, dict):
        temiz = {}
        for kod, et in zh.items():
            k = str(kod).strip()[:3]
            if k.isdigit() and len(k) == 3:
                temiz[k] = str(et).strip() or k
        if temiz:
            yeni["zorunlu_hesaplar"] = temiz

    if "mizan_sapma_yuzde" in body:
        yeni["mizan_sapma_yuzde"] = max(0.0, _sayi(body["mizan_sapma_yuzde"], mevcut["mizan_sapma_yuzde"]))
    if "mizan_sapma_min_tutar" in body:
        yeni["mizan_sapma_min_tutar"] = max(0.0, _sayi(body["mizan_sapma_min_tutar"], mevcut["mizan_sapma_min_tutar"]))
    if "zorunlu_hesap_tolerans" in body:
        yeni["zorunlu_hesap_tolerans"] = max(0.0, _sayi(body["zorunlu_hesap_tolerans"], mevcut["zorunlu_hesap_tolerans"]))
    if "tevkifat_varsayilan_pay" in body:
        yeni["tevkifat_varsayilan_pay"] = max(0, int(_sayi(body["tevkifat_varsayilan_pay"], mevcut["tevkifat_varsayilan_pay"])))
    if "tevkifat_varsayilan_payda" in body:
        pd = int(_sayi(body["tevkifat_varsayilan_payda"], mevcut["tevkifat_varsayilan_payda"]))
        yeni["tevkifat_varsayilan_payda"] = pd if pd > 0 else mevcut["tevkifat_varsayilan_payda"]
    if "kdv_oran_tolerans_yuzde" in body:
        yeni["kdv_oran_tolerans_yuzde"] = max(0.0, _sayi(body["kdv_oran_tolerans_yuzde"], mevcut["kdv_oran_tolerans_yuzde"]))
    if "kdv_tutar_tolerans" in body:
        yeni["kdv_tutar_tolerans"] = max(0.0, _sayi(body["kdv_tutar_tolerans"], mevcut["kdv_tutar_tolerans"]))

    return {"ok": True, "ayarlar": _ayar_sansur(ayarlar.yaz(yeni))}


def api_musteri_ekle(body):
    m = depo.musteri_ekle(body.get("unvan", "Yeni Musteri"),
                          body.get("vergi_no", ""))
    depo.donem_getir(m["id"], AKTIF_DONEM, M.kodlar())   # ilk donemi ac
    return {"ok": True, "musteri": m}


def api_musteri_arsiv(body):
    """Musteriyi arsive alir / arsivden cikarir (veri durur, panodan gizlenir).
    Yetki: onay yetkisi olanlar (Ofis Yoneticisi + Muhasebe Muduru)."""
    if not depo.yetkili_mi("onay"):
        return {"hata": "Müşteri arşivleme yetkisi Yönetici/Müdürdedir."}
    m = depo.musteri_arsiv_ayarla(body.get("m"), bool(body.get("arsiv", True)))
    if not m:
        return {"hata": "Müşteri bulunamadı."}
    return {"ok": True, "id": m["id"], "aktif": m.get("aktif", True)}


def api_musteri_sil(body):
    """Musteriyi KALICI siler (kayit + tum donem/yukleme verisi).
    Korumalar: yalniz Ofis Yoneticisi; unvanin AYNEN yazilarak onaylanmasi;
    kilitli donem varsa engel (depo.musteri_sil). Geri donusu yoktur —
    musteri ofisten ayrildiysa dogru yol SILMEK DEGIL ARSIVLEMEKTIR."""
    if not depo.yonetici_mi():
        return {"hata": "Kalıcı silme yetkisi yalnızca Ofis Yöneticisinde."}
    m = depo.musteri_getir(body.get("m"))
    if not m:
        return {"hata": "Müşteri bulunamadı."}
    beklenen = (m.get("unvan") or "").strip()
    yazilan = (body.get("onay_unvan") or "").strip()
    if not beklenen or yazilan != beklenen:
        return {"hata": "Onay için müşteri ünvanını aynen yazmalısınız."}
    return depo.musteri_sil(m["id"])


def api_yukle(body):
    """Modul icin dosya yukler (base64). Kaydeder; modulu hemen calistirir.
    rol verilirse cok-slotlu modul (or. cari bizim/karsi) icin ayri slot."""
    musteri_id = body.get("m"); donem = body.get("d"); kod = body.get("kod")
    mk = depo.musteri_getir(musteri_id)
    if mk and not mk.get("aktif", True):
        return {"hata": "Müşteri arşivde — dosya yüklemek için önce arşivden çıkarın."}
    if depo.donem_kilitli_mi(musteri_id, donem):
        return {"hata": "Dönem kilitli — yeni dosya yüklenemez. Önce kilidi açın."}
    rol = body.get("rol")
    ad = body.get("dosya_adi"); b64 = body.get("dosya_b64", "")
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    icerik = base64.b64decode(b64)
    depo.yuklenen_kaydet(musteri_id, donem, kod, ad, icerik, rol=rol)
    mod = M.getir(kod)
    sonuc = mod.calistir(musteri_id, donem) if mod else {}
    return {"ok": True, "html": mod.panel_html(sonuc) if mod else ""}


def rapor_sayfa(musteri_id, donem, tip):
    """Finansal raporu (gelir/bilanco) AYRI tam sayfa olarak uretir."""
    m = depo.musteri_getir(musteri_id)
    if not m:
        return "<h2>Müşteri bulunamadı.</h2>"
    from moduller import m9_finansal
    sonuc = m9_finansal.calistir(musteri_id, donem)
    govde = m9_finansal.rapor_govde(sonuc, tip)
    bas = "Gelir Tablosu" if tip == "gelir" else "Bilanço"
    return f"""<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{bas} — {m['unvan']}</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link rel="stylesheet" href="/static/stil.css">
<style>@media print{{.no-print{{display:none}}}}</style>
</head><body><div class="container">
  <header><div class="logo-area"><h1><i class="fa-solid fa-chart-line"></i> {bas}</h1>
    <p>{m['unvan']} · {m['id']} · Dönem: {donem}</p></div>
    <div class="header-meta no-print">
      <button class="btn-sec" onclick="window.close()"><i class="fa-solid fa-xmark"></i> Kapat</button>
      <button class="btn" onclick="window.print()"><i class="fa-solid fa-print"></i> Yazdır / PDF</button>
    </div></header>
  <main class="content-container"><section class="panel">{govde}</section></main>
  <footer><p>Ay Kapanış OS &copy; 2026 · Finansal Analiz Raporu</p></footer>
</div></body></html>"""


def kapanis_rapor_sayfa(musteri_id, donem):
    """Tum modulleri birlestiren kapanis raporunu AYRI tam sayfa olarak uretir."""
    m = depo.musteri_getir(musteri_id)
    if not m:
        return "<h2>Müşteri bulunamadı.</h2>"
    from moduller import m8_dosya
    sonuc = m8_dosya.calistir(musteri_id, donem)
    govde = m8_dosya.kapanis_rapor_govde(sonuc)
    return f"""<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kapanış Raporu — {m['unvan']}</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link rel="stylesheet" href="/static/stil.css">
<style>@media print{{.no-print{{display:none}}}}</style>
</head><body><div class="container">
  <header><div class="logo-area"><h1><i class="fa-solid fa-folder-tree"></i> Kapanış Raporu</h1>
    <p>{m['unvan']} · {m['id']} · Dönem: {donem}</p></div>
    <div class="header-meta no-print">
      <button class="btn-sec" onclick="window.close()"><i class="fa-solid fa-xmark"></i> Kapat</button>
      <button class="btn" onclick="window.print()"><i class="fa-solid fa-print"></i> Yazdır / PDF</button>
    </div></header>
  <main class="content-container"><section class="panel">{govde}</section></main>
  <footer><p>Ay Kapanış OS &copy; 2026 · Dönem Kapanış Raporu</p></footer>
</div></body></html>"""


def _mektup_govde(m, donem, cari, y):
    """Tek cari icin mutabakat mektubu govdesi."""
    from moduller.m3_cari import _tl
    k = depo.aktif_kullanici()
    imza = k["ad"] if k else ""
    bugun = y.get("bugun", donem)
    bakiye = cari["net"]
    yon = "borçlu" if bakiye >= 0 else "alacaklı"
    return f"""
    <div style="max-width:720px;margin:0 auto;">
      <p style="text-align:right;color:var(--text-muted);">Tarih: {bugun}</p>
      <p style="margin-top:10px;"><strong>Sayın {cari['cari_adi']}</strong> ({cari['cari_kodu']})</p>
      <p style="margin-top:16px;line-height:1.7;">
        {m['unvan']} ({m['id']}) defter kayıtlarımıza göre, <strong>{bugun}</strong> tarihi itibarıyla
        firmanız ile aramızdaki cari hesap bakiyesi <strong>{_tl(abs(bakiye))}</strong>
        ({yon} bakiye) olarak görünmektedir.</p>
      <p style="margin-top:10px;line-height:1.7;">
        Söz konusu bakiyenin kayıtlarınızla mutabık olup olmadığını, mutabık değilse farkın
        kaynağını belirten dökümü tarafımıza bildirmenizi rica ederiz.</p>
      <table style="margin-top:16px;width:100%;">
        <tr><th style="text-align:left">Yaş Aralığı</th><th style="text-align:right">Tutar</th></tr>
        {"".join(f'<tr><td>{e} gün</td><td style="text-align:right">{_tl(cari["kovalar"][e])}</td></tr>' for e in cari_analiz.KOVA_ETIKET if cari["kovalar"][e])}
        <tr style="font-weight:700;"><td>Toplam</td><td style="text-align:right">{_tl(bakiye)}</td></tr>
      </table>
      <div style="margin-top:40px;display:flex;justify-content:space-between;">
        <div><p style="border-top:1px solid var(--text-muted);padding-top:6px;">{m['unvan']}<br>{imza}</p></div>
        <div><p style="border-top:1px solid var(--text-muted);padding-top:6px;">Karşı Taraf Onayı<br>(Kaşe / İmza)</p></div>
      </div>
      <p style="margin-top:24px;font-size:11px;color:var(--text-muted);">
        Bu mektup bilgilendirme amaçlıdır; defter kayıtlarımız esas alınarak hazırlanmıştır.</p>
    </div>"""


def cari_mektup_sayfa(musteri_id, donem, cari_kodu):
    """Cari mutabakat mektubu — tek cari veya '__hepsi__' icin toplu, ayri sayfa."""
    m = depo.musteri_getir(musteri_id)
    if not m:
        return "<h2>Müşteri bulunamadı.</h2>"
    mod = M.getir("m3_cari")
    sonuc = mod.calistir(musteri_id, donem) if mod else {}
    y = sonuc.get("yaslandirma") or {}
    cariler = y.get("cariler", [])
    if not cariler:
        govde = "<p>Yaşlandırılacak cari bakiye bulunamadı. Önce bizim defter dosyasını yükleyin.</p>"
    elif cari_kodu == "__hepsi__":
        govde = ('<div style="page-break-after:always;"></div>'.join(
            _mektup_govde(m, donem, c, y) for c in cariler))
    else:
        sec = next((c for c in cariler if c["cari_kodu"] == cari_kodu), None)
        govde = (_mektup_govde(m, donem, sec, y) if sec
                 else f"<p>{cari_kodu} kodlu cari için açık bakiye bulunamadı.</p>")
    return f"""<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mutabakat Mektubu — {m['unvan']}</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link rel="stylesheet" href="/static/stil.css">
<style>@media print{{.no-print{{display:none}}}}</style>
</head><body><div class="container">
  <header><div class="logo-area"><h1><i class="fa-solid fa-envelope-open-text"></i> Mutabakat Mektubu</h1>
    <p>{m['unvan']} · {m['id']} · Dönem: {donem}</p></div>
    <div class="header-meta no-print">
      <button class="btn-sec" onclick="window.close()"><i class="fa-solid fa-xmark"></i> Kapat</button>
      <button class="btn" onclick="window.print()"><i class="fa-solid fa-print"></i> Yazdır / PDF</button>
    </div></header>
  <main class="content-container"><section class="panel">{govde}</section></main>
  <footer><p>Ay Kapanış OS &copy; 2026 · Cari Mutabakat Mektubu</p></footer>
</div></body></html>"""


def tevkifat_beyan_sayfa(musteri_id, donem):
    """2 No.lu KDV (tevkifat) beyanname taslagi — yazdirilabilir sayfa."""
    from moduller.m4_gib_kdv import _tl
    m = depo.musteri_getir(musteri_id)
    if not m:
        return "<h2>Müşteri bulunamadı.</h2>"
    mod = M.getir("m4_gib_kdv")
    sonuc = mod.calistir(musteri_id, donem) if mod else {}
    tev = sonuc.get("tevkifat")
    if not tev or tev.get("hata"):
        govde = "<p>Tevkifat listesi bulunamadı veya okunamadı. Önce tevkifat dosyasını yükleyin.</p>"
    else:
        sat = "".join(
            f'<tr><td>{s["islem"]}</td><td style="text-align:right">{_tl(s["matrah"])}</td>'
            f'<td style="text-align:center">%{int(s["kdv_orani"])}</td>'
            f'<td style="text-align:right">{_tl(s["kdv"])}</td>'
            f'<td style="text-align:center">{s["oran_metin"]}</td>'
            f'<td style="text-align:right">{_tl(s["tevkif"])}</td>'
            f'<td style="text-align:right">{_tl(s["indirilecek"])}</td></tr>'
            for s in tev["satirlar"])
        govde = f"""
        <div style="max-width:840px;margin:0 auto;">
          <h2 style="margin-bottom:4px;">KDV Tevkifatı — 2 No.lu Beyanname Taslağı</h2>
          <p style="color:var(--text-muted);">{m['unvan']} ({m['id']}) · Dönem: {donem}</p>
          <p style="margin-top:14px;line-height:1.7;">Aşağıdaki kısmi tevkifata tabi alış hizmetleri için
            alıcı sorumlu sıfatıyla tevkif edilen KDV, <strong>360 Ödenecek Vergi ve Fonlar</strong>
            hesabına kaydedilir ve 2 No.lu KDV beyannamesi ile beyan edilir. Satıcıya ödenen kısım
            <strong>191 İndirilecek KDV</strong>'dir.</p>
          <table style="margin-top:16px;width:100%;">
            <tr><th style="text-align:left">İşlem Türü</th><th style="text-align:right">Matrah</th>
                <th style="text-align:center">KDV%</th><th style="text-align:right">Hesaplanan KDV</th>
                <th style="text-align:center">Tevkifat Oranı</th><th style="text-align:right">Tevkif Edilen (360)</th>
                <th style="text-align:right">İndirilecek (191)</th></tr>
            {sat}
            <tr style="font-weight:700;border-top:2px solid #888;"><td>TOPLAM</td>
              <td style="text-align:right">{_tl(tev['toplam_matrah'])}</td><td></td>
              <td style="text-align:right">{_tl(tev['toplam_kdv'])}</td><td></td>
              <td style="text-align:right">{_tl(tev['toplam_tevkif'])}</td>
              <td style="text-align:right">{_tl(tev['toplam_indirilecek'])}</td></tr>
          </table>
          <p style="margin-top:24px;line-height:1.8;"><strong>Beyan Özeti</strong><br>
            2 No.lu KDV Beyannamesi (sorumlu sıfatıyla ödenecek tevkifat): <strong>{_tl(tev['toplam_tevkif'])}</strong><br>
            1 No.lu KDV Beyannamesi indirilecek KDV (bu hizmetlerden): <strong>{_tl(tev['toplam_indirilecek'])}</strong></p>
          <p style="margin-top:24px;font-size:11px;color:var(--text-muted);">
            Bu taslak yüklenen tevkifat listesinden üretilmiştir; beyan öncesi kontrol amaçlıdır.
            Nihai onay ve beyan kullanıcıya aittir.</p>
        </div>"""
    return f"""<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tevkifat Beyanname Taslağı — {m['unvan']}</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<link rel="stylesheet" href="/static/stil.css">
<style>@media print{{.no-print{{display:none}}}}</style>
</head><body><div class="container">
  <header><div class="logo-area"><h1><i class="fa-solid fa-scissors"></i> Tevkifat Beyanname Taslağı</h1>
    <p>{m['unvan']} · {m['id']} · Dönem: {donem}</p></div>
    <div class="header-meta no-print">
      <button class="btn-sec" onclick="window.close()"><i class="fa-solid fa-xmark"></i> Kapat</button>
      <button class="btn" onclick="window.print()"><i class="fa-solid fa-print"></i> Yazdır / PDF</button>
    </div></header>
  <main class="content-container"><section class="panel">{govde}</section></main>
  <footer><p>Ay Kapanış OS &copy; 2026 · 2 No.lu KDV Beyanname Taslağı</p></footer>
</div></body></html>"""


def api_fis_islem(body):
    """Tek fis icin onay/gonderme islemi; son onay kullanicidadir.
    islem: onayla | gonder | reddet | geri. Modulu yeniden calistirir."""
    musteri_id = body.get("m"); donem = body.get("d")
    anahtar = body.get("anahtar"); islem = body.get("islem")
    HARITA = {"onayla": "onaylandi", "gonder": "gonderildi",
              "reddet": "reddedildi", "geri": "taslak"}
    yeni = HARITA.get(islem)
    if not yeni:
        return {"hata": "Geçersiz işlem."}
    if depo.donem_kilitli_mi(musteri_id, donem):
        return {"hata": "Dönem kilitli — fiş işlemi yapılamaz."}
    # Onay/gonderme/red sadece mudur yetkisinde; "geri" (taslaga al) herkese acik
    if islem in ("onayla", "gonder", "reddet") and not depo.yetkili_mi("onay"):
        return {"hata": "Fiş onay/gönderme yetkisi yalnızca Muhasebe Müdüründe."}
    # Gondermeden once onay sarti
    if islem == "gonder":
        mevcut = depo.fis_durumlari(musteri_id, donem).get(anahtar, {}).get("durum")
        if mevcut != "onaylandi":
            return {"hata": "ERP'ye göndermeden önce fiş onaylanmalı."}
    k = depo.aktif_kullanici()
    depo.fis_durum_guncelle(musteri_id, donem, anahtar, yeni, k["ad"] if k else "")
    mod = M.getir("m6_fis")
    sonuc = mod.calistir(musteri_id, donem) if mod else {}
    return {"ok": True, "html": mod.panel_html(sonuc) if mod else ""}


def api_gecici_vergi(body):
    """Musavirin girdigi KKEG tutarlari + indirim/mahsup parametrelerini saklar,
    gecici vergi modulunu yeniden calistirip yeni paneli doner.
    KKEG aday + musavir ONAY modeli: tutarlari musavir girer; motor fis ATMAZ."""
    musteri_id = body.get("m"); donem = body.get("d")
    if depo.donem_kilitli_mi(musteri_id, donem):
        return {"hata": "Dönem kilitli — geçici vergi girişi yapılamaz."}
    ALANLAR = ("kkeg_gvk40", "kkeg_kvk11", "kkeg_fgk", "kkeg_diger",
               "istisna", "gecmis_zarar", "onceki_hesaplanan", "pesin_odenen")
    veri = {}
    for a in ALANLAR:
        veri[a] = _sayi(body.get(a), 0.0)
    bm = body.get("beyan_matrah")
    veri["beyan_matrah"] = "" if bm in ("", None) else _sayi(bm, 0.0)
    k = depo.aktif_kullanici()
    depo.gecici_vergi_yaz(musteri_id, donem, veri, k["ad"] if k else "")
    mod = M.getir("m10_gecici_vergi")
    sonuc = mod.calistir(musteri_id, donem) if mod else {}
    return {"ok": True, "html": mod.panel_html(sonuc) if mod else ""}


def api_mutabakat_modu(body):
    """Musterinin Akilli Mutabakat sahipligini ac/kapat; modulu yeniden calistirir."""
    musteri_id = body.get("m"); donem = body.get("d")
    deger = bool(body.get("deger"))
    depo.musteri_guncelle(musteri_id, akilli_mutabakat=deger)
    mod = M.getir("m3_cari")
    sonuc = mod.calistir(musteri_id, donem) if mod else {}
    return {"ok": True, "html": mod.panel_html(sonuc) if mod else ""}


# --------------------------------------------------------------------------- #
# HTTP katmani
# --------------------------------------------------------------------------- #
def _dosya_oku(yol):
    with open(yol, encoding="utf-8") as f:
        return f.read()


def _hata_logla(istek, e):
    """Sunucu hatasini stdout'a yazar (Railway log gormesi icin) — canli teshis."""
    import traceback
    print(f"[HATA] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {istek}: {e!r}", flush=True)
    traceback.print_exc()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _gonder(self, data, ctype="application/json; charset=utf-8", code=200):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False)
        if not isinstance(data, (bytes, bytearray)):
            data = data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        # Bu yanitlarin hepsi dinamik (HTML sayfa + API JSON); tarayici onbellege
        # almamali — yoksa eski sablon/sema gosterilir.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(data)

    def _oturum_kur(self, token, hedef="/", max_age=None):
        """Basarili giriste cerez koyar ve hedefe yonlendirir.
        max_age verilirse kalici cerez (Beni Hatirla); verilmezse oturumluk."""
        guvenli = "; Secure" if BULUT else ""
        kalici = f"; Max-Age={int(max_age)}" if max_age else ""
        self.send_response(302)
        self.send_header("Set-Cookie",
                         f"oturum={token}; Path=/; HttpOnly; SameSite=Lax{guvenli}{kalici}")
        self.send_header("Location", hedef)
        self.end_headers()

    def _yonlendir(self, hedef):
        self.send_response(302)
        self.send_header("Location", hedef)
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)
        try:
            # --- Giris kapisi: /giris, /cikis ve /static disinda her sey oturum ister ---
            if p == "/giris":
                kalan = _giris_kilit_kalan(_istemci_ip(self), time.time()) if q.get("kilit") else 0
                return self._gonder(_giris_sayfa(hata=bool(q.get("hata")), kilit=kalan),
                                    "text/html; charset=utf-8")
            if p == "/cikis":
                ck = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
                t = ck.get("oturum")
                if t:
                    _OTURUMLAR.pop(t.value, None)
                    _PLATFORM_OTURUMLAR.pop(t.value, None)
                return self._yonlendir("/giris")
            # --- Platform kapisi: kiraci-disi; kiraci gate'inden ONCE ele alinir ---
            if p == "/yonetim" or p.startswith("/api/kiraci"):
                if not _platform_mi(self):
                    if p.startswith("/api/"):
                        return self._gonder({"hata": "Platform yetkisi gerekli.", "giris": True}, code=401)
                    return self._yonlendir("/giris")
                if p == "/yonetim":
                    return self._gonder(_dosya_oku(os.path.join(TPL, "yonetim.html")),
                                        "text/html; charset=utf-8")
                if p == "/api/kiracilar":
                    return self._gonder(api_kiracilar())
                return self._gonder({"hata": "bulunamadi"}, code=404)
            # --- Karsi taraf PORTALI: oturumsuz ama IMZALI token ile -------------
            # Maildeki link tok=<kid.imza> tasir; imza (kiraci,cari,mukellef)
            # uclusune baglidir. Gecerliyse yalniz portal rotalari, o kiracinin
            # kapsaminda ve o cariyle sinirli servis edilir (bkz. app_logic).
            if p.startswith("/mutabakat/"):
                pub = mutabakat.portal_coz(p[len("/mutabakat"):], q, post=False)
                if pub:
                    if "mutabakat" not in kiraci.kiraci_moduller(pub["kid"]):
                        return self._gonder({"hata": "Modül etkin değil."}, code=403)
                    depo.kiraci_ayarla(pub["kid"])
                    kod, ctype, govde = mutabakat.dispatch_get(
                        p[len("/mutabakat"):], q, _istemci_ip(self),
                        host=self.headers.get("Host", ""), public=pub)
                    return self._gonder(govde, ctype, kod)

            if not p.startswith("/static/"):
                kid = _oturum_kiraci(self)
                if kid is None:
                    if p.startswith("/api/"):
                        return self._gonder({"hata": "Oturum gerekli.", "giris": True}, code=401)
                    # Platform oturumu kiraci sayfasina geldiyse yonetime don.
                    return self._yonlendir("/yonetim" if _platform_mi(self) else "/giris")
                depo.kiraci_ayarla(kid)     # bu istegin tum veri erisimi bu kiraciya kapsanir

            if p in ("/", "/index.html"):
                if _kurulum_gerekli():
                    return self._yonlendir("/kurulum")
                urunler = kiraci.kiraci_moduller(depo.aktif_kiraci())
                # Kiraci birden fazla urune sahipse once urun secim ekranini goster.
                if len(urunler) >= 2:
                    return self._gonder(_dosya_oku(os.path.join(TPL, "urun_secim.html")),
                                        "text/html; charset=utf-8")
                # Tek urun: hangisiyse ona git (mutabakat-only kiraci ay-kapanisa dusmesin).
                if urunler == ["mutabakat"]:
                    return self._yonlendir("/mutabakat/ofis")
                return self._yonlendir("/ay-kapanis")
            if p in ("/ay-kapanis", "/ay-kapanis.html"):
                if _kurulum_gerekli():
                    return self._yonlendir("/kurulum")
                # Urun sahipligi: mutabakat ile ayni kural (capraz satis bayragi iki yonlu).
                if "ay_kapanis" not in kiraci.kiraci_moduller(depo.aktif_kiraci()):
                    return self._yonlendir("/")
                return self._gonder(_dosya_oku(os.path.join(TPL, "ofis_panosu.html")),
                                    "text/html; charset=utf-8")
            if p == "/mutabakat" or p.startswith("/mutabakat/"):
                if "mutabakat" not in kiraci.kiraci_moduller(depo.aktif_kiraci()):
                    return self._yonlendir("/")
                sub = p[len("/mutabakat"):]   # "" | "/ofis" | "/api/yukle" ...
                kod, ctype, govde = mutabakat.dispatch_get(sub, q, _istemci_ip(self),
                                                           host=self.headers.get("Host", ""))
                return self._gonder(govde, ctype, kod)
            if p == "/kurulum":
                if not _kurulum_gerekli():
                    return self._yonlendir("/")
                return self._gonder(_dosya_oku(os.path.join(TPL, "kurulum.html")),
                                    "text/html; charset=utf-8")
            if p in ("/kokpit", "/kokpit.html"):
                return self._gonder(_dosya_oku(os.path.join(TPL, "kapanis_kokpit.html")),
                                    "text/html; charset=utf-8")
            if p == "/rapor":
                return self._gonder(rapor_sayfa((q.get("m") or [""])[0],
                                                (q.get("d") or [""])[0],
                                                (q.get("tip") or ["bilanco"])[0]),
                                    "text/html; charset=utf-8")
            if p == "/kapanis_rapor":
                return self._gonder(kapanis_rapor_sayfa((q.get("m") or [""])[0],
                                                        (q.get("d") or [""])[0]),
                                    "text/html; charset=utf-8")
            if p == "/cari_mektup":
                return self._gonder(cari_mektup_sayfa((q.get("m") or [""])[0],
                                                      (q.get("d") or [""])[0],
                                                      (q.get("cari") or [""])[0]),
                                    "text/html; charset=utf-8")
            if p == "/tevkifat_beyan":
                return self._gonder(tevkifat_beyan_sayfa((q.get("m") or [""])[0],
                                                         (q.get("d") or [""])[0]),
                                    "text/html; charset=utf-8")
            if p.startswith("/static/"):
                ad = os.path.basename(p[len("/static/"):])
                yol = os.path.join(STATIC, ad)
                if os.path.exists(yol):
                    ctype = "text/css" if ad.endswith(".css") else "application/octet-stream"
                    return self._gonder(_dosya_oku(yol), ctype + "; charset=utf-8")
                return self._gonder({"hata": "bulunamadi"}, code=404)
            if p == "/api/urunler":
                return self._gonder(api_urunler())
            if p == "/api/ofis":
                return self._gonder(api_ofis((q.get("d") or [None])[0]))
            if p == "/api/kokpit":
                return self._gonder(api_kokpit((q.get("m") or [""])[0], (q.get("d") or [""])[0]))
            if p == "/api/kullanici_listesi":
                return self._gonder(api_kullanici_listesi())
            if p == "/api/kullanicilar":
                return self._gonder(api_kullanicilar())
            if p == "/api/kurulum_bilgi":
                return self._gonder(api_kurulum_bilgi())
            if p == "/api/ayarlar":
                return self._gonder(api_ayarlar_oku())
            if p == "/api/modul":
                return self._gonder(api_modul((q.get("m") or [""])[0],
                                              (q.get("d") or [""])[0],
                                              (q.get("kod") or [""])[0]))
        except Exception as e:
            _hata_logla(f"GET {self.path}", e)
            return self._gonder({"hata": str(e)}, code=500)
        return self._gonder({"hata": "bulunamadi"}, code=404)

    def do_POST(self):
        p = urlparse(self.path).path
        n = int(self.headers.get("Content-Length", 0))
        ham = self.rfile.read(n)
        # --- Giris formu (urlencoded), JSON'dan ONCE ele alinir ---
        if p == "/giris":
            now = time.time()
            ip = _istemci_ip(self)
            if _giris_kilit_kalan(ip, now):
                return self._yonlendir("/giris?kilit=1")
            params = parse_qs(ham.decode("utf-8", "replace"))
            eposta = (params.get("eposta") or [""])[0]
            parola = (params.get("parola") or [""])[0]
            hatirla = bool((params.get("beni_hatirla") or [""])[0])
            # Once platform sahibi kimligi denenir; degilse kiraci girisi.
            if _platform_dogrula(eposta, parola):
                _giris_basarili(ip)
                t = secrets.token_urlsafe(32)
                _PLATFORM_OTURUMLAR[t] = {"baslangic": now, "son": now}
                return self._oturum_kur(t, "/yonetim")
            k = kiraci.dogrula(eposta, parola)
            if k:
                _giris_basarili(ip)
                t = secrets.token_urlsafe(32)
                o = {"kid": k["id"], "baslangic": now, "son": now}
                if hatirla:   # formdaki "Beni Hatirla (30 gun)" gercekten uygulanir
                    o["bosta"], o["azami"] = HATIRLA_BOSTA_SN, HATIRLA_AZAMI_SN
                _OTURUMLAR[t] = o
                return self._oturum_kur(t, "/", max_age=HATIRLA_AZAMI_SN if hatirla else None)
            _giris_basarisiz(ip, now)
            return self._yonlendir("/giris?hata=1")
        # --- Veri geri yukleme (platform sahibi): lokal veri/ -> bulut volume ---
        # Govde JSON degil ZIP; json.loads'tan ONCE ele alinir. Zip-slip korumali,
        # uygulama oncesi mevcut /data otomatik yedeklenir (geri donulebilir).
        if p == "/api/veri_geri_yukle":
            if not _platform_mi(self):
                return self._gonder({"hata": "Platform yetkisi gerekli.", "giris": True}, code=401)
            try:
                import io, zipfile, shutil
                kok = os.path.abspath(depo.ROOT_VERI)
                zf = zipfile.ZipFile(io.BytesIO(ham))
                adlar = zf.namelist()
                for ad in adlar:
                    hedef = os.path.abspath(os.path.join(kok, ad))
                    if hedef != kok and not hedef.startswith(kok + os.sep):
                        return self._gonder({"hata": f"Guvensiz yol: {ad}"}, code=400)
                yedek = kok.rstrip("/\\") + "_yedek_" + datetime.now().strftime("%Y%m%d_%H%M%S")
                if os.path.isdir(kok) and os.listdir(kok):
                    shutil.copytree(kok, yedek, dirs_exist_ok=True)
                else:
                    yedek = None
                zf.extractall(kok)
                return self._gonder({"ok": True, "dosya": len(adlar),
                                     "yedek": os.path.basename(yedek) if yedek else None})
            except Exception as e:
                _hata_logla("POST /api/veri_geri_yukle", e)
                return self._gonder({"hata": str(e)}, code=500)
        try:
            body = json.loads(ham or b"{}")
            if not isinstance(body, dict):
                body = {}
        except Exception:
            return self._gonder({"hata": "Geçersiz JSON gövdesi."}, code=400)
        # --- Platform yonetim POST'lari: kiraci gate'inden ONCE ---
        if p.startswith("/api/kiraci"):
            if not _platform_mi(self):
                return self._gonder({"hata": "Platform yetkisi gerekli.", "giris": True}, code=401)
            try:
                if p == "/api/kiraci_ekle":
                    return self._gonder(api_kiraci_ekle(body))
                if p == "/api/kiraci_durum":
                    return self._gonder(api_kiraci_durum(body))
                if p == "/api/kiraci_parola":
                    return self._gonder(api_kiraci_parola(body))
                if p == "/api/kiraci_moduller":
                    return self._gonder(api_kiraci_moduller(body))
                if p == "/api/kiraci_sil":
                    return self._gonder(api_kiraci_sil(body))
            except Exception as e:
                _hata_logla(f"POST {p}", e)
                return self._gonder({"hata": str(e)}, code=500)
            return self._gonder({"hata": "bulunamadi"}, code=404)
        # --- Karsi taraf PORTALI (POST): oturumsuz, imzali token govdede ---
        if p.startswith("/mutabakat/"):
            pub = mutabakat.portal_coz(p[len("/mutabakat"):], body, post=True)
            if pub:
                if "mutabakat" not in kiraci.kiraci_moduller(pub["kid"]):
                    return self._gonder({"hata": "Modül etkin değil."}, code=403)
                depo.kiraci_ayarla(pub["kid"])
                try:
                    kod, ctype, govde = mutabakat.dispatch_post(
                        p[len("/mutabakat"):], body, _istemci_ip(self),
                        self.headers.get("User-Agent", ""),
                        host=self.headers.get("Host", ""), public=pub)
                except Exception as e:
                    _hata_logla(f"POST {p}", e)
                    return self._gonder({"hata": str(e)}, code=500)
                return self._gonder(govde, ctype, kod)
        kid = _oturum_kiraci(self)
        if kid is None:
            return self._gonder({"hata": "Oturum gerekli.", "giris": True}, code=401)
        depo.kiraci_ayarla(kid)             # bu istegin tum veri erisimi bu kiraciya kapsanir
        if p.startswith("/mutabakat/"):
            if "mutabakat" not in kiraci.kiraci_moduller(depo.aktif_kiraci()):
                return self._gonder({"hata": "Bu modül kiracıda etkin değil."}, code=403)
            ua = self.headers.get("User-Agent", "")
            try:
                kod, ctype, govde = mutabakat.dispatch_post(p[len("/mutabakat"):], body,
                                                            _istemci_ip(self), ua,
                                                            host=self.headers.get("Host", ""))
            except Exception as e:
                _hata_logla(f"POST {p}", e)
                return self._gonder({"hata": str(e)}, code=500)
            return self._gonder(govde, ctype, kod)
        try:
            if p == "/api/kurulum":
                return self._gonder(api_kurulum(body))
            if p == "/api/erp_test":
                return self._gonder(api_erp_test(body))
            if p == "/api/musteri_ekle":
                return self._gonder(api_musteri_ekle(body))
            if p == "/api/musteri_arsiv":
                return self._gonder(api_musteri_arsiv(body))
            if p == "/api/musteri_sil":
                return self._gonder(api_musteri_sil(body))
            if p == "/api/yukle":
                return self._gonder(api_yukle(body))
            if p == "/api/mutabakat_modu":
                return self._gonder(api_mutabakat_modu(body))
            if p == "/api/fis_islem":
                return self._gonder(api_fis_islem(body))
            if p == "/api/gecici_vergi":
                return self._gonder(api_gecici_vergi(body))
            if p == "/api/aktif_kullanici":
                return self._gonder(api_aktif_kullanici(body))
            if p == "/api/kullanici_ekle":
                return self._gonder(api_kullanici_ekle(body))
            if p == "/api/kullanici_rol":
                return self._gonder(api_kullanici_rol(body))
            if p == "/api/kullanici_sil":
                return self._gonder(api_kullanici_sil(body))
            if p == "/api/donem_kilit":
                return self._gonder(api_donem_kilit(body))
            if p == "/api/ayarlar":
                return self._gonder(api_ayarlar_yaz(body))
        except Exception as e:
            _hata_logla(f"POST {p}", e)
            return self._gonder({"hata": str(e)}, code=500)
        return self._gonder({"hata": "bulunamadi"}, code=404)


def main(port=None):
    # Railway/bulut PORT'u env ile verir; yerelde 5050.
    port = port or int(os.environ.get("PORT", 5050))
    # Bulutta 0.0.0.0'a baglanmak zorunlu; yerelde sadece localhost.
    bulut = bool(os.environ.get("PORT"))
    host = os.environ.get("HOST") or ("0.0.0.0" if bulut else "127.0.0.1")
    seed()
    srv = ThreadingHTTPServer((host, port), Handler)
    url = f"http://localhost:{port}"
    print(f"Ay Kapanis OS calisiyor:  {host}:{port}", flush=True)
    vk = kiraci.kiraci_getir("varsayilan")
    if vk:
        print(f"Varsayilan giris      :  {vk['eposta']}  /  {GIRIS_PAROLASI or '1234'}", flush=True)
    print(f"Platform yonetim giris:  {PLATFORM_EPOSTA}  /  {PLATFORM_PAROLA}   ->  /yonetim", flush=True)
    print(f"Kayitli kiraci sayisi :  {len(kiraci.kiracilari_getir())}", flush=True)
    print("Kapatmak icin Ctrl+C.", flush=True)
    if not bulut:                       # tarayiciyi yalniz yerelde ac
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nKapatiliyor...")
        srv.shutdown()


# --------------------------------------------------------------------------- #
# Demo/seed verisi (ilk calistirmada ornek musteriler olusturur)
# --------------------------------------------------------------------------- #
def _varsayilan_kiraci_seed():
    """Hicbir kiraci yoksa giris yapilabilsin diye 'varsayilan' kiraciyi olusturur.
    Eposta: VARSAYILAN_EPOSTA env'i (yoksa ofis@aykapanis.local).
    Parola: GIRIS_PAROLASI env'i (yoksa 1234)."""
    if kiraci.kiraci_getir("varsayilan"):
        return
    eposta = os.environ.get("VARSAYILAN_EPOSTA", "ofis@aykapanis.local")
    parola = GIRIS_PAROLASI or "1234"
    kayitlar = kiraci.kiracilari_getir()
    kayitlar.append({
        "id": "varsayilan", "unvan": "Varsayılan Ofis", "tip": "ofis",
        "eposta": eposta, "parola_hash": kiraci._hash_parola(parola),
        "paket": "pilot", "aktif": True,
        "olusturma": datetime.now().strftime("%Y-%m-%d"),
    })
    depo._yaz(kiraci.KIRACILAR_JSON, kayitlar)


def seed():
    _varsayilan_kiraci_seed()
    if not depo.kullanicilari_getir():
        depo.kullanici_ekle("Ayşe Yılmaz (Yönetici)", "yonetici")
        depo.kullanici_ekle("Mehmet Demir", "eleman")
    if depo.musterileri_getir():
        return
    ornekler = [
        ("ÖRNEK SANAYİ A.Ş.", "1234567890", "Logo Tiger"),
        ("DEMİR ÇELİK TİC. LTD.", "2345678901", "Mikro"),
        ("GÜL PLASTİK SAN. A.Ş.", "3456789012", "Netsis"),
        ("CEYHAN LOJİSTİK A.Ş.", "4567890123", "Dosya Yükleme"),
    ]
    kodlar = M.kodlar()
    for unvan, vno, erp in ornekler:
        m = depo.musteri_ekle(unvan, vno, erp)
        d = depo.donem_getir(m["id"], AKTIF_DONEM, kodlar)
        d["son_tarih"] = "2026-06-26"
        depo.donem_kaydet(m["id"], AKTIF_DONEM, d)


if __name__ == "__main__":
    main()
