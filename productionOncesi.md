# Production Oncesi Kontrol ve Tarama Notlari

Olusturma tarihi: 2026-02-21

## 1) Hizli Tarama Ozeti

### Proje ve stack
- Framework: Django 5.x (`requirements.txt`)
- Dil: Python
- DB: Development SQLite, Production PostgreSQL (`personmeter/settings_base.py`, `personmeter/settings_production.py`)
- Dosya depolama: Production'da AWS S3 zorunlu (`personmeter/settings_production.py`)
- UI: Bootstrap 5 (`core/templates/core/base.html`)

### Runtime secimi
- Ortam secimi `PERSONMETER_ENV` ile yapiliyor (`personmeter/settings.py`).
- `production` secilirse `settings_production.py` yukleniyor.

### Mevcut kalite durumu (lokalde calistirildi)
- `python manage.py check` -> sorunsuz
- `python manage.py test` -> 14 test, hepsi gecti

## 2) Tarama Sonucu Kritik Noktalar

### Kritik (go-live oncesi cozulmeli)
1. Upload validasyonu eksik:
- `PersonForm` tarafinda dosya tipi/boyut limiti yok (`core/forms.py`).
- `compress_image` dogrudan `Image.open` yapiyor; bozuk/buyuk dosyada 500 riski var (`core/models.py`).

2. Production static servis plani net degil:
- Projede `Dockerfile`/`Procfile` yok, `gunicorn` dependency yok (`requirements.txt`).
- `DEBUG=False` durumda static dosyalar Django tarafindan servis edilmez; WhiteNoise/Nginx stratejisi gerekli.

3. Production settings AWS'e bagimli:
- `settings_production.py` AWS env degiskenlerini zorunlu bekliyor.
- AWS'den cikilacaksa (veya bucket erisimi degisecekse) deploy fail eder.

### Yuksek oncelik
1. Security baseline sertlestirme eksikleri:
- `settings_base.py` icinde default/fallback `SECRET_KEY` var (production import'unda override edilse de yanlis env ile riskli).
- `SECURE_SSL_REDIRECT`, HSTS ve security header ayarlari tanimli degil.

2. Performans riski:
- `home` ve `search` gorunumlerinde yogun annotate/filter yapisi var (`core/views.py`).
- `tags__icontains` zinciri buyuk veri setinde yavaslayabilir.

3. Bakim maliyeti:
- `User` icin iki `post_save` sinyali cift yazim/karmasiklik yaratabilir (`core/signals.py`).

## 3) Coolify + 4GB VPS Icin Production Oncesi Yapilacaklar

## A. Erisim ve devir teslim
- AWS tarafindan su bilgileri teslim al:
  - Domain/DNS panel erisimi
  - S3 bucket erisimi ve IAM key'leri
  - Varsa eski PostgreSQL dump/backup
  - SSL sertifika/yonlendirme bilgisi
- Yeni sorumlu oldugun icin tum gizli anahtarlari rotasyon et:
  - `DJANGO_SECRET_KEY`
  - `DB_PASSWORD`
  - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`

## B. Coolify uygulama tanimi
- App type: Python (veya Dockerfile tabanli, eger sonradan eklenecekse).
- Build command:
```bash
pip install -r requirements.txt
```
- Start command (onerilen):
```bash
gunicorn personmeter.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
```
- Not: Bunun icin `gunicorn` paketini `requirements.txt`'ye ekle.

## C. Zorunlu environment degiskenleri
- Runtime:
  - `PERSONMETER_ENV=production`
  - `DJANGO_DEBUG=false`
  - `DJANGO_SECRET_KEY=<guclu-rastgele-deger>`
  - `DJANGO_ALLOWED_HOSTS=<senin-domainin>,www.<senin-domainin>`
  - `DJANGO_CSRF_TRUSTED_ORIGINS=https://<senin-domainin>,https://www.<senin-domainin>`
- PostgreSQL:
  - `DB_NAME`
  - `DB_USER`
  - `DB_PASSWORD`
  - `DB_HOST`
  - `DB_PORT`
- AWS S3:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_STORAGE_BUCKET_NAME`
  - `AWS_S3_REGION_NAME`

## D. Statik ve medya stratejisi
- Medya zaten S3'e yaziliyor (production ayarlari buna gore).
- Static icin iki yoldan birini sec:
1. WhiteNoise ekle (en hizli yol, tek container).
2. Nginx/CDN ile `/static` servis et.
- Go-live oncesi mutlaka:
```bash
python manage.py collectstatic --noinput
```

## E. Veritabani ve veri tasima
- Yeni VPS PostgreSQL olustur.
- Eski sistemden dump alip yeni DB'ye restore et.
- Deploy sirasi:
1. `python manage.py migrate`
2. Gerekirse `python manage.py createsuperuser`
3. Uygulama smoke test

## F. Security hardening (onerilen)
- `SECURE_SSL_REDIRECT=True` (proxy arkasinda)
- HSTS ac:
  - `SECURE_HSTS_SECONDS`
  - `SECURE_HSTS_INCLUDE_SUBDOMAINS`
  - `SECURE_HSTS_PRELOAD`
- Header sertlestirme:
  - `SECURE_CONTENT_TYPE_NOSNIFF=True`
  - `X_FRAME_OPTIONS='DENY'` (ihtiyaca gore)
- Cookie guvenligi:
  - `SESSION_COOKIE_SECURE=True` (zaten production'da true)
  - `CSRF_COOKIE_SECURE=True` (zaten production'da true)

## G. Uygulama guvenligi ve dayaniklilik
- Upload dogrulamasi ekle:
  - izinli mime/type
  - maksimum boyut
  - image open/save hatalarini yakala
- Uygulama loglarini merkezi topla:
  - gunluk rotate
  - 4xx/5xx alarmi
- DB backup politikasi:
  - gunluk otomatik backup
  - haftalik restore testi

## H. Performans / kapasite (4GB RAM)
- Gunicorn worker sayisi: 2-3 ile basla, RAM/latency izleyip ayarla.
- DB connection sayisini sinirla (asiri baglanti acma).
- Search ve home endpointlerini izleyip gerekli index/cache adimlarini planla.

## 4) Go-Live Kontrol Listesi (isaretleyerek git)

- [ ] Domain DNS kayitlari yeni VPS/Coolify yonlenmis
- [ ] SSL aktif, HTTPS zorunlu
- [ ] Tum production env degiskenleri Coolify'da tanimli
- [ ] `PERSONMETER_ENV=production` dogru
- [ ] PostgreSQL baglantisi test edildi
- [ ] `python manage.py migrate` basarili
- [ ] `python manage.py collectstatic --noinput` basarili
- [ ] Admin panel girisi calisiyor
- [ ] Login/register/rating/comment/report akislari test edildi
- [ ] S3 medya upload + goruntuleme test edildi
- [ ] 404/500 sayfalari kontrol edildi
- [ ] Backup ve rollback plani hazir

## 5) Ilk 24 Saat Izleme Plani

- Hata orani (5xx), response sureleri, RAM/CPU, disk ve DB connection takip et.
- Ozellikle su endpointleri izle:
  - `/`
  - `/search`
  - `/person/<id>`
- S3 erisim hatalari ve DB timeoutlarina alarm koy.

## 6) Bu Proje Ozelinde Hizli Aksiyon Onerisi

1. `requirements.txt` icine `gunicorn` ekle.
2. Static servis stratejisini netlestir (tercihen WhiteNoise).
3. Upload validasyonu + image exception handling patch'i cikar.
4. Security hardening ayarlarini env-temelli production'a ekle.
5. Coolify'da staging benzeri bir ilk deployment yapip sonra canliya gec.
