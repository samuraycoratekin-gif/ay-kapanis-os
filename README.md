# Ay Kapanış OS

Ay sonu muhasebe kapanışı otomasyonu. Çok-kiracılı (multi-tenant) web uygulaması:
her ofis/şirket kendi izole alanında çalışır, verisi birbirine karışmaz.

Saf Python `http.server` (ThreadingHTTPServer) — hafif, framework yok. Veri JSON
dosyalarında tutulur; bulutta kalıcı disk (Volume) ile saklanır.

## Yerelde çalıştırma

```
python app.py
```

`baslat.bat` (Windows) aynısını yapar ve tarayıcıyı açar. Varsayılan port 5050.

Yerel giriş bilgileri (yalnızca geliştirme):

| Rol | E-posta | Parola | Adres |
|-----|---------|--------|-------|
| Platform sahibi | `patron@aykapanis.local` | `patron1234` | `/yonetim` |
| Varsayılan kiracı | `ofis@aykapanis.local` | `1234` | `/` |

## Yetki katmanları

1. **Platform sahibi** (sağlayıcı) — kiracıları (ofis/şirket) oluşturur, parola
   tanımlar, aktif/pasif yapar. `/yonetim` ekranı. Kiracı verisine erişemez.
2. **Ofis Yöneticisi** — kiracı içinde personel ve ayarları yönetir, onay/kilit.
3. **Muhasebe Müdürü** — onay/gönder/kilit.
4. **Muhasebe Elemanı** — yalnızca taslak üretir.

Yeni bir kiracı ilk girişinde **boş** başlar ve kurulum sihirbazına (`/kurulum`)
düşer: ofis adı + ilk yönetici + kullandığı muhasebe programı (ERP).

## Ortam değişkenleri (Railway / bulut)

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `PORT` | Railway otomatik verir | Dinlenecek port; varken `0.0.0.0`'a bağlanır. |
| `VERI_DIR` | **Evet (bulutta)** | Kalıcı disk yolu (Volume mount). Örn. `/data`. Ayarlanmazsa veri her deploy'da uçar. |
| `PLATFORM_EPOSTA` | Önerilir | Platform sahibi giriş e-postası. |
| `PLATFORM_PAROLA` | **Evet (bulutta)** | Platform sahibi parolası. Varsayılan yalnızca yereldedir; canlıda mutlaka değiştirin. |
| `GIRIS_PAROLASI` | Önerilir | İlk varsayılan kiracının seed parolası. |
| `VARSAYILAN_EPOSTA` | Hayır | İlk varsayılan kiracının e-postası (varsayılan `ofis@aykapanis.local`). |

> **Güvenlik:** Parolalar pbkdf2-sha256 ile hash'lenir; düz parola hiçbir yerde
> saklanmaz. Gerçek müşteri verisi (`veri/`) `.gitignore` ile repodan dışlanır.

## Railway'e dağıtım (özet)

1. Repoyu GitHub'a push edin.
2. Railway'de **New Project → Deploy from GitHub repo** ile bu repoyu seçin.
   `Procfile` (`web: python app.py`) ve `requirements.txt` otomatik algılanır.
3. **Variables** sekmesinden yukarıdaki env değişkenlerini girin
   (`PLATFORM_PAROLA`, `GIRIS_PAROLASI`, `VERI_DIR=/data`).
4. **Volume** ekleyin ve mount yolunu `VERI_DIR` ile aynı yapın (`/data`).
5. Deploy sonrası verilen URL'de `/giris` ile açılır.

## Bağımlılıklar

`openpyxl`, `xlrd` (Excel okuma). Geri kalan her şey Python standart kütüphanesi.
Akıllı Mutabakat (Mutabakat_AI) entegrasyonu opsiyoneldir; yoksa devre dışı kalır.
