# 🦉 Athena — BIST Yapay Zeka Yatırım Asistanı

Kişisel BIST yatırım asistanı. Tüm piyasayı tarar, bütçeni yönetir, al/sat sinyali verir.

**Backend:** Django REST Framework + Supabase PostgreSQL + Groq (Llama 3.3 70B) + yfinance  
**Deploy:** Render.com  
**Dil:** Türkçe (tüm API yanıtları Türkçe)

---

## ⚠️ Frontend Geliştirici İçin Kritik Notlar

- **Authentication YOK** — Tüm endpointler herkese açık. Kişisel kullanım aracı.
- **yfinance 15 dk gecikmeli veri** verir. Anlık fiyat için kullanıcı kendi aracı kurumuna bakmalı.
- **CORS açık** — Her origin'den istek atılabilir (`CORS_ALLOW_ALL_ORIGINS = True`).
- **Groq rate limit** — AI analizi endpointleri (`/butce/olustur/`, `/invest/`, `/advisor/analyze/`) 429 dönebilir. UI'da bunu handle et.
- **Free Render** — 15 dk hareketsizlikte uyur, ilk istek 30-60 sn sürebilir. Loading state ekle.
- **Base URL:** `https://athena-backend.onrender.com` *(gerçek URL ile değiştir)*

---

## 🗺️ Ana İş Akışı (Ekran Tasarımı İçin)

```
[1] Kullanıcı bütçe girer (TL + risk profili)
        ↓
[2] POST /api/monitor/butce/olustur/
    → Athena 80 hisse tarar (~10-20 sn sürer)
    → 1-3 hisse önerir + Groq Türkçe analiz
        ↓
[3] Kullanıcı listeyi görür, hisseyi satın alır (gerçek hayatta)
    → POST /api/monitor/butce/pozisyon/{id}/alindi/
        ↓
[4] Takip ekranı: GET /api/monitor/butce/durum/
    → Anlık fiyat, kâr/zarar, tavsiye (TUT/SAT/DİKKAT)
    → acil_uyarilar doluysa kırmızı banner göster
        ↓
[5] Kullanıcı satar → POST /api/monitor/butce/pozisyon/{id}/kapat/
        ↓
[6] Geçmiş: GET /api/monitor/butce/gecmis/
```

---

## 📡 API Referansı — Bütçe Yönetimi

### `POST /api/monitor/butce/olustur/`
Piyasayı tara, hisse öner, plan oluştur.

**Request:**
```json
{
  "toplam_butce": 1000,
  "risk_profili": "orta",
  "max_hisse_sayisi": 3
}
```

| Alan | Tip | Zorunlu | Açıklama |
|------|-----|---------|----------|
| `toplam_butce` | float | ✅ | TL cinsinden bütçe |
| `risk_profili` | string | ✅ | `"dusuk"` / `"orta"` / `"yuksek"` |
| `max_hisse_sayisi` | int | ❌ | Kaç hisse (varsayılan: 3) |

**Risk Profilleri:**
| Profil | Stop-Loss | Hedef Kâr |
|--------|-----------|-----------|
| `dusuk` | -%4 | +%8 |
| `orta` | -%7 | +%15 |
| `yuksek` | -%10 | +%25 |

**Response (200 — başarılı):**
```json
{
  "plan_id": 1,
  "toplam_butce": 1000.0,
  "kullanilan_butce": 847.50,
  "kalan_nakit": 152.50,
  "risk_profili": "orta",
  "taranan_hisse": 80,
  "bulunan_aday": 5,
  "secilen_hisse": 3,
  "pozisyonlar": [
    {
      "id": 1,
      "sembol": "SISE",
      "adet": 10,
      "giris_fiyat": 45.20,
      "maliyet_tl": 452.00,
      "stop_fiyat": 42.04,
      "hedef_fiyat": 52.00,
      "stop_pct": 7,
      "hedef_pct": 15,
      "skor": 8,
      "sinyal": "GÜÇLÜ_AL",
      "rsi": 28.4,
      "trend": "yukari",
      "gerekceler": [
        "🟢 RSI 28 — Aşırı satım bölgesi",
        "🟢 MACD yukarı kesiş — Güçlü alım sinyali",
        "🟢 Yükseliş trendi"
      ],
      "durum": "bekliyor"
    }
  ],
  "athena_analiz": "SISE için RSI 28 ile aşırı satım bölgesindedir...",
  "mesaj": "Athena 80 hisse taradı, 5 aday buldu, en iyi 3 tanesini seçti."
}
```

**Response (200 — sinyal bulunamadı):**
```json
{
  "error": "Yeterli sinyal bulunamadı. Piyasa şu an nötr veya düşüş eğiliminde.",
  "taranan": 80
}
```
> ⚠️ Sinyal bulunamazsa `status=200` ile `error` alanı döner. `pozisyonlar` gelmez.

---

### `POST /api/monitor/butce/pozisyon/{id}/alindi/`
Kullanıcı hisseyi gerçekten aldı → pozisyonu aç.

**URL Parametresi:** `id` = pozisyon ID'si (`butce_olustur` yanıtındaki `pozisyonlar[].id`)

**Request (opsiyonel — gerçek alış fiyatı farklıysa):**
```json
{
  "gercek_fiyat": 45.50
}
```
> Body boş gönderilebilir. Boş giderse Athena'nın önerdiği fiyat kullanılır.

**Response (200):**
```json
{
  "status": "Pozisyon açık olarak işaretlendi",
  "sembol": "SISE",
  "adet": 10.0,
  "giris_fiyat": 45.50,
  "stop_fiyat": 42.32,
  "hedef_fiyat": 52.33,
  "maliyet_tl": 455.00,
  "mesaj": "SISE portföyüne eklendi. Stop: 42.32 TL | Hedef: 52.33 TL. Athena düzenli takip edecek."
}
```

---

### `GET /api/monitor/butce/durum/`
Aktif planın anlık durumu + SAT/TUT tavsiyesi.
> Bu ekranı her 60-120 saniyede bir yenile (polling).

**Response (200):**
```json
{
  "plan_id": 1,
  "toplam_butce": 1000.0,
  "risk_profili": "orta",
  "toplam_maliyet": 847.50,
  "toplam_guncel": 912.30,
  "toplam_kaz_kayip": 64.80,
  "toplam_kaz_kayip_pct": 7.65,
  "acik_pozisyon_sayisi": 3,
  "bekleyen_sayisi": 0,
  "acil_uyarilar": [],
  "son_tarama": "2025-01-15T10:30:00Z",
  "athena_analiz": "...",
  "pozisyonlar": [
    {
      "id": 1,
      "sembol": "SISE",
      "durum": "acik",
      "adet": 10.0,
      "giris_fiyat": 45.20,
      "guncel_fiyat": 48.50,
      "stop_fiyat": 42.04,
      "hedef_fiyat": 52.00,
      "maliyet_tl": 452.00,
      "guncel_deger": 485.00,
      "kaz_kayip_tl": 33.00,
      "kaz_kayip_pct": 7.30,
      "degisim_bugun": 1.25,
      "rsi": 52.3,
      "trend": "yukari",
      "tavsiye": "TUT",
      "athena_sinyal": "AL",
      "sinyal_skoru": 4,
      "gerekceler": ["🟢 Yükseliş trendi", "🟢 MACD pozitif momentum"],
      "acil_uyari": null
    }
  ]
}
```

**`tavsiye` Değerleri (UI renklendirme için):**
| Değer | Renk | Açıklama |
|-------|------|----------|
| `TUT` | ⚪ gri | Pozisyon sağlıklı, bekle |
| `TUT_AL` | 🟢 yeşil | Güçlü sinyal, ekleme yapılabilir |
| `SAT` | 🔴 kırmızı | Stop geldi veya güçlü SAT sinyali — acil |
| `DİKKAT` | 🟡 sarı | Stop seviyesine yaklaşıyor |

**`durum` Değerleri:**
| Değer | Açıklama |
|-------|----------|
| `bekliyor` | Athena önerdi, kullanıcı henüz almadı |
| `acik` | Kullanıcı aldı, pozisyon açık |

**`acil_uyarilar`:** Boş array `[]` ise sorun yok. Dolu ise her string'i kırmızı banner olarak göster.

**Hata (404 — aktif plan yok):**
```json
{
  "error": "Aktif bütçe planı yok. /api/monitor/butce/olustur/ ile başla."
}
```

---

### `POST /api/monitor/butce/pozisyon/{id}/kapat/`
Pozisyonu kapat, kar/zarar kaydet.

**Request:**
```json
{
  "cikis_fiyat": 52.00,
  "neden": "hedef"
}
```

| Alan | Tip | Zorunlu | Açıklama |
|------|-----|---------|----------|
| `cikis_fiyat` | float | ❌ | Boş bırakılırsa anlık fiyat alınır |
| `neden` | string | ❌ | `"hedef"` / `"stop"` / `"manuel"` (varsayılan: `"manuel"`) |

**Response (200):**
```json
{
  "status": "Pozisyon kapatıldı",
  "sembol": "SISE",
  "giris_fiyat": 45.20,
  "cikis_fiyat": 52.00,
  "adet": 10.0,
  "maliyet_tl": 452.00,
  "gelir_tl": 520.00,
  "kaz_kayip_tl": 68.00,
  "kaz_kayip_pct": 15.04,
  "durum": "hedef",
  "mesaj": "✅ SISE kapatıldı: +68.00 TL (+15.04%)"
}
```

---

### `POST /api/monitor/butce/yeni-firsat/`
Kalan nakit için yeni fırsat ara.

**Request:**
```json
{
  "kalan_butce": 152.50,
  "risk_profili": "orta"
}
```

**Response (200):**
```json
{
  "kalan_butce": 152.50,
  "bulunan": 3,
  "oneriler": [
    {
      "sembol": "KRDMD",
      "puan": 6,
      "fiyat": 12.30,
      "adet": 12,
      "maliyet": 147.60,
      "stop_f": 11.44,
      "hedef_f": 14.15,
      "rsi": 31.2,
      "trend": "yukari",
      "gerekceler": ["🟢 RSI 31 — Aşırı satım bölgesi", "🟢 MACD yukarı kesiş"]
    }
  ],
  "mesaj": "3 yeni fırsat bulundu, en iyi 3 tanesi listelendi."
}
```

---

### `GET /api/monitor/butce/gecmis/`
Kapalı pozisyonların performans geçmişi.

**Response (200):**
```json
{
  "toplam_islem": 10,
  "kazanan": 7,
  "kaybeden": 3,
  "basari_orani": 70.0,
  "toplam_kaz_kayip_tl": 342.50,
  "pozisyonlar": [
    {
      "sembol": "SISE",
      "giris_fiyat": 45.20,
      "cikis_fiyat": 52.00,
      "adet": 10.0,
      "kaz_kayip_tl": 68.00,
      "kaz_kayip_pct": 15.04,
      "durum": "hedef",
      "acilis": "2025-01-10T09:30:00Z",
      "kapanis": "2025-01-15T14:22:00Z"
    }
  ]
}
```

**`durum` Değerleri (geçmiş için):**
| Değer | Açıklama |
|-------|----------|
| `hedef` | Hedef fiyata ulaştı (kâr) |
| `stop` | Stop-loss tetiklendi (zarar) |
| `kapali` | Manuel kapatıldı |

---

## 📡 API Referansı — Diğer Endpointler

### `GET /api/monitor/market/`
Genel piyasa paneli (BIST100, döviz, altın, öne çıkan hisseler).

**Response:**
```json
{
  "overview": {
    "bist100": {"price": 9842.50, "change_percent": 1.23},
    "usdtry": {"price": 32.45, "change_percent": 0.12},
    "altin": {"price": 2450.30, "change_percent": -0.5}
  },
  "top_gainers": [
    {"symbol": "THYAO", "price": 245.60, "change_percent": 4.52}
  ],
  "top_losers": [
    {"symbol": "PETKM", "price": 18.20, "change_percent": -3.10}
  ],
  "timestamp": "2025-01-15T10:30:00Z"
}
```

---

### `GET /api/monitor/scan/results/?limit=20&min_score=0`
Tüm hisselerin anlık tarama skorları (AI olmadan, hızlı).

**Query Params:**
| Param | Varsayılan | Açıklama |
|-------|-----------|----------|
| `limit` | 20 | Kaç sonuç dönsün |
| `min_score` | 0 | Minimum mutlak skor filtresi |

**Response:**
```json
{
  "count": 15,
  "results": [
    {
      "symbol": "SISE",
      "price": 45.20,
      "change_percent": 1.25,
      "score": 8,
      "signal": "GÜÇLÜ_AL",
      "rsi": 28.4,
      "trend": "yukari",
      "volume_signal": "yuksek",
      "reasons": ["🟢 RSI 28 — Aşırı satım", "🟢 MACD yukarı kesiş"],
      "in_portfolio": false
    }
  ]
}
```

**`signal` Değerleri:**
| Değer | Açıklama |
|-------|----------|
| `GÜÇLÜ_AL` | Skor ≥ 6 |
| `AL` | Skor 3-5 |
| `BEKLE` | Skor -2 ile 2 arası |
| `SAT` | Skor -3 ile -5 arası |
| `GÜÇLÜ_SAT` | Skor ≤ -6 |

---

### `GET /api/advisor/signal/{SEMBOL}/`
Tek hisse için hızlı kural-tabanlı sinyal (AI kullanmaz, anlık).

**Örnek:** `GET /api/advisor/signal/THYAO/`

**Response:**
```json
{
  "symbol": "THYAO",
  "signal": "AL",
  "signal_strength": "Güçlü",
  "signal_emoji": "🟢",
  "score": 4,
  "price": 245.60,
  "change_percent": 1.25,
  "rsi": 42.3,
  "trend": "yukari",
  "macd_histogram": 0.45,
  "bb_position": "normal",
  "support": 238.50,
  "resistance": 252.00,
  "reasons": [
    "🟢 MACD pozitif momentum sürüyor",
    "🟢 Trend yukarı",
    "⚪ RSI 42 → Normal bölge"
  ],
  "note": "Kural tabanlı hızlı sinyal. Tam AI analizi için /api/advisor/analyze/ kullanın."
}
```

---

### `GET /api/advisor/analyze/`
Portföydeki tüm hisseler için Groq AI derin analizi.
> ⚠️ Groq API çağrısı yapar, 5-15 sn sürebilir. Rate limit riski var.

**Response:**
```json
{
  "portfolio": [...],
  "analysis": "## 1. PORTFÖY GENEL SAĞLIĞI\n...",
  "model": "llama-3.3-70b-versatile",
  "type": "full_analysis"
}
```

---

### `POST /api/advisor/ask/`
Athena'ya serbest soru sor (konuşma geçmişi destekli).

**Request:**
```json
{
  "question": "MOGAN'ı satmalı mıyım?",
  "history": [
    {"role": "user", "content": "THYAO iyi mi?"},
    {"role": "assistant", "content": "THYAO şu an..."}
  ]
}
```
> `history` opsiyonel. Önceki mesajları gönderirsen Athena bağlamı hatırlar (max son 10 mesaj).

**Response:**
```json
{
  "question": "MOGAN'ı satmalı mıyım?",
  "answer": "MOGAN için RSI 72 ile aşırı alım bölgesinde...",
  "model": "llama-3.3-70b-versatile"
}
```

---

### `POST /api/monitor/invest/`
Gelişmiş tek hisse yatırım danışmanı (AI analiz + plan kaydet + mail).

**Request:**
```json
{
  "symbol": "THYAO",
  "budget": 5000,
  "risk_level": "orta",
  "strategy": "swing",
  "market": "bist"
}
```

| Alan | Varsayılan | Seçenekler |
|------|-----------|-----------|
| `symbol` | — | Boş bırakılırsa en iyi hisse otomatik seçilir |
| `budget` | — | TL (zorunlu) |
| `risk_level` | `"orta"` | `"dusuk"` / `"orta"` / `"yuksek"` |
| `strategy` | `"swing"` | `"scalp"` / `"swing"` / `"pozisyon"` / `"temetu"` |
| `market` | `"bist"` | `"bist"` / `"kripto"` / `"emtia"` / `"forex"` |

---

### `GET /api/monitor/plans/`
Aktif yatırım planları listesi (anlık fiyat + K/Z durumu).

---

### `POST /api/monitor/scan/`
Manuel piyasa taraması başlat + sinyal maili gönder.

---

### `GET /api/monitor/alerts/`
Geçmiş sinyal uyarıları.

**Query Params:** `?symbol=THYAO&signal=AL`

---

### `GET /api/monitor/commodities/`
Altın, gümüş, petrol, döviz, kripto anlık verileri.

---

### `GET /api/portfolio/`
Portföy özeti (Portfolio modeli — manuel eklenen hisseler).

### `POST /api/portfolio/add/`
Portföye hisse ekle.
```json
{"symbol": "THYAO", "quantity": 10, "avg_cost": 240.50}
```

### `POST /api/portfolio/sell/`
Portföyden hisse çıkar.
```json
{"symbol": "THYAO", "quantity": 5, "sell_price": 250.00}
```

---

### `GET /api/stocks/{SEMBOL}/`
Hisse detay verisi (fiyat, teknik göstergeler, fundamental).

### `GET /api/news/`
KAP haberleri RSS.

**Query Params:** `?symbol=THYAO&limit=10`

---

## 🖥️ Önerilen Ekranlar

```
1. Ana Sayfa / Dashboard
   → Piyasa özeti (BIST100, USD/TRY, Altın)
   → Aktif bütçe durumu (özet kart)
   → Son uyarılar

2. Bütçe Oluştur
   → Bütçe + risk profili + hisse sayısı form
   → Loading: "Athena 80 hisseyi tarıyor..." (~10-20 sn)
   → Sonuç: Önerilen hisseler kartları + Athena analiz metni
   → Her kart: "Aldım" butonu

3. Pozisyon Takip
   → Açık pozisyonlar listesi
   → Her pozisyon: anlık fiyat, K/Z yüzdesi, tavsiye badge
   → Kırmızı banner: acil_uyarilar doluysa
   → "Kapat" butonu → fiyat girişi → kapanma

4. Tarama / Fırsatlar
   → /api/monitor/scan/results/ sonuçları
   → Filtreler: min skor, signal tipi

5. Athena Chat
   → /api/advisor/ask/ ile sohbet arayüzü
   → History state'i frontend'de tut, her seferinde gönder

6. Geçmiş / Performans
   → /api/monitor/butce/gecmis/
   → Kazanma oranı, toplam kâr/zarar grafik
```

---

## 💰 Servis Maliyetleri

| Servis | Ücret |
|--------|-------|
| Groq (Llama 3.3 70B) | Ücretsiz (14.400 istek/gün) |
| Render Web Service | Ücretsiz (750 saat/ay) |
| Render PostgreSQL | Ücretsiz (90 gün) |
| yfinance | Ücretsiz (15dk gecikmeli) |
| KAP RSS | Ücretsiz |

---

## 🔧 Hata Kodları

| HTTP | Açıklama |
|------|----------|
| 200 | Başarılı (dikkat: bazı "hata" durumları da 200 döner, `error` alanını kontrol et) |
| 400 | Eksik veya hatalı istek parametresi |
| 404 | Kaynak bulunamadı (pozisyon ID, aktif plan yok, vb.) |
| 429 | Groq API rate limit — 1 dk bekle, tekrar dene |
| 500 | Sunucu hatası (genellikle API key sorunu) |

---

*Bu analiz kişisel kullanım içindir, resmi yatırım tavsiyesi değildir. Son karar her zaman kullanıcıya aittir.*