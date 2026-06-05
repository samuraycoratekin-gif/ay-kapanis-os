# -*- coding: utf-8 -*-
"""M9 - Finansal Analiz: Gelir Tablosu + Bilanco (yonetici raporu).

Mizandan (M2) calisir, EK DOSYA GEREKMEZ. Kokpit panelinde iki giris karti
(Gelir Tablosu / Bilanco) gosterir; karta tiklayinca AYRI SAYFADA tam yonetici
raporu acilir. Tum oranlar, donem/aylik karsilastirmalari ve finansal riskler
muhasebe muduru/patron onunde sunulacak kalitede hazirlanir.
"""
import calendar
from datetime import date
from core.moduller import Modul, kaydet
from core import depo, mizan_oku, finansal_analiz, varlik_oku, cari_oku, cari_analiz

AD = "Finansal Analiz"
ACIKLAMA = "Gelir tablosu ve bilanço analizi — geçmiş ay/dönem karşılaştırmaları ve tüm finansal riskler."


def _mizan(musteri_id, donem):
    yol = depo.yuklenen_bul(musteri_id, donem, "m2_mizan")
    if not yol:
        return None
    try:
        return mizan_oku.oku(yol)
    except Exception:
        return None


def calistir(musteri_id, donem):
    mizan = _mizan(musteri_id, donem)
    if not mizan:
        depo.modul_durum_guncelle(musteri_id, donem, "m9_finansal",
                                  durum="bekliyor", ilerleme=0, bulgu_sayisi=0)
        return {"hazir": False}
    a = finansal_analiz.analiz(mizan)
    a["nakit_akis"] = _nakit_akis(musteri_id, donem, a)
    bulgu = a["kritik_sayisi"] + a["uyari_sayisi"]
    depo.modul_durum_guncelle(musteri_id, donem, "m9_finansal",
                              durum=("uyari" if bulgu else "tamam"),
                              ilerleme=100, bulgu_sayisi=bulgu)
    return {"hazir": True, "analiz": a, "kaynak": mizan.get("kaynak")}


def _donem_sonrasi(donem):
    """Projeksiyon baslangic gunu: donem sonu ertesi (bugun bundan onceyse bugun)."""
    try:
        y, ay = (int(x) for x in donem.split("-")[:2])
        son = calendar.monthrange(y, ay)[1]
        ds = date(y, ay, son)
        return max(ds, date.today())
    except Exception:
        return date.today()


def _nakit_akis(musteri_id, donem, a):
    """Senet/cek vadeleri + cari yaslandirmayi okuyup nakit projeksiyonu uretir.
    Senet 'm6_fis' rol=senet altinda, cari defteri 'm3_cari' rol=bizim altinda."""
    baslangic = a["bilanco"].get("hazir_degerler", 0) or 0
    senetler = []
    sen_yol = depo.yuklenen_bul(musteri_id, donem, "m6_fis", rol="senet")
    if sen_yol:
        try:
            senetler = varlik_oku.senet_oku(sen_yol)
        except Exception:
            senetler = []
    cari_yas = None
    biz_yol = depo.yuklenen_bul(musteri_id, donem, "m3_cari", rol="bizim")
    if biz_yol:
        try:
            cari_yas = cari_analiz.yaslandirma(cari_oku.oku(biz_yol), _donem_sonrasi(donem))
        except Exception:
            cari_yas = None
    return finansal_analiz.nakit_akis_ongoru(baslangic, senetler, cari_yas,
                                             _donem_sonrasi(donem))


# --------------------------------------------------------------------------- #
def _tl(v):
    try:
        return f"{v:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"


def _tl0(v):
    try:
        return f"{v:,.0f} TL".replace(",", ".")
    except Exception:
        return "—"


def _oran(v, ek=""):
    return "—" if v is None else f"{v:.2f}{ek}"


def _yuzde(v):
    if v is None:
        return '<span style="color:var(--text-muted)">—</span>'
    renk = "var(--accent-emerald)" if v >= 0 else "var(--accent-rose)"
    ok = "▲" if v >= 0 else "▼"
    return f'<span style="color:{renk}">{ok} %{abs(v):.1f}</span>'


SEV = {"kritik": ("err", "fa-triangle-exclamation", "Kritik"),
       "uyari": ("warn", "fa-circle-exclamation", "Uyarı"),
       "iyi": ("success", "fa-circle-check", "İyi")}


def _baslik():
    return f"""
    <div class="panel-header">
      <div class="panel-title"><h2><i class="fa-solid fa-chart-line"></i> {AD}</h2>
      <p>{ACIKLAMA}</p></div>
      <div class="panel-header-icon"><i class="fa-solid fa-chart-line"></i></div>
    </div>"""


def panel_html(sonuc):
    ust = _baslik()
    if not sonuc.get("hazir"):
        return (ust + '<div class="notif-pill"><div class="circle-icon-badge" '
                'style="background:var(--accent-gold)"></div><span>Önce <strong>Mizan & '
                'Anomali</strong> modülünden mizan yükleyin. Finansal analiz mizandan '
                'otomatik üretilir, ek dosya gerekmez.</span></div>')

    a = sonuc["analiz"]
    o = a["oranlar"]
    b = a["bilanco"]
    gt = a["gelir_tablosu"]

    # iki giris karti -> ayri sayfada rapor acar
    kartlar = """
    <div class="feature-grid" style="margin:18px 0;">
      <div class="feature-box" style="cursor:pointer;border:1px solid rgba(56,189,248,0.25);"
           onclick="window.open('/rapor'+location.search+'&tip=gelir','_blank')">
        <h3><i class="fa-solid fa-file-invoice-dollar" style="color:var(--accent-cyan)"></i> Gelir Tablosu</h3>
        <p>Brüt satıştan dönem kârına kademeli gelir tablosu, kâr marjları ve aylık satış/kâr trendi.
           <br><strong style="color:var(--accent-cyan)">Ayrı sayfada aç →</strong></p>
      </div>
      <div class="feature-box" style="cursor:pointer;border:1px solid rgba(52,211,153,0.25);"
           onclick="window.open('/rapor'+location.search+'&tip=bilanco','_blank')">
        <h3><i class="fa-solid fa-scale-balanced" style="color:var(--accent-emerald)"></i> Bilanço</h3>
        <p>Aktif/pasif yapısı, likidite ve kaldıraç oranları, dönem başına göre değişim.
           <br><strong style="color:var(--accent-emerald)">Ayrı sayfada aç →</strong></p>
      </div>
    </div>"""

    # ozet stat kartlari
    stat = f"""
    <div class="stats-grid" style="margin-bottom:8px;">
      <div class="stat-card"><div class="stat-header"><span>Net Satış (Dönem)</span><i class="fa-solid fa-sack-dollar" style="color:var(--accent-cyan)"></i></div><div class="stat-val" style="font-size:22px">{_tl0(gt['net_satis'])}</div></div>
      <div class="stat-card emerald"><div class="stat-header"><span>Dönem Kârı</span><i class="fa-solid fa-coins" style="color:var(--accent-emerald)"></i></div><div class="stat-val" style="font-size:22px">{_tl0(gt['donem_kari'])}</div><div class="stat-desc">Net marj {_oran(o['net_kar_marji']*100 if o['net_kar_marji'] is not None else None,'%')}</div></div>
      <div class="stat-card gold"><div class="stat-header"><span>Cari Oran</span><i class="fa-solid fa-droplet" style="color:var(--accent-gold)"></i></div><div class="stat-val">{_oran(o['cari_oran'])}</div><div class="stat-desc">Likidite</div></div>
      <div class="stat-card rose"><div class="stat-header"><span>Açık Risk</span><i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-rose)"></i></div><div class="stat-val">{a['kritik_sayisi']+a['uyari_sayisi']}</div><div class="stat-desc"><span class="rose">{a['kritik_sayisi']} kritik</span> · {a['uyari_sayisi']} uyarı</div></div>
    </div>"""

    altman = _altman_blok(a.get("altman"))
    nakit = _nakit_akis_blok(a.get("nakit_akis"))
    svg = _svg_trend_blok(a.get("aylik_trend", []), a.get("guncel_ay"))
    riskler = _risk_listesi(a["riskler"])

    return ust + kartlar + stat + altman + nakit + svg + riskler


# --------------------------------------------------------------------------- #
# ALTMAN Z'-SCORE GOSTERGESI
# --------------------------------------------------------------------------- #
_ZON_RENK = {"guvenli": "var(--accent-emerald)", "gri": "var(--accent-gold)",
             "riskli": "var(--accent-rose)"}


def _altman_blok(al):
    if not al or not al.get("hesaplanabilir"):
        return ('<div class="notif-pill" style="margin-top:16px"><div class="circle-icon-badge" '
                'style="background:var(--accent-gold)"></div><span><strong>Altman Z\'-Score</strong> '
                'hesaplanamadı — toplam aktif veya toplam borç sıfır/negatif.</span></div>')
    z = al["z"]
    renk = _ZON_RENK.get(al["zon"], "var(--text-muted)")
    # 0..6 araligini bar olarak goster; isaretci z konumunda
    oran = max(0.0, min(1.0, z / 6.0))
    bilesen = al["bilesenler"]
    bil_html = " · ".join(f"T{i}={bilesen[f'T{i}']:.2f}" for i in range(1, 6))
    return f"""
    <div style="margin-top:18px;padding:18px;border:1px solid {renk}55;border-radius:14px;background:rgba(7,10,19,0.35);">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
        <div>
          <h4 style="margin:0 0 4px;font-size:15px;"><i class="fa-solid fa-gauge-high" style="color:{renk}"></i>
            Altman Z'-Score <span style="color:var(--text-muted);font-weight:400;font-size:12px;">(özel sermayeli firma modeli)</span></h4>
          <p style="margin:0;font-size:12px;color:var(--text-muted);">{bil_html}</p>
        </div>
        <div style="text-align:right;">
          <div style="font-family:'Outfit',sans-serif;font-size:30px;font-weight:800;color:{renk};line-height:1;">{z:.2f}</div>
          <span class="badge {'success' if al['zon']=='guvenli' else ('warn' if al['zon']=='gri' else 'err')}">{al['etiket']}</span>
        </div>
      </div>
      <div style="position:relative;height:12px;border-radius:6px;margin-top:14px;
                  background:linear-gradient(90deg,var(--accent-rose) 0%,var(--accent-rose) 20.5%,var(--accent-gold) 20.5%,var(--accent-gold) 48.3%,var(--accent-emerald) 48.3%,var(--accent-emerald) 100%);">
        <div style="position:absolute;top:-4px;left:calc({oran*100:.1f}% - 2px);width:4px;height:20px;border-radius:2px;background:#fff;box-shadow:0 0 6px rgba(0,0,0,.6);"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--text-muted);margin-top:4px;">
        <span>0 — sıkıntı</span><span>1,23</span><span>2,9 — güvenli</span><span>6+</span>
      </div>
    </div>"""


# --------------------------------------------------------------------------- #
# NAKIT AKIS ONGORUSU BLOGU
# --------------------------------------------------------------------------- #
def _nakit_akis_blok(n):
    baslik = ('<h4 style="margin:18px 0 8px;font-size:15px;">'
              '<i class="fa-solid fa-money-bill-trend-up" style="color:var(--accent-cyan)"></i> '
              'Nakit Akış Öngörüsü <span style="color:var(--text-muted);font-weight:400;font-size:12px;">'
              '(senet/çek vadeleri — ileriye dönük likidite)</span></h4>')
    if not n or not n.get("hesaplanabilir"):
        return (baslik + '<div class="notif-pill"><div class="circle-icon-badge" '
                'style="background:var(--accent-gold)"></div><span>Projeksiyon için '
                '<strong>Fiş Üreticiler</strong> modülünden vadeli senet/çek listesi veya '
                '<strong>Cari Mutabakat</strong> modülünden bizim defteri yükleyin.</span></div>')

    def renk(v):
        return "var(--accent-emerald)" if v >= 0 else "var(--accent-rose)"

    satirlar = ""
    if n.get("senet_var"):
        for s in n["satirlar"]:
            if s["giris"] == 0 and s["cikis"] == 0:
                continue
            satirlar += (
                f'<tr><td>{s["etiket"]}</td>'
                f'<td style="text-align:right;color:var(--accent-emerald)">{_tl0(s["giris"]) if s["giris"] else "—"}</td>'
                f'<td style="text-align:right;color:var(--accent-rose)">{_tl0(s["cikis"]) if s["cikis"] else "—"}</td>'
                f'<td style="text-align:right;color:{renk(s["net"])}">{_tl0(s["net"])}</td>'
                f'<td style="text-align:right;font-weight:700;color:{renk(s["bakiye"])}">{_tl0(s["bakiye"])}</td></tr>')
    tablo = ""
    if satirlar:
        tablo = f"""
        <div style="overflow-x:auto;margin-top:6px;"><table>
          <tr><th>Vade Dönemi</th><th style="text-align:right">Giriş (alacak)</th>
              <th style="text-align:right">Çıkış (borç)</th><th style="text-align:right">Net</th>
              <th style="text-align:right">Tahmini Nakit</th></tr>
          <tr style="background:rgba(56,189,248,0.06);">
            <td><strong>Başlangıç Nakit</strong></td><td colspan="3"></td>
            <td style="text-align:right;font-weight:700">{_tl0(n["baslangic"])}</td></tr>
          {satirlar}
          <tr style="background:rgba(52,211,153,0.06);font-weight:700">
            <td>Dönem Toplamı</td>
            <td style="text-align:right;color:var(--accent-emerald)">{_tl0(n["toplam_giris"])}</td>
            <td style="text-align:right;color:var(--accent-rose)">{_tl0(n["toplam_cikis"])}</td>
            <td style="text-align:right;color:{renk(n["net"])}">{_tl0(n["net"])}</td>
            <td style="text-align:right;color:{renk(n["bitis"])}">{_tl0(n["bitis"])}</td></tr>
        </table></div>"""
    else:
        tablo = ('<div class="notif-pill" style="margin-top:6px;"><div class="circle-icon-badge"></div>'
                 '<span>Vadeli senet/çek bulunamadı — projeksiyon yalnızca cari pozisyon üzerinden.</span></div>')

    stat = f"""
    <div class="stats-grid" style="margin-top:10px;">
      <div class="stat-card"><div class="stat-header"><span>Başlangıç Nakit</span><i class="fa-solid fa-wallet" style="color:var(--accent-cyan)"></i></div><div class="stat-val" style="font-size:20px">{_tl0(n["baslangic"])}</div><div class="stat-desc">Kasa + Banka (10)</div></div>
      <div class="stat-card emerald"><div class="stat-header"><span>Beklenen Giriş</span><i class="fa-solid fa-arrow-down" style="color:var(--accent-emerald)"></i></div><div class="stat-val" style="font-size:20px">{_tl0(n["toplam_giris"])}</div><div class="stat-desc">Senet/çek alacak</div></div>
      <div class="stat-card rose"><div class="stat-header"><span>Beklenen Çıkış</span><i class="fa-solid fa-arrow-up" style="color:var(--accent-rose)"></i></div><div class="stat-val" style="font-size:20px">{_tl0(n["toplam_cikis"])}</div><div class="stat-desc">Senet/çek borç</div></div>
      <div class="stat-card gold"><div class="stat-header"><span>En Düşük Nakit</span><i class="fa-solid fa-chart-line-down" style="color:var(--accent-gold)"></i></div><div class="stat-val" style="font-size:20px;color:{renk(n["en_dusuk"])}">{_tl0(n["en_dusuk"])}</div><div class="stat-desc">Projeksiyon dip noktası</div></div>
    </div>"""

    cari_html = ""
    c = n.get("cari")
    if c:
        cari_html = (f'<div class="notif-pill" style="margin-top:10px;"><div class="circle-icon-badge"></div>'
                     f'<span>Ek bağlam (cari): açık alacak <strong>{_tl0(c["acik_alacak"])}</strong>'
                     f' · vadesi geçen <strong style="color:var(--accent-gold)">{_tl0(c["vadesi_gecen"])}</strong>'
                     f' — kesin vade içermediği için projeksiyona dahil edilmedi.</span></div>')

    uyari_html = ""
    for u in n.get("uyarilar", []):
        uyari_html += (f'<div class="notif-pill" style="margin-top:8px;"><div class="circle-icon-badge" '
                       f'style="background:var(--accent-rose)"></div><span>'
                       f'<span class="badge err"><i class="fa-solid fa-triangle-exclamation"></i> Likidite</span> '
                       f'{u}</span></div>')

    tatil_html = ""
    if n.get("tatil_kaymasi"):
        ek = (" Vade yılı resmî tatil takviminde tanımlı değil; dinî bayramlar hariç, "
              "sonuç yaklaşıktır." if n.get("tatil_yaklasik") else "")
        tatil_html = (f'<div class="notif-pill" style="margin-top:8px;"><div class="circle-icon-badge" '
                      f'style="background:var(--accent-cyan)"></div><span>'
                      f'<span class="badge"><i class="fa-solid fa-calendar-day"></i> Tatil takvimi</span> '
                      f'{n["tatil_kaymasi"]} senet/çek vadesi hafta sonu veya resmî tatile denk geldi; '
                      f'tahsilat/ödeme bir sonraki iş gününe kaydırılarak projeksiyona yansıtıldı.{ek}</span></div>')

    return baslik + stat + tablo + cari_html + tatil_html + uyari_html


# --------------------------------------------------------------------------- #
# SAF SVG AYLIK TREND GRAFIGI (sifir bagimlilik)
# --------------------------------------------------------------------------- #
def _svg_trend_blok(trend, guncel_ay=None):
    dolu = [t for t in trend if abs(t["net_satis"]) > 0.5 or abs(t["donem_kari"]) > 0.5]
    if len(dolu) < 2:
        return ""
    W, H = 720, 260
    ml, mr, mt, mb = 54, 16, 18, 34
    iw, ih = W - ml - mr, H - mt - mb
    seriler = [("net_satis", "Net Satış", "#38bdf8"), ("donem_kari", "Dönem Kârı", "#34d399")]
    tum = [t[k] for t in dolu for k, _, _ in seriler]
    vmax, vmin = max(tum), min(tum)
    if vmax == vmin:
        vmax += 1
    vmin = min(vmin, 0.0)   # sifir cizgisi gorunur olsun
    n = len(dolu)

    def x(i):
        return ml + (iw * i / (n - 1) if n > 1 else 0)

    def y(v):
        return mt + ih - (v - vmin) / (vmax - vmin) * ih

    def kisa(v):
        a = abs(v)
        if a >= 1e9: return f"{v/1e9:.1f}B".replace(".", ",")
        if a >= 1e6: return f"{v/1e6:.1f}M".replace(".", ",")
        if a >= 1e3: return f"{v/1e3:.0f}K"
        return f"{v:.0f}"

    parcalar = [f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="rgba(7,10,19,0.35)"/>']
    # yatay izgara + y etiket (4 seviye)
    for s in range(5):
        gv = vmin + (vmax - vmin) * s / 4
        gy = y(gv)
        parcalar.append(f'<line x1="{ml}" y1="{gy:.1f}" x2="{W-mr}" y2="{gy:.1f}" stroke="rgba(255,255,255,0.07)" stroke-width="1"/>')
        parcalar.append(f'<text x="{ml-6}" y="{gy+3:.1f}" text-anchor="end" font-size="9" fill="#7a8699">{kisa(gv)}</text>')
    # sifir cizgisi vurgusu
    if vmin < 0 < vmax:
        zy = y(0)
        parcalar.append(f'<line x1="{ml}" y1="{zy:.1f}" x2="{W-mr}" y2="{zy:.1f}" stroke="rgba(255,255,255,0.22)" stroke-width="1" stroke-dasharray="3 3"/>')
    # x etiketleri (ay)
    for i, t in enumerate(dolu):
        parcalar.append(f'<text x="{x(i):.1f}" y="{H-12}" text-anchor="middle" font-size="9" fill="#7a8699">{str(t["ay"])[:3].title()}</text>')
    # seriler
    for k, _, renk in seriler:
        pts = " ".join(f"{x(i):.1f},{y(t[k]):.1f}" for i, t in enumerate(dolu))
        parcalar.append(f'<polyline points="{pts}" fill="none" stroke="{renk}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
        for i, t in enumerate(dolu):
            parcalar.append(f'<circle cx="{x(i):.1f}" cy="{y(t[k]):.1f}" r="3" fill="{renk}"/>')
    svg = f'<svg viewBox="0 0 {W} {H}" width="100%" preserveAspectRatio="xMidYMid meet" style="display:block;">' + "".join(parcalar) + '</svg>'
    legend = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:18px;font-size:12px;color:var(--text-muted);">'
        f'<span style="width:12px;height:3px;background:{renk};display:inline-block;border-radius:2px;"></span>{et}</span>'
        for _, et, renk in seriler)
    return f"""
    <div style="margin-top:18px;">
      <h4 style="margin:0 0 8px;font-size:15px;"><i class="fa-solid fa-chart-line" style="color:var(--accent-cyan)"></i>
        Aylık Net Satış &amp; Dönem Kârı Trendi</h4>
      <div>{legend}</div>
      <div style="margin-top:6px;border:1px solid rgba(255,255,255,0.08);border-radius:12px;overflow:hidden;">{svg}</div>
    </div>"""


def _risk_listesi(rsk):
    satir = ""
    for x in rsk:
        rozet, ikon, et = SEV.get(x["seviye"], ("neutral", "fa-circle", ""))
        satir += (f'<div class="notif-pill" style="margin-bottom:8px;">'
                  f'<div class="circle-icon-badge" style="background:var(--accent-{"rose" if x["seviye"]=="kritik" else ("gold" if x["seviye"]=="uyari" else "emerald")})"></div>'
                  f'<span><span class="badge {rozet}"><i class="fa-solid {ikon}"></i> {et}</span> '
                  f'<strong>{x["baslik"]}</strong> — {x["mesaj"]}</span></div>')
    return (f'<h4 style="margin:18px 0 10px;font-size:15px;"><i class="fa-solid fa-shield-halved"></i> '
            f'Finansal & Operasyonel Risk Tablosu</h4>{satir}')


# --------------------------------------------------------------------------- #
# AYRI SAYFA RAPORLARI
# --------------------------------------------------------------------------- #
def _gt_satir(ad, deger, kalin=False, ara=False):
    st = "font-weight:700;" if kalin else ""
    bg = 'background:rgba(56,189,248,0.06);' if ara else ""
    return (f'<tr style="{bg}"><td style="{st}">{ad}</td>'
            f'<td style="text-align:right;{st}">{_tl(deger)}</td></tr>')


def _rapor_gelir(a):
    gt = a["gelir_tablosu"]
    o = a["oranlar"]
    tablo = "".join([
        _gt_satir("Brüt Satışlar", gt["brut_satis"]),
        _gt_satir("(−) Satış İndirimleri", -gt["satis_ind"]),
        _gt_satir("= NET SATIŞLAR", gt["net_satis"], kalin=True, ara=True),
        _gt_satir("(−) Satışların Maliyeti (SMM)", -gt["smm"]),
        _gt_satir("= BRÜT SATIŞ KÂRI", gt["brut_kar"], kalin=True, ara=True),
        _gt_satir("(−) Faaliyet Giderleri", -gt["faal_gid"]),
        _gt_satir("= FAALİYET KÂRI", gt["faaliyet_kari"], kalin=True, ara=True),
        _gt_satir("(+) Diğer Faaliyet Gelirleri", gt["diger_gel"]),
        _gt_satir("(−) Diğer Faaliyet Giderleri", -gt["diger_gid"]),
        _gt_satir("(−) Finansman Giderleri", -gt["finansman"]),
        _gt_satir("= OLAĞAN KÂR", gt["olagan_kar"], kalin=True, ara=True),
        _gt_satir("(+) Olağandışı Gelirler", gt["olagandisi_gel"]),
        _gt_satir("(−) Olağandışı Giderler", -gt["olagandisi_gid"]),
        _gt_satir("= DÖNEM KÂRI / ZARARI", gt["donem_kari"], kalin=True, ara=True),
    ])

    marj = f"""
    <div class="stats-grid" style="margin:18px 0;">
      <div class="stat-card"><div class="stat-header"><span>Brüt Kâr Marjı</span></div><div class="stat-val">{_oran(o['brut_kar_marji']*100 if o['brut_kar_marji'] is not None else None,'%')}</div></div>
      <div class="stat-card"><div class="stat-header"><span>Faaliyet Kâr Marjı</span></div><div class="stat-val">{_oran(o['faaliyet_kar_marji']*100 if o['faaliyet_kar_marji'] is not None else None,'%')}</div></div>
      <div class="stat-card"><div class="stat-header"><span>Net Kâr Marjı</span></div><div class="stat-val">{_oran(o['net_kar_marji']*100 if o['net_kar_marji'] is not None else None,'%')}</div></div>
    </div>"""

    # aylik trend tablosu
    trend = a["aylik_trend"]
    dolu = [t for t in trend if abs(t["net_satis"]) > 0.5 or abs(t["donem_kari"]) > 0.5]
    trend_html = ""
    if dolu:
        sat = "".join(
            f'<tr><td>{t["ay"].title()}</td><td style="text-align:right">{_tl0(t["net_satis"])}</td>'
            f'<td style="text-align:right">{_tl0(t["brut_kar"])}</td>'
            f'<td style="text-align:right">{_tl0(t["donem_kari"])}</td></tr>'
            for t in dolu)
        trend_html = f"""
        <h3 style="margin-top:26px"><i class="fa-solid fa-chart-column"></i> Aylık Trend (Net Hareket)</h3>
        <div style="overflow-x:auto"><table>
          <tr><th>Ay</th><th style="text-align:right">Net Satış</th><th style="text-align:right">Brüt Kâr</th><th style="text-align:right">Dönem Kârı</th></tr>
          {sat}
        </table></div>"""

    kiyas_html = ""
    k = a["ay_kiyas"]
    if k:
        kiyas_html = f"""
        <div class="notif-pill" style="margin-top:16px">
          <div class="circle-icon-badge" style="background:var(--accent-cyan)"></div>
          <span><strong>{k['son_ay'].title()}</strong> ayı net satışı {_tl0(k['son_satis'])} —
          önceki ayların ortalamasına ({_tl0(k['ort_satis'])}) göre {_yuzde(k['satis_yuzde'])};
          dönem kârı {_yuzde(k['kar_yuzde'])}.</span>
        </div>"""

    return f"""
    <h2><i class="fa-solid fa-file-invoice-dollar"></i> Gelir Tablosu — Dönem (Kümüle)</h2>
    {marj}
    <div style="overflow-x:auto"><table>
      <tr><th>Kalem</th><th style="text-align:right">Tutar</th></tr>
      {tablo}
    </table></div>
    {kiyas_html}
    {_svg_trend_blok(a.get('aylik_trend', []), a.get('guncel_ay'))}
    {trend_html}
    {_risk_listesi([r for r in a['riskler'] if r['seviye']!='iyi'] or a['riskler'])}
    """


def _bil_satir(ad, k, kalin=False):
    """k = bilanco_karsilastir[anahtar]."""
    st = "font-weight:700;" if kalin else ""
    return (f'<tr><td style="{st}">{ad}</td>'
            f'<td style="text-align:right;{st}">{_tl0(k["guncel"])}</td>'
            f'<td style="text-align:right">{_tl0(k["acilis"])}</td>'
            f'<td style="text-align:right">{_yuzde(k["yuzde"])}</td></tr>')


def _rapor_bilanco(a):
    b = a["bilanco"]
    o = a["oranlar"]
    kk = a["bilanco_karsilastir"]

    aktif = f"""
    <h3 style="margin-top:18px"><i class="fa-solid fa-arrow-up-right-dots"></i> AKTİF (Varlıklar)</h3>
    <div style="overflow-x:auto"><table>
      <tr><th>Kalem</th><th style="text-align:right">Güncel</th><th style="text-align:right">Dönem Başı</th><th style="text-align:right">Değişim</th></tr>
      {_bil_satir("Dönen Varlıklar", kk["donen"], kalin=True)}
      <tr><td style="padding-left:22px;color:var(--text-muted)">· Hazır Değerler</td><td style="text-align:right">{_tl0(b['hazir_degerler'])}</td><td colspan="2"></td></tr>
      <tr><td style="padding-left:22px;color:var(--text-muted)">· Ticari Alacaklar</td><td style="text-align:right">{_tl0(b['ticari_alacak'])}</td><td colspan="2"></td></tr>
      <tr><td style="padding-left:22px;color:var(--text-muted)">· Stoklar</td><td style="text-align:right">{_tl0(b['stok'])}</td><td colspan="2"></td></tr>
      {_bil_satir("Duran Varlıklar", kk["duran"], kalin=True)}
      <tr style="background:rgba(56,189,248,0.06);font-weight:700"><td>TOPLAM AKTİF</td><td style="text-align:right">{_tl0(kk['aktif']['guncel'])}</td><td style="text-align:right">{_tl0(kk['aktif']['acilis'])}</td><td style="text-align:right">{_yuzde(kk['aktif']['yuzde'])}</td></tr>
    </table></div>"""

    pasif = f"""
    <h3 style="margin-top:22px"><i class="fa-solid fa-arrow-down-wide-short"></i> PASİF (Kaynaklar)</h3>
    <div style="overflow-x:auto"><table>
      <tr><th>Kalem</th><th style="text-align:right">Güncel</th><th style="text-align:right">Dönem Başı</th><th style="text-align:right">Değişim</th></tr>
      {_bil_satir("Kısa Vadeli Yab. Kaynaklar", kk["kv_yk"], kalin=True)}
      <tr><td style="padding-left:22px;color:var(--text-muted)">· Ticari Borçlar</td><td style="text-align:right">{_tl0(b['ticari_borc'])}</td><td colspan="2"></td></tr>
      <tr><td style="padding-left:22px;color:var(--text-muted)">· Ödenecek Vergi/SGK</td><td style="text-align:right">{_tl0(b['odenecek_vergi'])}</td><td colspan="2"></td></tr>
      {_bil_satir("Uzun Vadeli Yab. Kaynaklar", kk["uv_yk"], kalin=True)}
      {_bil_satir("Özkaynaklar", kk["ozkaynak"], kalin=True)}
      <tr><td style="padding-left:22px;color:var(--text-muted)">· Ödenmiş Sermaye</td><td style="text-align:right">{_tl0(b['sermaye'])}</td><td colspan="2"></td></tr>
      <tr><td style="padding-left:22px;color:var(--text-muted)">· Dönem Net Kârı/Zararı</td><td style="text-align:right">{_tl0(b.get('donem_kari',0))}</td><td colspan="2"></td></tr>
      <tr style="background:rgba(52,211,153,0.06);font-weight:700"><td>TOPLAM PASİF</td><td style="text-align:right">{_tl0(b['pasif'])}</td><td colspan="2"></td></tr>
    </table></div>"""

    oranlar_html = f"""
    <h3 style="margin-top:22px"><i class="fa-solid fa-gauge"></i> Finansal Oranlar</h3>
    <div class="stats-grid" style="margin-top:10px">
      <div class="stat-card"><div class="stat-header"><span>Cari Oran</span></div><div class="stat-val">{_oran(o['cari_oran'])}</div><div class="stat-desc">İdeal ≥ 1,5</div></div>
      <div class="stat-card"><div class="stat-header"><span>Asit-Test</span></div><div class="stat-val">{_oran(o['asit_test'])}</div><div class="stat-desc">İdeal ≥ 1,0</div></div>
      <div class="stat-card"><div class="stat-header"><span>Nakit Oran</span></div><div class="stat-val">{_oran(o['nakit_oran'])}</div><div class="stat-desc">İdeal ≥ 0,20</div></div>
      <div class="stat-card gold"><div class="stat-header"><span>Borç / Özkaynak</span></div><div class="stat-val">{_oran(o['borc_ozkaynak'])}</div><div class="stat-desc">Düşük = sağlam</div></div>
      <div class="stat-card"><div class="stat-header"><span>Özkaynak / Aktif</span></div><div class="stat-val">{_oran(o['ozkaynak_aktif']*100 if o['ozkaynak_aktif'] is not None else None,'%')}</div></div>
      <div class="stat-card"><div class="stat-header"><span>Net İşletme Sermayesi</span></div><div class="stat-val" style="font-size:20px">{_tl0(o['net_isletme_sermayesi'])}</div></div>
    </div>"""

    denge = ""
    if abs(b["denge_farki"]) > 1:
        denge = (f'<div class="notif-pill" style="margin-top:14px"><div class="circle-icon-badge" '
                 f'style="background:var(--accent-gold)"></div><span>Aktif-Pasif farkı '
                 f'<strong>{_tl0(b["denge_farki"])}</strong> — mizanda denkleşmeyen kayıt olabilir.</span></div>')

    return f"""
    <h2><i class="fa-solid fa-scale-balanced"></i> Bilanço — Dönem Karşılaştırmalı</h2>
    {aktif}{pasif}{denge}{oranlar_html}
    {_altman_blok(a.get("altman"))}
    {_nakit_akis_blok(a.get("nakit_akis"))}
    {_risk_listesi([r for r in a['riskler'] if r['seviye']!='iyi'] or a['riskler'])}
    """


def rapor_govde(sonuc, tip):
    if not sonuc.get("hazir"):
        return ('<div class="notif-pill"><div class="circle-icon-badge" '
                'style="background:var(--accent-gold)"></div><span>Mizan bulunamadı. '
                'Önce Mizan & Anomali modülünden mizan yükleyin.</span></div>')
    a = sonuc["analiz"]
    if tip == "gelir":
        return _rapor_gelir(a)
    return _rapor_bilanco(a)


kaydet(Modul("m9_finansal", AD, "fa-chart-line", 10, calistir, panel_html))
