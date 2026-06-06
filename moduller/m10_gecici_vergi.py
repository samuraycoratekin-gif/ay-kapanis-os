# -*- coding: utf-8 -*-
"""M10 - Gecici Vergi (Kurum) Hazirlik & Matrah Motoru.

Ceyrek kapanis mizanindan ticari kari alir; musavirin onayladigi KKEG +
indirimlerle matrah ve odenecek gecici vergiyi uretir. Enflasyon modulunun
sira=8 slotunu devraldi (enflasyon arsivde).

Capstone modul: degeri diger modulleri (M2/M3/M4/M6) CAPRAZ okuyunca dogar.
  (1) Hazirlik kontrol listesi  -> diger modul durumlarini oku
  (2) KKEG aday avcisi           -> mizandan aday, musavir onaylar (yari-oto)
  (3) Matrah & vergi (%25 + asgari %10 MAX)
  (4) Ters-mutabakat             -> beyan matrahi <-> motor matrahi
  (5) Tahakkuk fisi 691/370 ONERISI -> M6'ya akar, onay musavirde

ILK SURUM: yalnizca KURUMLAR (sabit %25). Gelir vergisi gecici sonraya.
"""
from core.moduller import Modul, kaydet
from core import depo, mizan_oku, finansal_analiz, gecici_vergi

AD = "Geçici ve Kurumlar Vergisine Hazırlık"
ACIKLAMA = ("Çeyrek kapanış mizanından kurumlar geçici vergi matrahı, KKEG aday "
            "avcısı, asgari vergi kontrolü ve tahakkuk fişi önerisi (689→KKEG, 691/370).")

# Hazirlik kontrol listesi: matrahi etkileyen/besleyen moduller.
_KONTROL = [
    ("m2_mizan", "Mizan yüklü & sağlık taraması", "Matrahın temeli — mizan olmadan hesap yok."),
    ("m6_fis", "Dönem fişleri (amortisman/kur farkı/reeskont)", "Ticari kârı doğrudan değiştirir; eksikse matrah yanlış çıkar."),
    ("m4_gib_kdv", "KDV / GİB mutabakatı", "Beyan bütünlüğü; tevkifat/KDV uyumu."),
    ("m3_cari", "Cari mutabakat", "Şüpheli alacak karşılığı / kur farkı kârı etkiler."),
    ("m13_stok", "Stok & SMM", "SMM yanlışsa ticari kâr yanlış."),
]


def _kontrol_listesi(musteri_id, donem):
    from core.moduller import liste
    kodlar = [m.kod for m in liste()]
    durum = depo.donem_getir(musteri_id, donem, kodlar)
    md = durum.get("moduller", {})
    cikti = []
    for kod, ad, neden in _KONTROL:
        d = (md.get(kod) or {}).get("durum", "bekliyor")
        dosya_var = bool(depo.yuklenen_bul(musteri_id, donem, kod))
        if d == "tamam":
            sev = "tamam"
        elif d in ("uyari", "hata"):
            sev = "uyari"
        elif dosya_var:
            # Dosya yuklu ama modul henuz "tamam" degil -> EKSIK degil, kontrol et.
            sev = "uyari"
        else:
            sev = "eksik"
        cikti.append({"kod": kod, "ad": ad, "neden": neden,
                      "modul_durum": d, "seviye": sev, "dosya_var": dosya_var})
    return cikti


def calistir(musteri_id, donem):
    yol = depo.yuklenen_bul(musteri_id, donem, "m2_mizan")
    if not yol:
        depo.modul_durum_guncelle(musteri_id, donem, "m10_gecici_vergi",
                                  durum="bekliyor", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": False}
    try:
        mizan = mizan_oku.oku(yol)
        analiz = finansal_analiz.analiz(mizan)
    except Exception as e:
        depo.modul_durum_guncelle(musteri_id, donem, "m10_gecici_vergi",
                                  durum="hata", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": True, "hata": str(e)}

    ticari_kar = analiz["bilanco"]["donem_kari"]
    adaylar = gecici_vergi.kkeg_adaylari(mizan)
    g = depo.gecici_vergi_oku(musteri_id, donem)        # musavir girisi

    # KKEG: musavirin onayladigi tutarlar (yoksa 0). Aday toplamlari ONERI olarak ayrica gosterilir.
    kkeg_gvk40 = float(g.get("kkeg_gvk40", 0) or 0)
    kkeg_kvk11 = float(g.get("kkeg_kvk11", 0) or 0)
    kkeg_fgk = float(g.get("kkeg_fgk", 0) or 0)
    kkeg_diger = float(g.get("kkeg_diger", 0) or 0)
    kkeg_toplam = round(kkeg_gvk40 + kkeg_kvk11 + kkeg_fgk + kkeg_diger, 2)

    istisna = float(g.get("istisna", 0) or 0)
    gecmis_zarar = float(g.get("gecmis_zarar", 0) or 0)
    onceki_hesaplanan = float(g.get("onceki_hesaplanan", 0) or 0)
    pesin_odenen = float(g.get("pesin_odenen", 0) or 0)
    beyan_matrah = g.get("beyan_matrah", None)
    if beyan_matrah in ("", None):
        beyan_matrah = None
    else:
        beyan_matrah = float(beyan_matrah)

    h = gecici_vergi.hesapla(
        ticari_kar=ticari_kar, kkeg=kkeg_toplam, istisna=istisna,
        gecmis_zarar=gecmis_zarar, onceki_hesaplanan=onceki_hesaplanan,
        pesin_odenen=pesin_odenen, damga=gecici_vergi.DAMGA_GECICI)

    tmut = gecici_vergi.ters_mutabakat(h["matrah"], beyan_matrah)
    fis = gecici_vergi.fis_onerisi(h["mahsup_sonrasi"])
    kontrol = _kontrol_listesi(musteri_id, donem)
    ceyrek = gecici_vergi.ceyrek_bilgi(donem)

    # Bulgu/durum: eksik kontrol kalemi + ters-mutabakat uyumsuzlugu uyaridir.
    eksik = sum(1 for k in kontrol if k["seviye"] != "tamam")
    mutabakat_uyari = 1 if (tmut.get("karsilastirildi") and not tmut.get("uyumlu")) else 0
    bulgu = eksik + mutabakat_uyari
    if bulgu == 0:
        durum, ilerleme = "tamam", 100
    elif eksik and not (kkeg_toplam or istisna or gecmis_zarar):
        durum, ilerleme = "bekliyor", 30
    else:
        durum, ilerleme = "uyari", 70
    depo.modul_durum_guncelle(musteri_id, donem, "m10_gecici_vergi",
                              durum=durum, ilerleme=ilerleme, bulgu_sayisi=bulgu)

    return {
        "hazir": True, "donem": donem, "ceyrek": ceyrek,
        "ticari_kar": ticari_kar, "hesap": h, "adaylar": adaylar,
        "giris": {"kkeg_gvk40": kkeg_gvk40, "kkeg_kvk11": kkeg_kvk11,
                  "kkeg_fgk": kkeg_fgk, "kkeg_diger": kkeg_diger,
                  "istisna": istisna, "gecmis_zarar": gecmis_zarar,
                  "onceki_hesaplanan": onceki_hesaplanan,
                  "pesin_odenen": pesin_odenen,
                  "beyan_matrah": ("" if beyan_matrah is None else beyan_matrah)},
        "ters_mutabakat": tmut, "fis": fis, "kontrol": kontrol,
        "kkeg_toplam": kkeg_toplam,
    }


# --------------------------------------------------------------------------- #
def _tl(v):
    return f"{(v or 0):,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def _yukleme_uyari():
    return f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-file-invoice-dollar"></i> {AD}</h2>
      <p>{ACIKLAMA}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-file-invoice-dollar"></i></div>
    </div>
    <div class="notif-pill" style="margin-top:16px;">
      <i class="fa-solid fa-circle-info" style="color:var(--accent-cyan)"></i>
      <span>Bu modül çeyrek mizanından beslenir. Önce <strong>Mizan Sağlık Taraması</strong> sekmesinden mizanı yükleyin.</span>
    </div>"""


_SEV_BADGE = {"tamam": "success", "uyari": "warn", "eksik": "err"}


def _kontrol_etiket(k):
    """Rozet metni: dosya yuklu mu, modul tamam mi belli olsun (yanlis 'eksik' olmasin)."""
    if k["seviye"] == "tamam":
        return "hazır"
    if k["seviye"] == "eksik":
        return "yüklenmedi"
    return "yüklü · kontrol et" if k.get("dosya_var") else "kontrol et"


def _kontrol_html(kontrol):
    sat = "".join(
        f'<tr><td><span class="badge {_SEV_BADGE[k["seviye"]]}">{_kontrol_etiket(k)}</span></td>'
        f'<td><strong>{k["ad"]}</strong></td>'
        f'<td style="color:var(--text-muted);font-size:12px">{k["neden"]}</td></tr>'
        for k in kontrol)
    return (f'<div style="overflow-x:auto;"><table>'
            f'<tr><th>Durum</th><th>Adım</th><th>Neden önemli</th></tr>{sat}</table></div>')


def _aday_html(adaylar):
    blok = []
    for kod, d in adaylar.items():
        if not d["kalemler"]:
            continue
        sat = "".join(
            f'<tr><td>{x["hesap"]}</td><td>{x["ad"]}</td>'
            f'<td style="text-align:right">{_tl(x["bakiye"])}</td></tr>'
            for x in d["kalemler"])
        blok.append(
            f'<div style="margin-top:12px;"><strong style="font-size:13px;">{d["ad"]}</strong>'
            f' <span class="badge neutral">aday toplam {_tl(d["toplam"])}</span>'
            f'<div style="overflow-x:auto;margin-top:6px;"><table>'
            f'<tr><th>Hesap</th><th>Ad</th><th>Bakiye</th></tr>{sat}</table></div></div>')
    if not blok:
        return ('<div class="notif-pill"><div class="circle-icon-badge"></div>'
                '<span>Mizanda otomatik KKEG adayı bulunamadı — tutarları aşağıdan elle girin.</span></div>')
    return ('<p style="color:var(--text-muted);font-size:12px;margin-bottom:4px;">'
            'Bunlar <strong>ADAYDIR</strong>; nihai KKEG tutarını aşağıdaki forma siz girersiniz.</p>'
            + "".join(blok))


def _g(giris, k):
    v = giris.get(k, "")
    return "" if v in ("", None) else v


def _form_html(giris):
    def inp(ad, etiket, ipucu=""):
        return (f'<div style="display:flex;flex-direction:column;gap:4px;">'
                f'<label style="font-size:12px;color:var(--text-muted);">{etiket}'
                f'{(" · " + ipucu) if ipucu else ""}</label>'
                f'<input type="number" step="0.01" id="gv_{ad}" value="{_g(giris, ad)}" '
                f'placeholder="0,00" style="padding:8px 10px;border-radius:8px;'
                f'border:1px solid var(--border);background:var(--bg-input,rgba(255,255,255,0.04));'
                f'color:var(--text);font-size:14px;"></div>')
    return f"""
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:8px;">
      {inp("kkeg_gvk40", "KKEG — GVK 40 binek oto", "gider/amort/kira kısıtı")}
      {inp("kkeg_kvk11", "KKEG — KVK m.11 genel", "MTV, ceza, gec. zammı, bağış")}
      {inp("kkeg_fgk", "KKEG — finansman gider kısıtı", "KVK 11/1-i %10")}
      {inp("kkeg_diger", "KKEG — diğer", "")}
      {inp("istisna", "İstisnalar (−)", "iştirak kazancı vb.")}
      {inp("gecmis_zarar", "Geçmiş yıl zararı (−)", "5 yıl")}
      {inp("onceki_hesaplanan", "Önceki dönem hesaplanan (−)", "kümülatif mahsup")}
      {inp("pesin_odenen", "Peşin ödenen / stopaj (−)", "193")}
      {inp("beyan_matrah", "Beyan edilecek matrah", "ters-mutabakat için (ops.)")}
    </div>
    <button onclick="geciciKaydet()" class="btn-primary" style="margin-top:14px;padding:10px 18px;border-radius:10px;border:none;cursor:pointer;font-weight:600;background:var(--accent-cyan);color:#06121a;">
      <i class="fa-solid fa-floppy-disk"></i> Hesapla & Kaydet</button>"""


def _matrah_html(h):
    sat = [
        ("Ticari kâr / zarar", h["ticari_kar"], ""),
        ("+ KKEG", h["kkeg"], "kanunen kabul edilmeyen giderler"),
        ("− İstisnalar", -h["istisna"], ""),
        ("− Geçmiş yıl zararı", -h["gecmis_zarar"], ""),
    ]
    govde = "".join(
        f'<tr><td>{ad}</td><td style="text-align:right">{_tl(v)}</td>'
        f'<td style="color:var(--text-muted);font-size:12px">{nt}</td></tr>'
        for ad, v, nt in sat)
    govde += (f'<tr style="border-top:2px solid var(--border);"><td><strong>Matrah</strong>'
              f'{" (negatif → 0)" if h["matrah_negatif"] else ""}</td>'
              f'<td style="text-align:right"><strong>{_tl(h["matrah"])}</strong></td><td></td></tr>')
    return f'<div style="overflow-x:auto;"><table>{govde}</table></div>'


def _vergi_html(h):
    asg = ('<span class="badge warn">asgari %10 bağlayıcı</span>' if h["asgari_baglayici"]
           else '<span class="badge success">normal %25 geçerli</span>')
    sat = (
        f'<tr><td>Normal vergi (matrah × %{int(h["oran"]*100)})</td>'
        f'<td style="text-align:right">{_tl(h["normal_vergi"])}</td></tr>'
        f'<tr><td>Asgari vergi (matrah × %{int(h["asgari_oran"]*100)})</td>'
        f'<td style="text-align:right">{_tl(h["asgari_vergi"])}</td></tr>'
        f'<tr><td><strong>Hesaplanan (MAX)</strong> {asg}</td>'
        f'<td style="text-align:right"><strong>{_tl(h["hesaplanan"])}</strong></td></tr>'
        f'<tr><td>− Önceki dönem hesaplanan</td><td style="text-align:right">{_tl(-h["onceki_hesaplanan"])}</td></tr>'
        f'<tr><td>− Peşin ödenen / stopaj</td><td style="text-align:right">{_tl(-h["pesin_odenen"])}</td></tr>'
        f'<tr><td>Mahsup sonrası geçici vergi</td><td style="text-align:right">{_tl(h["mahsup_sonrasi"])}</td></tr>'
        f'<tr><td>+ Damga vergisi (sabit)</td><td style="text-align:right">{_tl(h["damga"])}</td></tr>'
        f'<tr style="border-top:2px solid var(--border);"><td><strong>Ödenecek</strong></td>'
        f'<td style="text-align:right"><strong>{_tl(h["odenecek"])}</strong></td></tr>')
    return f'<div style="overflow-x:auto;"><table>{sat}</table></div>'


def _mutabakat_html(t):
    if not t.get("karsilastirildi"):
        return ('<div class="notif-pill"><i class="fa-solid fa-circle-info" style="color:var(--accent-cyan)"></i>'
                '<span>Beyan matrahını girerseniz, motorun ürettiği matrahla karşılaştırıp '
                '<strong>yanlış beyanı göndermeden</strong> yakalarız.</span></div>')
    if t["uyumlu"]:
        return (f'<div class="notif-pill"><i class="fa-solid fa-circle-check" style="color:var(--accent-emerald)"></i>'
                f'<span>Beyan matrahı ({_tl(t["beyan_matrah"])}) motor matrahıyla <strong>uyumlu</strong>.</span></div>')
    return (f'<div class="notif-pill" style="border-color:var(--accent-rose);">'
            f'<i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-rose)"></i>'
            f'<span><strong>UYUMSUZ:</strong> beyan {_tl(t["beyan_matrah"])} ≠ motor {_tl(t["motor_matrah"])} '
            f'(fark {_tl(t["fark"])}). Göndermeden önce kontrol edin.</span></div>')


def _fis_html(fis):
    if not fis:
        return ('<div class="notif-pill"><div class="circle-icon-badge"></div>'
                '<span>Ödenecek geçici vergi 0 — tahakkuk fişi önerisi yok.</span></div>')
    sat = "".join(
        f'<tr><td><strong>{s["hesap"]}</strong> {s["ad"]}</td>'
        f'<td style="text-align:right">{_tl(s["borc"]) if s["borc"] else "—"}</td>'
        f'<td style="text-align:right">{_tl(s["alacak"]) if s["alacak"] else "—"}</td></tr>'
        for s in fis["satirlar"])
    return (f'<p style="color:var(--text-muted);font-size:12px;margin-bottom:6px;">'
            f'{fis["aciklama"]} — <strong>öneri</strong>, M6\'ya akar; onay/kayıt sizde.</p>'
            f'<div style="overflow-x:auto;"><table>'
            f'<tr><th>Hesap</th><th>Borç</th><th>Alacak</th></tr>{sat}</table></div>')


def panel_html(sonuc):
    if not sonuc.get("hazir"):
        return _yukleme_uyari()
    if sonuc.get("hata"):
        return (_yukleme_uyari() +
                f'<p style="margin-top:16px;color:var(--accent-rose);">Okuma hatası: {sonuc["hata"]}</p>')

    h = sonuc["hesap"]
    c = sonuc["ceyrek"]
    ust = f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-file-invoice-dollar"></i> {AD}</h2>
      <p>Dönem {sonuc['donem']} · {c['ad']} · kurumlar geçici vergi (sabit %25)</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-file-invoice-dollar"></i></div>
    </div>
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card"><div class="stat-header"><span>Ticari Kâr/Zarar</span><i class="fa-solid fa-scale-balanced" style="color:var(--accent-cyan)"></i></div><div class="stat-val" style="font-size:18px;">{_tl(sonuc['ticari_kar'])}</div><div class="stat-desc"><span class="ipucu">mizandan</span></div></div>
      <div class="stat-card gold"><div class="stat-header"><span>KKEG (onaylı)</span><i class="fa-solid fa-ban" style="color:var(--accent-gold)"></i></div><div class="stat-val" style="font-size:18px;">{_tl(sonuc['kkeg_toplam'])}</div><div class="stat-desc"><span class="ipucu">+matraha</span></div></div>
      <div class="stat-card"><div class="stat-header"><span>Matrah</span><i class="fa-solid fa-calculator" style="color:var(--accent-cyan)"></i></div><div class="stat-val" style="font-size:18px;">{_tl(h['matrah'])}</div><div class="stat-desc"><span class="ipucu">{'negatif → 0' if h['matrah_negatif'] else 'pozitif'}</span></div></div>
      <div class="stat-card emerald"><div class="stat-header"><span>Ödenecek Geçici Vergi</span><i class="fa-solid fa-hand-holding-dollar" style="color:var(--accent-emerald)"></i></div><div class="stat-val" style="font-size:18px;">{_tl(h['odenecek'])}</div><div class="stat-desc"><span class="ipucu">{'asgari %10' if h['asgari_baglayici'] else 'normal %25'}</span></div></div>
    </div>"""

    def bolum(ikon, renk, baslik, govde):
        return (f'<div style="margin-top:24px;"><h3 style="font-family:\'Outfit\',sans-serif;'
                f'font-size:16px;margin-bottom:12px;"><i class="fa-solid {ikon}" '
                f'style="color:{renk}"></i> {baslik}</h3>{govde}</div>')

    return (ust
            + bolum("fa-list-check", "var(--accent-cyan)", "1 · Hazırlık Kontrol Listesi",
                    _kontrol_html(sonuc["kontrol"]))
            + bolum("fa-magnifying-glass-dollar", "var(--accent-gold)", "2 · KKEG Aday Avcısı (yarı-otomatik)",
                    _aday_html(sonuc["adaylar"]))
            + bolum("fa-keyboard", "var(--accent-cyan)", "3 · KKEG & İndirim Girişi (onay sizde)",
                    _form_html(sonuc["giris"]))
            + bolum("fa-calculator", "var(--accent-cyan)", "4 · Matrah",
                    _matrah_html(h))
            + bolum("fa-coins", "var(--accent-emerald)", "5 · Hesaplanan & Ödenecek Vergi",
                    _vergi_html(h))
            + bolum("fa-scale-unbalanced-flip", "var(--accent-gold)", "6 · Ters-Mutabakat",
                    _mutabakat_html(sonuc["ters_mutabakat"]))
            + bolum("fa-file-pen", "var(--accent-emerald)", "7 · Tahakkuk Fişi Önerisi (691/370 → M6)",
                    _fis_html(sonuc["fis"])))


kaydet(Modul("m10_gecici_vergi", AD, "fa-file-invoice-dollar", 10, calistir, panel_html))
