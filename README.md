# 🦉 Athena Backend — BIST Yatırım Asistanı

Tamamen ücretsiz, Groq tabanlı, kişisel BIST yatırım asistanı.
Tüm piyasayı tarar, bütçeni yönetir, ne zaman alıp satacağını söyler.

---

## 🚀 Hızlı Başlangıç (Local)

```bash
# 1. Sanal ortam kur
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 2. Bağımlılıkları yükle
pip install -r requirements.txt

# 3. .env dosyasını oluştur
cp .env.example .env
# → .env'i aç, GROQ_API_KEY'ini yaz (console.groq.com → ücretsiz)

# 4. Veritabanını hazırla
python manage.py migrate

# 5. Çalıştır
python manage.py runserver
```

---

## 📡 API Kullanımı

### 1️⃣ Bütçe Gir — Athena Piyasayı Tarasın

```http
POST /api/monitor/butce/olustur/
Content-Type: application/json

{
  "toplam_butce": 1000,
  "risk_profili": "orta",
  "max_hisse_sayisi": 3
}
```

**Risk Profilleri:**
| Profil | Stop-Loss | Hedef Kâr |
|--------|-----------|-----------|
| dusuk  | -%4       | +%8       |
| orta   | -%7       | +%15      |
| yuksek | -%10      | +%25      |

**Athena ne yapar?**
- BIST'teki 80 likit hisseyi tarar
- RSI, MACD, Bollinger, Trend, Stochastic, Williams %R ile skorlar
- Skor ≥ 4 olan güçlü adayları seçer
- Bütçene göre kaç adet alacağını hesaplar
- Groq ile Türkçe analiz yazar
- Stop-loss ve hedef fiyat belirler

**Yanıt:**
```json
{
  "plan_id": 1,
  "toplam_butce": 1000,
  "kullanilan_butce": 847.50,
  "kalan_nakit": 152.50,
  "pozisyonlar": [
    {
      "id": 1,
      "sembol": "SISE",
      "adet": 10,
      "giris_fiyat": 45.20,
      "maliyet_tl": 452.00,
      "stop_fiyat": 42.04,
      "hedef_fiyat": 52.00,
      "skor": 8,
      "gerekceler": ["🟢 RSI 28 — Aşırı satım", "🟢 MACD yukarı kesiş", "..."],
      "durum": "bekliyor"
    }
  ],
  "athena_analiz": "SISE için: RSI 28 ile aşırı satım bölgesinde..."
}
```

---

### 2️⃣ "Aldım" Onayı Ver

```http
POST /api/monitor/butce/pozisyon/1/alindi/
Content-Type: application/json

{
  "gercek_fiyat": 45.50
}
```
*(gercek_fiyat opsiyonel — vermezsen Athena'nın önerdiği fiyatı kullanır)*

---

### 3️⃣ Anlık Takip — Athena SAT Sinyali Verir Mi?

```http
GET /api/monitor/butce/durum/
```

**Yanıt:**
```json
{
  "toplam_maliyet": 847.50,
  "toplam_guncel": 912.30,
  "toplam_kaz_kayip": 64.80,
  "toplam_kaz_kayip_pct": 7.65,
  "acil_uyarilar": [],
  "pozisyonlar": [
    {
      "sembol": "SISE",
      "guncel_fiyat": 48.50,
      "kaz_kayip_tl": 33.00,
      "kaz_kayip_pct": 7.30,
      "tavsiye": "TUT",
      "acil_uyari": null
    }
  ]
}
```

**Tavsiye değerleri:**
- `TUT` — Pozisyon sağlıklı, beklemeye devam
- `TUT_AL` — Güçlü sinyal, ekleme yapılabilir
- `SAT` — Stop-loss geldi veya güçlü SAT sinyali
- `DİKKAT` — Stop seviyesine yaklaşıyor

---

### 4️⃣ Pozisyon Kapat

```http
POST /api/monitor/butce/pozisyon/1/kapat/
Content-Type: application/json

{
  "cikis_fiyat": 52.00,
  "neden": "hedef"
}
```
*(neden: "hedef" | "stop" | "manuel")*

---

### 5️⃣ Yeni Fırsat Ara (Kalan Nakit İçin)

```http
POST /api/monitor/butce/yeni-firsat/
Content-Type: application/json

{
  "kalan_butce": 152.50,
  "risk_profili": "orta"
}
```

---

### 6️⃣ Performans Geçmişi

```http
GET /api/monitor/butce/gecmis/
```

---

## 📊 Diğer Endpointler

| Endpoint | Metod | Açıklama |
|----------|-------|----------|
| `/api/portfolio/` | GET | Portföy özeti |
| `/api/portfolio/add/` | POST | Hisse ekle |
| `/api/portfolio/sell/` | POST | Hisse sat |
| `/api/advisor/analyze/` | GET | AI portföy analizi |
| `/api/advisor/signal/SISE/` | GET | Hızlı sinyal |
| `/api/monitor/market/` | GET | Piyasa paneli |
| `/api/monitor/scan/results/` | GET | Tüm tarama sonuçları |
| `/api/stocks/SISE/` | GET | Hisse detayı |
| `/api/news/` | GET | KAP haberleri |

---

## 🌐 Render'a Deploy

1. GitHub'a push et (`.env` dosyasını ASLA commit etme!)
2. [render.com](https://render.com) → New Web Service
3. GitHub repo'nu bağla
4. **Build Command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
5. **Start Command:** `gunicorn core.wsgi --log-file -`
6. **Environment Variables** bölümüne `.env.example`'daki değerleri gir
7. PostgreSQL için: Render Dashboard → New PostgreSQL → `DATABASE_URL`'i kopyala → Environment Variables'a yapıştır

---

## 💰 Maliyet

| Servis | Ücret |
|--------|-------|
| Groq (Llama 3.3 70B) | **Tamamen ücretsiz** (14.400 istek/gün) |
| Render (Web Service) | **Ücretsiz** (750 saat/ay) |
| Render (PostgreSQL) | **Ücretsiz** (90 gün, sonra $7/ay) |
| yfinance (BIST verisi) | **Tamamen ücretsiz** (15dk gecikmeli) |
| KAP RSS | **Tamamen ücretsiz** |

> **Tahmini aylık maliyet: 0 TL** (90 gün içinde)

---

## ⚠️ Önemli Notlar

- Bu uygulama **yalnızca kişisel kullanım** içindir.
- Al/Sat tavsiyeleri yatırım danışmanlığı değil, AI teknik analizidir. **Son karar her zaman kullanıcıya aittir.**
- yfinance 15 dakika gecikmeli veri verir. Anlık fiyat için aracı kurum uygulamanızı kullanın.
- API Key'leri asla koda yazmayın, her zaman `.env` dosyasında tutun.