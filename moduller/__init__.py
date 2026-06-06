# -*- coding: utf-8 -*-
"""Kapanis modulleri paketi. Her dosya kendini core.moduller'a kaydeder."""


def kayitli_yukle():
    # Import siralamasi onemsiz; her modul sira alanina gore dizilir.
    from . import m2_mizan        # noqa: F401
    from . import m3_cari         # noqa: F401
    from . import m4_gib_kdv      # noqa: F401
    from . import m5_banka        # noqa: F401
    from . import m13_stok        # noqa: F401
    from . import m12_bordro      # noqa: F401
    from . import m11_beyan       # noqa: F401
    # Enflasyon muhasebesi bu yil kullanilmiyor -> arsivlendi (dosyalar duruyor).
    # Ihtiyac olursa asagidaki satiri ac; sira=8 slotu gecici vergiye verildi.
    # from . import m10_enflasyon   # noqa: F401  (ARSIV)
    from . import m10_gecici_vergi  # noqa: F401
    from . import m6_fis          # noqa: F401
    from . import m9_finansal     # noqa: F401
    from . import m7_eksik        # noqa: F401
    from . import m8_dosya        # noqa: F401


def placeholder_panel(ad, aciklama, ozellikler):
    """Asama 0: modul ici henuz bos. Yapilacaklari gosteren panel."""
    satirlar = "".join(
        f'<div class="feature-box"><h3><i class="fa-solid fa-circle-dot" '
        f'style="color:var(--accent-cyan)"></i> {b}</h3><p>{a}</p></div>'
        for b, a in ozellikler
    )
    return f"""
    <div class="panel-header">
      <div class="panel-title">
        <h2>{ad}</h2>
        <p>{aciklama}</p>
      </div>
      <div class="panel-header-icon"><i class="fa-solid fa-helmet-safety"></i></div>
    </div>
    <div class="notif-pill" style="margin-bottom:20px;">
      <div class="circle-icon-badge"></div>
      <span>Bu modul yapim asamasinda — sonraki asamada devreye girecek</span>
    </div>
    <div class="feature-grid">{satirlar}</div>
    """
