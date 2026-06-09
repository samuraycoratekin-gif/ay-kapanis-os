# -*- coding: utf-8 -*-
"""
Mutabakat formu + durum takip katmani (prototip).

Akis:
  1) Motor her cari icin bakiye + bulgu uretir, baslangic durumu = TASLAK.
  2) Her cari icin karsi tarafa gidecek bir MUTABAKAT FORMU (HTML) uretilir.
       - bizim bakiye + karsinin bakiyesi yan yana
       - iki buton: "Mutabikiz" / "Mutabik Degiliz"
  3) Karsi taraf butona basinca yanit kaydedilir (kaydet_yanit).
       - "MUTABIK"  -> bizim ekranimiza yesil dusar, kilitlenir
       - "ITIRAZLI" -> motoru tetikler (fark analizi)
  4) Bizim TAKIP EKRANIMIZ (dashboard HTML) tum carilerin guncel durumunu gosterir.

Durum deposu: Mutabakat_AI/mutabakat_durum.json
Bu prototipte karsi tarafin tikladigi simule edilir; uretimde formdaki butonlar
bir backend'e POST eder, ayni kaydet_yanit() cagrilir.
"""
import os, json, html
from . import motor as m

KLASOR = "Mutabakat_AI"
DURUM_DOSYA = os.path.join(KLASOR, "mutabakat_durum.json")
FORM_KLASOR = os.path.join(KLASOR, "formlar")
DASHBOARD = os.path.join(KLASOR, "bizim_ekran.html")

DURUMLAR = {
    "TASLAK":     ("#9aa0a6", "Taslak"),
    "GONDERILDI": ("#1a73e8", "Gonderildi - yanit bekleniyor"),
    "MUTABIK":    ("#188038", "MUTABIK"),
    "ITIRAZLI":   ("#d93025", "Mutabik Degil - itiraz var"),
}


# --------------------------------------------------------------------------- #
def bakiye(satirlar):
    """Cari net bakiye = toplam FATURA - toplam ODEME (tedarikci perspektifi)."""
    fat = sum(float(r["tutar"]) for r in satirlar if r["tip"] == "FATURA")
    ode = sum(float(r["tutar"]) for r in satirlar if r["tip"] == "ODEME")
    return round(fat - ode, 2)


def cari_analiz(bz=None, kr=None):
    """Her cari icin: ad, bakiyeler, durum-onerisi, bulgular."""
    bz = bz or os.path.join(KLASOR, "bizim_ekstreler.xlsx")
    kr = kr or os.path.join(KLASOR, "karsi_ekstreler.xlsx")
    bizim = m.grupla(m.oku(bz))
    karsi = m.grupla(m.oku(kr))
    cariler = sorted(set(bizim) | set(karsi))
    cikti = {}
    for ck in cariler:
        b_rows, k_rows = bizim.get(ck, []), karsi.get(ck, [])
        adi = (b_rows or k_rows)[0]["cari_adi"]
        bulgular = m.cari_esle([dict(r) for r in b_rows], [dict(r) for r in k_rows])
        cikti[ck] = {
            "cari_adi": adi,
            "bizim_bakiye": bakiye(b_rows),
            "karsi_bakiye": bakiye(k_rows),
            "motor_durum": m.cari_durum(bulgular),   # MUTABIK / TUTAR FARKLI / EKSIK BELGE
            "tahmini_acik": m.fark_tutari(bulgular),
            "bulgular": [(t, ac) for t, _, _, ac in bulgular],
        }
    return cikti


# --------------------------------------------------------------------------- #
# Durum deposu
# --------------------------------------------------------------------------- #
def durum_yukle():
    if os.path.exists(DURUM_DOSYA):
        with open(DURUM_DOSYA, encoding="utf-8") as f:
            return json.load(f)
    return {}


def durum_kaydet(d):
    with open(DURUM_DOSYA, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def durum_baslat(analiz):
    """Henuz durumu olmayan carileri TASLAK olarak ekler."""
    d = durum_yukle()
    for ck, a in analiz.items():
        if ck not in d:
            d[ck] = {"durum": "TASLAK", "yanit_notu": "", "karsi_bakiye_beyani": None}
    durum_kaydet(d)
    return d


def gonder(ck):
    d = durum_yukle()
    d[ck]["durum"] = "GONDERILDI"
    durum_kaydet(d)


def kaydet_yanit(ck, secim, not_="", beyan=None):
    """Karsi tarafin form yaniti. secim: 'MUTABIK' | 'ITIRAZLI'."""
    d = durum_yukle()
    d[ck]["durum"] = secim
    d[ck]["yanit_notu"] = not_
    d[ck]["karsi_bakiye_beyani"] = beyan
    durum_kaydet(d)
    return d[ck]


# --------------------------------------------------------------------------- #
# Form HTML (karsi tarafa giden)
# --------------------------------------------------------------------------- #
FORM_SABLON = """<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mutabakat Formu - {adi}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;background:#f1f3f4;margin:0;padding:24px;color:#202124}}
.kart{{max-width:560px;margin:0 auto;background:#fff;border-radius:12px;
  box-shadow:0 1px 4px rgba(0,0,0,.15);overflow:hidden}}
.bas{{background:#1a73e8;color:#fff;padding:20px 24px}}
.bas h1{{font-size:18px;margin:0}}.bas p{{margin:6px 0 0;opacity:.9;font-size:13px}}
.govde{{padding:24px}}
.bakiye{{display:flex;gap:12px;margin:8px 0 20px}}
.bk{{flex:1;border:1px solid #e0e0e0;border-radius:8px;padding:14px;text-align:center}}
.bk small{{color:#5f6368;font-size:12px}}.bk b{{display:block;font-size:20px;margin-top:6px}}
.fark{{text-align:center;padding:10px;border-radius:8px;margin-bottom:20px;font-size:14px}}
.fark.ok{{background:#e6f4ea;color:#188038}}.fark.no{{background:#fce8e6;color:#d93025}}
.butonlar{{display:flex;gap:12px}}
button{{flex:1;padding:14px;border:0;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer}}
.evet{{background:#188038;color:#fff}}.hayir{{background:#fff;color:#d93025;border:2px solid #d93025}}
.dipnot{{margin-top:18px;font-size:12px;color:#5f6368;text-align:center}}
#sonuc{{margin-top:16px;padding:12px;border-radius:8px;display:none;font-size:14px;text-align:center}}
</style></head><body>
<div class="kart">
  <div class="bas"><h1>Cari Hesap Mutabakat Formu</h1>
    <p>{firma} &middot; Donem: {donem}</p></div>
  <div class="govde">
    <p><b>{adi}</b> ({ck}) ile cari hesap mutabakati:</p>
    <div class="bakiye">
      <div class="bk"><small>Bizim kayitlarimizda</small><b>{biz_bakiye} TL</b></div>
      <div class="bk"><small>Sizin bakiyeniz</small><b>{karsi_bakiye} TL</b></div>
    </div>
    <div class="fark {fark_sinif}">{fark_metni}</div>
    <div class="butonlar">
      <button class="evet" onclick="yanitla('MUTABIK')">Mutabikiz</button>
      <button class="hayir" onclick="yanitla('ITIRAZLI')">Mutabik Degiliz</button>
    </div>
    <div id="sonuc"></div>
    <p class="dipnot">Yanitiniz dogrudan gonderen firmanin mutabakat ekranina dusecektir.</p>
  </div>
</div>
<script>
function yanitla(secim){{
  var s=document.getElementById('sonuc');s.style.display='block';
  if(secim==='MUTABIK'){{s.style.background='#e6f4ea';s.style.color='#188038';
    s.innerHTML='Tesekkurler. <b>Mutabikiz</b> olarak kaydedildi ve karsi tarafa iletildi.';}}
  else{{s.style.background='#fce8e6';s.style.color='#d93025';
    s.innerHTML='<b>Mutabik degiliz</b> kaydedildi. Lutfen kendi cari ekstrenizi ekleyin; '
      +'sistem farki otomatik analiz edecek.';}}
  localStorage.setItem('mutabakat_{ck}',secim);
  /* Uretimde: fetch('/api/yanit',{{method:'POST',body:JSON.stringify(...)}}) */
}}
</script></body></html>"""


def form_uret(analiz, firma="ORNEK SANAYI A.S.", donem="Mayis 2026"):
    os.makedirs(FORM_KLASOR, exist_ok=True)
    for ck, a in analiz.items():
        esit = abs(a["bizim_bakiye"] - a["karsi_bakiye"]) <= 0.01
        if esit:
            fark_sinif, fark_metni = "ok", "Bakiyeler birebir ortusuyor."
        else:
            fark = round(a["bizim_bakiye"] - a["karsi_bakiye"], 2)
            fark_sinif = "no"
            fark_metni = f"Bakiyeler arasinda {abs(fark):.2f} TL fark var (motor: {a['motor_durum']})."
        dosya = os.path.join(FORM_KLASOR, f"form_{ck.replace('.', '_')}.html")
        with open(dosya, "w", encoding="utf-8") as f:
            f.write(FORM_SABLON.format(
                adi=html.escape(a["cari_adi"]), ck=ck, firma=firma, donem=donem,
                biz_bakiye=f"{a['bizim_bakiye']:,.2f}",
                karsi_bakiye=f"{a['karsi_bakiye']:,.2f}",
                fark_sinif=fark_sinif, fark_metni=fark_metni))


# --------------------------------------------------------------------------- #
# Bizim takip ekranimiz (dashboard)
# --------------------------------------------------------------------------- #
def dashboard_uret(analiz):
    d = durum_yukle()
    satirlar = []
    sayac = {}
    for ck, a in analiz.items():
        durum = d.get(ck, {}).get("durum", "TASLAK")
        sayac[durum] = sayac.get(durum, 0) + 1
        renk, etiket = DURUMLAR[durum]
        kilit = " 🔒" if durum == "MUTABIK" else ""
        not_ = d.get(ck, {}).get("yanit_notu", "")
        satirlar.append(f"""<tr>
          <td>{ck}</td><td>{html.escape(a['cari_adi'])}</td>
          <td style="text-align:right">{a['bizim_bakiye']:,.2f}</td>
          <td style="text-align:right">{a['karsi_bakiye']:,.2f}</td>
          <td><span class="rozet" style="background:{renk}">{etiket}{kilit}</span></td>
          <td style="font-size:12px;color:#5f6368">{html.escape(not_)}</td></tr>""")
    ozet = " &nbsp; ".join(f"<b style='color:{DURUMLAR[k][0]}'>{v}</b> {DURUMLAR[k][1]}"
                           for k, v in sorted(sayac.items()))
    html_str = f"""<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<title>Mutabakat Takip Ekrani</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;background:#f8f9fa;margin:0;padding:24px;color:#202124}}
h1{{font-size:20px}}.ozet{{margin:8px 0 18px;font-size:14px}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:10px;overflow:hidden;
  box-shadow:0 1px 3px rgba(0,0,0,.12)}}
th,td{{padding:11px 14px;border-bottom:1px solid #eee;font-size:14px;text-align:left}}
th{{background:#f1f3f4;color:#5f6368;font-weight:600}}
.rozet{{color:#fff;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600;white-space:nowrap}}
</style></head><body>
<h1>Mutabakat Takip Ekrani &mdash; Mayis 2026</h1>
<div class="ozet">{ozet}</div>
<table><thead><tr><th>Cari</th><th>Unvan</th><th>Bizim Bakiye</th>
<th>Karsi Bakiye</th><th>Durum</th><th>Not</th></tr></thead>
<tbody>{''.join(satirlar)}</tbody></table>
<p style="margin-top:14px;font-size:12px;color:#5f6368">
Karsi taraf formda "Mutabikiz" isaretledikce ilgili satir yesil <b>MUTABIK</b> olur ve kilitlenir.</p>
</body></html>"""
    with open(DASHBOARD, "w", encoding="utf-8") as f:
        f.write(html_str)


# --------------------------------------------------------------------------- #
def main():
    analiz = cari_analiz()
    durum_baslat(analiz)
    form_uret(analiz)

    # --- Simulasyon: karsi taraflar formu acip yanitliyor ---
    for ck in analiz:
        gonder(ck)
    # Bakiyesi tutan cariler "Mutabikiz" tikliyor:
    for ck, a in analiz.items():
        if abs(a["bizim_bakiye"] - a["karsi_bakiye"]) <= 0.01:
            kaydet_yanit(ck, "MUTABIK")
        else:
            kaydet_yanit(ck, "ITIRAZLI",
                         not_="Bizde bu tutar/fatura yok, ekstremiz ekte.",
                         beyan=a["karsi_bakiye"])

    dashboard_uret(analiz)

    # Konsol ozeti
    d = durum_yukle()
    print("FORM DONGUSU SONUCU")
    print("-" * 62)
    for ck, a in analiz.items():
        print(f"  {ck} {a['cari_adi'][:26]:<26} "
              f"biz={a['bizim_bakiye']:>10,.2f}  karsi={a['karsi_bakiye']:>10,.2f}  "
              f"-> {DURUMLAR[d[ck]['durum']][1]}")
    print("-" * 62)
    print(f"  Formlar      : {FORM_KLASOR}\\form_*.html")
    print(f"  Bizim ekran  : {DASHBOARD}")
    print(f"  Durum deposu : {DURUM_DOSYA}")


if __name__ == "__main__":
    main()
