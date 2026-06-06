# -*- coding: utf-8 -*-
"""M11 - Vergi Takvimi & Beyanname Son Tarihleri.

Tarih odakli (mizan sart degil). Kapanis donemi icin verilmesi gereken
beyannamelerin yasal son gunlerini, tatil kaymasiyla ve bugune gore kalan gun
ile listeler. Mizan/yuklemeler varsa capraz besleme ile hangi beyannamelerin
beklendigi netlestirilir (tevkifat->KDV2, bordro->Muhtasar+SGK).
"""
from core.moduller import Modul, kaydet
from core import depo, mizan_oku, vergi_takvim

AD = "Vergi Takvimi & Beyanname"
ACIKLAMA = "Döneme ait beyanname son tarihleri, tatil kayması ve kalan gün; tevkifat/bordro varlığına göre beklenen beyannameler."

TOL = 1.0


def _baglam(musteri_id, donem):
    """Mizan + yuklemelerden hangi beyannamelerin beklendigini cikarir."""
    bg = {"kdv_var": True, "tevkifat_var": False, "bordro_var": True,
          "damga_var": True, "mizan_var": False}
    mizan_yol = depo.yuklenen_bul(musteri_id, donem, "m2_mizan")
    if mizan_yol:
        try:
            h = mizan_oku.oku(mizan_yol)["hesaplar"]
            bg["mizan_var"] = True
            bg["kdv_var"] = any(h.get(k) for k in ("191", "391"))
            o361 = h.get("361") or {}
            o335 = h.get("335") or {}
            bg["bordro_var"] = (abs((o361.get("toplam") or 0)) > TOL
                                or abs((o335.get("toplam") or 0)) > TOL)
            o360 = h.get("360") or {}
            bg["damga_var"] = abs((o360.get("toplam") or 0)) > TOL or bg["kdv_var"]
        except Exception:
            pass
    # Tevkifat: m4 tevkifat yuklemesi varsa kesin beklenir
    if depo.yuklenen_bul(musteri_id, donem, "m4_gib_kdv", rol="tevkifat"):
        bg["tevkifat_var"] = True
    # Bordro: m12 yuklemesi varsa kesin beklenir
    if depo.yuklenen_bul(musteri_id, donem, "m12_bordro", rol="icmal"):
        bg["bordro_var"] = True
    return bg


def calistir(musteri_id, donem):
    bg = _baglam(musteri_id, donem)
    r = vergi_takvim.beyannameler(donem, bg)
    r["baglam"] = bg
    bulgu = r["gecti_sayisi"] + r["kritik_sayisi"]
    if r["gecti_sayisi"]:
        durum, ilerleme = "uyari", 40
    elif r["kritik_sayisi"]:
        durum, ilerleme = "uyari", 70
    else:
        durum, ilerleme = "tamam", 100
    depo.modul_durum_guncelle(musteri_id, donem, "m11_beyan",
                              durum=durum, ilerleme=ilerleme, bulgu_sayisi=bulgu)
    r["hazir"] = True
    return r


# --------------------------------------------------------------------------- #
_DURUM_RENK = {"gecti": "var(--accent-rose)", "kritik": "var(--accent-rose)",
               "yaklasiyor": "var(--accent-gold)", "var": "var(--accent-emerald)"}
_DURUM_BADGE = {"gecti": "err", "kritik": "err", "yaklasiyor": "warn", "var": "success"}
_DURUM_AD = {"gecti": "GEÇTİ", "kritik": "kritik", "yaklasiyor": "yaklaşıyor", "var": "zamanı var"}


def _kalan_str(k):
    if k["kalan_gun"] < 0:
        return f'<span style="color:var(--accent-rose)">{abs(k["kalan_gun"])} gün geçti</span>'
    if k["kalan_gun"] == 0:
        return '<span style="color:var(--accent-rose)">bugün son gün</span>'
    return f'{k["kalan_gun"]} gün kaldı'


def _satir(k):
    pasif = "" if k["beklenir"] else ' style="opacity:0.45"'
    kaydi = (' <i class="fa-solid fa-calendar-day" title="Tatil/hafta sonu nedeniyle kaydırıldı" '
             'style="color:var(--accent-gold);font-size:11px;"></i>') if k["kaydi_mi"] else ""
    beklenmez = '' if k["beklenir"] else ' <span class="badge neutral">beklenmiyor</span>'
    return (f'<tr{pasif}>'
            f'<td><span class="badge {_DURUM_BADGE[k["durum"]]}">{_DURUM_AD[k["durum"]]}</span></td>'
            f'<td><strong>{k["kod"]}</strong> — {k["ad"]}{beklenmez}</td>'
            f'<td>{k["ilgili"]}</td>'
            f'<td>{k["tarih"]}{kaydi}</td>'
            f'<td>{_kalan_str(k)}</td>'
            f'<td style="color:var(--text-muted);font-size:12px">{k["not"]}</td>'
            f'</tr>')


def panel_html(sonuc):
    r = sonuc
    bg = r.get("baglam", {})
    kaynak = ("mizan + yüklemelerden türetildi" if bg.get("mizan_var")
              else "mizan yok — varsayılan kapsam (yükleme sonrası netleşir)")
    ust = f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-calendar-check"></i> {AD}</h2>
      <p>Dönem {r['donem']} · bugün {r['bugun']} · kapsam: {kaynak}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-calendar-check"></i></div>
    </div>
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card {'rose' if r['gecti_sayisi'] else ''} filtre-kart" data-hedef="gecti" onclick="bulguFiltrele('gecti', this)"><div class="stat-header"><span>Süresi Geçen</span><i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-rose)"></i></div><div class="stat-val">{r['gecti_sayisi']}</div><div class="stat-desc"><span class="ipucu">acil</span></div></div>
      <div class="stat-card gold filtre-kart" data-hedef="kritik" onclick="bulguFiltrele('kritik', this)"><div class="stat-header"><span>Yaklaşan (≤10 gün)</span><i class="fa-solid fa-hourglass-half" style="color:var(--accent-gold)"></i></div><div class="stat-val">{r['kritik_sayisi']}</div><div class="stat-desc"><span class="ipucu">takip et</span></div></div>
      <div class="stat-card filtre-kart" data-hedef="all" onclick="bulguFiltrele('all', this)"><div class="stat-header"><span>Beklenen Beyanname</span><i class="fa-solid fa-file-invoice" style="color:var(--accent-cyan)"></i></div><div class="stat-val">{r['aktif_sayisi']}</div><div class="stat-desc"><span class="ipucu">bu dönem</span></div></div>
      <div class="stat-card emerald filtre-kart aktif" data-hedef="all" onclick="bulguFiltrele('all', this)"><div class="stat-header"><span>Takvimdeki Tüm Kalem</span><i class="fa-solid fa-list-check" style="color:var(--accent-emerald)"></i></div><div class="stat-val">{len(r['kayitlar'])}</div><div class="stat-desc"><span class="ipucu">Tümünü göster</span></div></div>
    </div>"""

    aktif = [k for k in r["kayitlar"] if k["beklenir"]]
    pasif = [k for k in r["kayitlar"] if not k["beklenir"]]
    gecti = [k for k in aktif if k["durum"] == "gecti"]
    kritik = [k for k in aktif if k["durum"] in ("kritik", "yaklasiyor")]

    def blok(grup, baslik, ikon, renk, kayit):
        govde = (f'<div style="overflow-x:auto;"><table>'
                 f'<tr><th>Durum</th><th>Beyanname</th><th>Hesap</th><th>Son Tarih</th><th>Kalan</th><th>Not</th></tr>'
                 + "".join(_satir(k) for k in kayit) + '</table></div>') if kayit else \
                ('<div class="notif-pill"><div class="circle-icon-badge"></div>'
                 '<span>Bu grupta kalem yok.</span></div>')
        return f"""<div class="filtre-bolum" data-grup="{grup}" style="margin-top:24px;">
          <h3 style="font-family:'Outfit',sans-serif;font-size:16px;margin-bottom:12px;">
          <i class="fa-solid {ikon}" style="color:{renk}"></i> {baslik}
          <span class="badge {'warn' if kayit else 'success'}" style="margin-left:8px;">{len(kayit)}</span></h3>
          {govde}</div>"""

    b_all = blok("all", "Tüm Beyanname Takvimi", "fa-calendar-days", "var(--accent-cyan)", r["kayitlar"])
    b_gecti = blok("gecti", "Süresi Geçenler", "fa-triangle-exclamation", "var(--accent-rose)", gecti)
    b_kritik = blok("kritik", "Yaklaşanlar", "fa-hourglass-half", "var(--accent-gold)", kritik)
    return ust + b_gecti + b_kritik + b_all


kaydet(Modul("m11_beyan", AD, "fa-calendar-check", 11, calistir, panel_html))
