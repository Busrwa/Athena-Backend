"""
Athena Paper Trading Engine v2
================================
- Sanal para ile gerçek fiyat hareketlerini takip eder
- Otomatik stop-loss ve hedef fiyat kontrolü
- Backtesting: geçmiş verilerle sinyal doğrulama
- Her pozisyon için gerçek zamanlı kâr/zarar hesabı
- Karar geçmişi ve istatistik raporu

Endpointler:
  POST /api/paper/ac/          — Yeni sanal pozisyon aç
  GET  /api/paper/pozisyonlar/ — Açık/Kapalı pozisyonlar
  POST /api/paper/guncelle/    — Fiyat kontrolü (stop/hedef)
  GET  /api/paper/istatistik/  — Performans özeti
  POST /api/paper/backtest/    — Geçmiş sinyal testi
  POST /api/paper/hepsi-guncelle/ — Tüm açık pozisyonları kontrol et
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta

from stocks.services import get_stock_data, get_technical_indicators
from monitor.models import PaperTrade
from monitor.scanner import compute_score, _get_signal_label


# ─── Yardımcılar ──────────────────────────────────────────────────────────────

def _poz_to_dict(p: PaperTrade, guncel_fiyat: float = None) -> dict:
    giris = float(p.giris_fiyat)
    adet  = float(p.adet)
    maliyet = round(giris * adet, 2)

    gf = guncel_fiyat or giris
    guncel_deger = round(gf * adet, 2)
    kz_tl  = round(guncel_deger - maliyet, 2)
    kz_pct = round((gf - giris) / giris * 100, 2) if giris else 0

    return {
        'id':              p.id,
        'sembol':          p.sembol,
        'strateji':        p.strateji,
        'giris_fiyat':     giris,
        'adet':            adet,
        'sanal_butce':     float(p.sanal_butce),
        'stop_fiyat':      round(float(p.giris_fiyat) * (1 - float(p.stop_pct) / 100), 4),
        'hedef_fiyat':     round(float(p.giris_fiyat) * (1 + float(p.hedef_pct) / 100), 4),
        'stop_pct':        float(p.stop_pct),
        'hedef_pct':       float(p.hedef_pct),
        'giris_skoru':     p.giris_skoru,
        'giris_sinyali':   p.giris_sinyali,
        'acilis_tarihi':   p.acilis_tarihi.isoformat(),
        'durum':           p.durum,
        'maliyet_tl':      maliyet,
        'guncel_fiyat':    round(gf, 2),
        'guncel_deger_tl': guncel_deger,
        'anlık_kz_tl':     kz_tl,
        'anlık_kz_pct':    kz_pct,
        'cikis_fiyat':     float(p.cikis_fiyat) if p.cikis_fiyat else None,
        'cikis_tarihi':    p.cikis_tarihi.isoformat() if p.cikis_tarihi else None,
        'kaz_kayip_tl':    float(p.kaz_kayip_tl) if p.kaz_kayip_tl else None,
        'kaz_kayip_pct':   float(p.kaz_kayip_pct) if p.kaz_kayip_pct else None,
        'not_alani':       p.not_alani,
    }


def _kapat(p: PaperTrade, fiyat: float, neden: str) -> PaperTrade:
    giris = float(p.giris_fiyat)
    adet  = float(p.adet)
    kz_tl  = round((fiyat - giris) * adet, 2)
    kz_pct = round((fiyat - giris) / giris * 100, 2)

    p.durum        = neden
    p.cikis_fiyat  = fiyat
    p.cikis_tarihi = timezone.now()
    p.kaz_kayip_tl  = kz_tl
    p.kaz_kayip_pct = kz_pct
    p.save()
    return p


# ─── 1. Pozisyon Aç ──────────────────────────────────────────────────────────

@api_view(['POST'])
def pozisyon_ac(request):
    """
    POST /api/paper/ac/
    Body: {
        "sembol": "THYAO",
        "sanal_butce": 1000,       ← TL cinsinden
        "strateji": "kisa",        ← kisa | uzun
        "stop_pct": 7,             ← opsiyonel, varsayılan risk profiline göre
        "hedef_pct": 15            ← opsiyonel
    }
    Athena teknik analiz yapar, skoru hesaplar, pozisyonu açar.
    """
    sembol      = request.data.get('sembol', '').upper().strip()
    sanal_butce = float(request.data.get('sanal_butce', 1000))
    strateji    = request.data.get('strateji', 'kisa')
    stop_pct    = float(request.data.get('stop_pct', 7 if strateji == 'kisa' else 10))
    hedef_pct   = float(request.data.get('hedef_pct', 15 if strateji == 'kisa' else 25))

    if not sembol:
        return Response({'error': 'sembol gerekli'}, status=400)
    if sanal_butce <= 0:
        return Response({'error': 'sanal_butce > 0 olmalı'}, status=400)

    # Gerçek fiyat
    stock = get_stock_data(sembol)
    if not stock or stock.get('price', 0) <= 0:
        return Response({'error': f'{sembol} için fiyat alınamadı'}, status=400)

    fiyat = stock['price']
    adet  = sanal_butce / fiyat
    if adet < 0.001:
        return Response({'error': 'Bütçe yetersiz, en az 1 hisse alınamıyor'}, status=400)

    # Teknik analiz skoru
    tech = get_technical_indicators(sembol)
    puan, gerekceler = compute_score(tech, stock)
    sinyal = _get_signal_label(puan)

    # Pozisyon kaydet
    p = PaperTrade.objects.create(
        sembol        = sembol,
        strateji      = strateji,
        giris_fiyat   = fiyat,
        adet          = round(adet, 4),
        sanal_butce   = sanal_butce,
        stop_pct      = stop_pct,
        hedef_pct     = hedef_pct,
        giris_skoru   = puan,
        giris_sinyali = sinyal,
        not_alani     = ' | '.join(gerekceler[:4]),
    )

    return Response({
        'mesaj':       'Pozisyon açıldı ✅',
        'pozisyon':    _poz_to_dict(p, fiyat),
        'teknik_ozet': tech.get('summary', ''),
        'gerekceler':  gerekceler,
        'uyari': (
            'Bu sanal (paper) işlemdir. Gerçek para kullanılmamaktadır. '
            'Bu analiz yatırım tavsiyesi değildir.'
        ),
    })


# ─── 2. Pozisyonlar ──────────────────────────────────────────────────────────

@api_view(['GET'])
def pozisyonlar(request):
    """
    GET /api/paper/pozisyonlar/?durum=acik
    durum: acik | kapali | hepsi (varsayılan: hepsi)
    """
    durum_filtre = request.query_params.get('durum', 'hepsi')
    qs = PaperTrade.objects.all()
    if durum_filtre == 'acik':
        qs = qs.filter(durum='acik')
    elif durum_filtre == 'kapali':
        qs = qs.exclude(durum='acik')

    result = []
    for p in qs[:100]:
        gf = None
        if p.durum == 'acik':
            stock = get_stock_data(p.sembol)
            if stock:
                gf = stock['price']
        result.append(_poz_to_dict(p, gf))

    return Response({
        'count': len(result),
        'pozisyonlar': result,
    })


# ─── 3. Tek Pozisyon Güncelle ─────────────────────────────────────────────────

@api_view(['POST'])
def pozisyon_guncelle(request, pozisyon_id: int):
    """
    POST /api/paper/guncelle/<id>/
    Fiyat çeker, stop ve hedef kontrol eder, gerekirse kapatır.
    """
    try:
        p = PaperTrade.objects.get(id=pozisyon_id, durum='acik')
    except PaperTrade.DoesNotExist:
        return Response({'error': 'Pozisyon bulunamadı veya zaten kapalı'}, status=404)

    stock = get_stock_data(p.sembol)
    if not stock:
        return Response({'error': 'Fiyat alınamadı'}, status=400)

    fiyat       = stock['price']
    stop_fiyat  = float(p.giris_fiyat) * (1 - float(p.stop_pct) / 100)
    hedef_fiyat = float(p.giris_fiyat) * (1 + float(p.hedef_pct) / 100)

    tetiklendi = None
    if fiyat <= stop_fiyat:
        _kapat(p, fiyat, 'stop')
        tetiklendi = f'🔴 STOP-LOSS tetiklendi! {p.sembol} {stop_fiyat:.2f} TL seviyesine düştü.'
    elif fiyat >= hedef_fiyat:
        _kapat(p, fiyat, 'hedef')
        tetiklendi = f'🟢 HEDEF TUTTU! {p.sembol} {hedef_fiyat:.2f} TL hedefine ulaştı!'

    p.refresh_from_db()
    return Response({
        'pozisyon':    _poz_to_dict(p, fiyat if p.durum == 'acik' else None),
        'tetiklendi':  tetiklendi,
        'guncel_fiyat': fiyat,
        'stop_fiyat':  round(stop_fiyat, 2),
        'hedef_fiyat': round(hedef_fiyat, 2),
    })


# ─── 4. Tüm Açık Pozisyonları Güncelle ───────────────────────────────────────

@api_view(['POST'])
def hepsini_guncelle(request):
    """
    POST /api/paper/hepsi-guncelle/
    Tüm açık pozisyonları tek seferde fiyat kontrolü yap.
    Stop veya hedef tetiklenenleri otomatik kapat.
    """
    acik = PaperTrade.objects.filter(durum='acik')
    sonuclar = []
    tetiklenenler = []

    for p in acik:
        stock = get_stock_data(p.sembol)
        if not stock:
            sonuclar.append({'sembol': p.sembol, 'durum': 'fiyat_alinamadi'})
            continue

        fiyat       = stock['price']
        stop_fiyat  = float(p.giris_fiyat) * (1 - float(p.stop_pct) / 100)
        hedef_fiyat = float(p.giris_fiyat) * (1 + float(p.hedef_pct) / 100)
        giris       = float(p.giris_fiyat)
        kz_pct      = round((fiyat - giris) / giris * 100, 2)

        durum_mesaj = f'+{kz_pct}%' if kz_pct >= 0 else f'{kz_pct}%'

        if fiyat <= stop_fiyat:
            _kapat(p, fiyat, 'stop')
            msg = f'🔴 STOP → {p.sembol} kapatıldı ({kz_pct:+.1f}%)'
            tetiklenenler.append(msg)
            sonuclar.append({'sembol': p.sembol, 'durum': 'stop_tetiklendi', 'fiyat': fiyat, 'kz_pct': kz_pct})
        elif fiyat >= hedef_fiyat:
            _kapat(p, fiyat, 'hedef')
            msg = f'🟢 HEDEF → {p.sembol} kapatıldı ({kz_pct:+.1f}%)'
            tetiklenenler.append(msg)
            sonuclar.append({'sembol': p.sembol, 'durum': 'hedef_tuttu', 'fiyat': fiyat, 'kz_pct': kz_pct})
        else:
            sonuclar.append({
                'sembol': p.sembol, 'durum': 'acik', 'fiyat': fiyat,
                'kz_pct': kz_pct, 'stop': round(stop_fiyat, 2),
                'hedef': round(hedef_fiyat, 2),
                'ozet': durum_mesaj,
            })

    return Response({
        'kontrol_edilen': len(sonuclar),
        'tetiklenenler':  tetiklenenler,
        'sonuclar':       sonuclar,
    })


# ─── 5. İstatistik ────────────────────────────────────────────────────────────

@api_view(['GET'])
def istatistik(request):
    """
    GET /api/paper/istatistik/
    Tüm paper trade geçmişinin özeti.
    """
    tumü = PaperTrade.objects.all()
    acik = [p for p in tumü if p.durum == 'acik']
    kapalı = [p for p in tumü if p.durum != 'acik']

    # Açık pozisyonlar anlık K/Z
    acik_kz = 0.0
    for p in acik:
        stock = get_stock_data(p.sembol)
        if stock:
            gf = stock['price']
            acik_kz += (gf - float(p.giris_fiyat)) * float(p.adet)

    # Kapalı pozisyon istatistikleri
    kazananlar = [p for p in kapalı if p.kaz_kayip_tl and float(p.kaz_kayip_tl) > 0]
    kaybedenler = [p for p in kapalı if p.kaz_kayip_tl and float(p.kaz_kayip_tl) <= 0]
    stop_count  = len([p for p in kapalı if p.durum == 'stop'])
    hedef_count = len([p for p in kapalı if p.durum == 'hedef'])

    toplam_kz = sum(float(p.kaz_kayip_tl or 0) for p in kapalı)
    ort_kz_pct = 0.0
    if kapalı:
        pctler = [float(p.kaz_kayip_pct or 0) for p in kapalı]
        ort_kz_pct = round(sum(pctler) / len(pctler), 2)

    kazanma_orani = round(len(kazananlar) / len(kapalı) * 100, 1) if kapalı else 0

    # En iyi ve en kötü işlem
    en_iyi = max(kapalı, key=lambda p: float(p.kaz_kayip_pct or -999), default=None)
    en_kotu = min(kapalı, key=lambda p: float(p.kaz_kayip_pct or 999), default=None)

    # Açık pozisyonlar özeti
    acik_ozet = []
    for p in acik:
        stock = get_stock_data(p.sembol)
        gf = stock['price'] if stock else float(p.giris_fiyat)
        kz = round((gf - float(p.giris_fiyat)) / float(p.giris_fiyat) * 100, 2)
        acik_ozet.append({
            'sembol': p.sembol,
            'giris': float(p.giris_fiyat),
            'guncel': round(gf, 2),
            'kz_pct': kz,
            'stop': round(float(p.giris_fiyat) * (1 - float(p.stop_pct) / 100), 2),
            'hedef': round(float(p.giris_fiyat) * (1 + float(p.hedef_pct) / 100), 2),
        })

    return Response({
        'ozet': {
            'toplam_islem':     len(tumü),
            'acik_pozisyon':    len(acik),
            'kapali_islem':     len(kapalı),
            'kazananlar':       len(kazananlar),
            'kaybedenler':      len(kaybedenler),
            'stop_tetiklenen':  stop_count,
            'hedef_tutan':      hedef_count,
            'kazanma_orani_pct': kazanma_orani,
            'toplam_kz_tl':     round(toplam_kz, 2),
            'acik_anlık_kz_tl': round(acik_kz, 2),
            'ort_kz_pct':       ort_kz_pct,
        },
        'en_iyi_islem': {
            'sembol': en_iyi.sembol,
            'kz_pct': float(en_iyi.kaz_kayip_pct),
            'kz_tl':  float(en_iyi.kaz_kayip_tl),
            'tarih':  en_iyi.acilis_tarihi.isoformat(),
        } if en_iyi else None,
        'en_kotu_islem': {
            'sembol': en_kotu.sembol,
            'kz_pct': float(en_kotu.kaz_kayip_pct),
            'kz_tl':  float(en_kotu.kaz_kayip_tl),
            'tarih':  en_kotu.acilis_tarihi.isoformat(),
        } if en_kotu else None,
        'acik_pozisyonlar': acik_ozet,
        'uyari': 'Bu sanal işlem istatistikleridir. Gerçek para söz konusu değildir.',
    })


# ─── 6. Manuel Kapat ─────────────────────────────────────────────────────────

@api_view(['POST'])
def pozisyon_kapat_manuel(request, pozisyon_id: int):
    """
    POST /api/paper/kapat/<id>/
    Kullanıcı manuel olarak pozisyonu kapatır.
    Body: {"fiyat": 42.5}  ← opsiyonel, yoksa anlık fiyat alınır
    """
    try:
        p = PaperTrade.objects.get(id=pozisyon_id, durum='acik')
    except PaperTrade.DoesNotExist:
        return Response({'error': 'Pozisyon bulunamadı veya zaten kapalı'}, status=404)

    fiyat = request.data.get('fiyat')
    if fiyat:
        fiyat = float(fiyat)
    else:
        stock = get_stock_data(p.sembol)
        if not stock:
            return Response({'error': 'Fiyat alınamadı, manuel fiyat girin'}, status=400)
        fiyat = stock['price']

    _kapat(p, fiyat, 'kapali')
    p.refresh_from_db()

    return Response({
        'mesaj': f'{p.sembol} pozisyonu kapatıldı.',
        'pozisyon': _poz_to_dict(p),
    })


# ─── 7. Backtest ─────────────────────────────────────────────────────────────

@api_view(['POST'])
def backtest(request):
    """
    POST /api/paper/backtest/
    Body: {
        "sembol": "THYAO",
        "stop_pct": 7,
        "hedef_pct": 15,
        "period": "1y"       ← 6mo | 1y | 2y
    }

    Athena geçmiş 1 yılın verisiyle şu soruyu cevaplar:
    "Bu sinyal motoru geçmişte çalışsaydı ne olurdu?"

    Yöntem: Her gün için teknik indikatörler hesapla → AL sinyali varsa
    'alındı' say → N gün sonra veya stop/hedef'e ulaştığında 'satıldı' say.
    """
    sembol    = request.data.get('sembol', '').upper().strip()
    stop_pct  = float(request.data.get('stop_pct', 7))
    hedef_pct = float(request.data.get('hedef_pct', 15))
    period    = request.data.get('period', '1y')

    if not sembol:
        return Response({'error': 'sembol gerekli'}, status=400)

    try:
        import yfinance as yf
        yf_sym = f"{sembol}.IS"
        ticker = yf.Ticker(yf_sym)
        hist   = ticker.history(period=period)

        if hist.empty or len(hist) < 60:
            return Response({'error': 'Yeterli geçmiş veri yok (min 60 gün)'}, status=400)

        close  = list(hist['Close'].values.tolist())
        high   = list(hist['High'].values.tolist())
        low    = list(hist['Low'].values.tolist())
        volume = list(hist['Volume'].values.tolist())
        dates  = [str(d.date()) for d in hist.index]
        n      = len(close)

        from stocks.services import _ema, _ewm_com, _sma
        from statistics import mean, stdev

        # Önceden tüm RSI ve MACD hesapla
        deltas   = [close[i] - close[i-1] for i in range(1, n)]
        gains    = [max(d, 0) for d in deltas]
        losses   = [-min(d, 0) for d in deltas]
        avg_gain = _ewm_com(gains, 13)
        avg_loss = _ewm_com(losses, 13)
        rsi_all  = []
        for g, l in zip(avg_gain, avg_loss):
            rsi_all.append(100.0 if l == 0 else 100 - 100 / (1 + g / l))
        rsi_all = [None] + rsi_all  # index hizala

        ema12_all    = _ema(close, 12)
        ema26_all    = _ema(close, 26)
        macd_all     = [a - b for a, b in zip(ema12_all, ema26_all)]
        signal_all   = _ema(macd_all, 9)
        hist_all     = [m - s for m, s in zip(macd_all, signal_all)]

        # Backtest döngüsü
        islemler = []
        i = 30  # İlk 30 gün warmup

        while i < n - 5:
            rsi  = rsi_all[i]
            mh   = hist_all[i]
            mhp  = hist_all[i-1]

            # Basit AL koşulu: RSI < 40 + MACD yukarı kesiş veya RSI < 30
            al_sinyali = (
                (rsi and rsi < 40 and mh > 0 and mhp <= 0) or  # RSI normal + MACD kesiş
                (rsi and rsi < 30) or                           # Aşırı satım
                (rsi and rsi < 35 and mh > mhp and mh > 0)     # RSI düşük + MACD güçleniyor
            )

            if al_sinyali and mh is not None:
                giris_fiyat = close[i]
                stop_fiyat  = giris_fiyat * (1 - stop_pct / 100)
                hedef_fiyat = giris_fiyat * (1 + hedef_pct / 100)
                giris_tarihi = dates[i]

                # Çıkış: stop, hedef veya max 20 gün
                cikis_i   = None
                cikis_neden = 'sure_doldu'
                for j in range(i + 1, min(i + 21, n)):
                    if low[j] <= stop_fiyat:
                        cikis_i = j
                        cikis_neden = 'stop'
                        break
                    if high[j] >= hedef_fiyat:
                        cikis_i = j
                        cikis_neden = 'hedef'
                        break

                if cikis_i is None:
                    cikis_i = min(i + 20, n - 1)

                cikis_fiyat  = close[cikis_i]
                kz_pct       = round((cikis_fiyat - giris_fiyat) / giris_fiyat * 100, 2)
                giris_rsi    = round(rsi, 1) if rsi else 0
                giris_macd   = round(mh, 3)

                islemler.append({
                    'giris_tarihi':  giris_tarihi,
                    'cikis_tarihi':  dates[cikis_i],
                    'giris_fiyat':   round(giris_fiyat, 2),
                    'cikis_fiyat':   round(cikis_fiyat, 2),
                    'kz_pct':        kz_pct,
                    'neden':         cikis_neden,
                    'giris_rsi':     giris_rsi,
                    'giris_macd_hist': giris_macd,
                    'sure_gun':      cikis_i - i,
                })
                i = cikis_i + 1  # Kapatıldıktan sonra devam et
            else:
                i += 1

        # İstatistik
        if not islemler:
            return Response({
                'sembol': sembol,
                'mesaj': 'Bu dönemde hiç AL sinyali oluşmadı.',
                'islemler': [],
            })

        kazananlar = [t for t in islemler if t['kz_pct'] > 0]
        kaybedenler = [t for t in islemler if t['kz_pct'] <= 0]
        stop_sayisi  = len([t for t in islemler if t['neden'] == 'stop'])
        hedef_sayisi = len([t for t in islemler if t['neden'] == 'hedef'])
        ort_kz = round(mean([t['kz_pct'] for t in islemler]), 2)
        maks_kz = max(islemler, key=lambda t: t['kz_pct'])
        en_kotu = min(islemler, key=lambda t: t['kz_pct'])
        kazanma_orani = round(len(kazananlar) / len(islemler) * 100, 1)

        # Bileşik getiri simulasyonu (1000 TL başlangıç)
        bakiye = 1000.0
        for t in islemler:
            bakiye = bakiye * (1 + t['kz_pct'] / 100)
        bakiye = round(bakiye, 2)
        toplam_getiri = round((bakiye - 1000) / 1000 * 100, 1)

        return Response({
            'sembol':   sembol,
            'period':   period,
            'stop_pct': stop_pct,
            'hedef_pct': hedef_pct,
            'ozet': {
                'toplam_islem':      len(islemler),
                'kazananlar':        len(kazananlar),
                'kaybedenler':       len(kaybedenler),
                'stop_tetiklenen':   stop_sayisi,
                'hedef_tutan':       hedef_sayisi,
                'kazanma_orani_pct': kazanma_orani,
                'ortalama_kz_pct':   ort_kz,
                'en_iyi_pct':        maks_kz['kz_pct'],
                'en_kotu_pct':       en_kotu['kz_pct'],
                'baslangic_tl':      1000,
                'bitis_tl':          bakiye,
                'toplam_getiri_pct': toplam_getiri,
            },
            'islemler': islemler,
            'uyari': (
                'Backtest geçmiş performansa dayanır ve gelecek sonuçları garanti etmez. '
                'Bu analiz yatırım tavsiyesi değildir.'
            ),
        })

    except Exception as e:
        return Response({'error': f'Backtest hatası: {str(e)}'}, status=500)