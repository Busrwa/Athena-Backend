from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings
from groq import Groq
from portfolio.models import Portfolio
from stocks.services import get_stock_data, get_technical_indicators
from news.views import fetch_kap_news

GROQ_MODEL = "llama-3.3-70b-versatile"

# Athena'nın temel kimliği — her istekte gönderilir
ATHENA_SYSTEM_PROMPT = """Sen Athena'sın — Türk borsası (BIST) uzmanı, kişisel yapay zeka yatırım danışmanısın.

KİMLİĞİN:
- Adın Athena. Bilgelik ve strateji tanrıçasından ilhamla adlandırıldın.
- 15+ yıllık BIST deneyimine sahip bir analist gibi düşünürsün.
- Teknik analiz (RSI, MACD, Bollinger, EMA) ve temel analizi birleştirirsin.
- KAP haberlerini ve piyasa sentiment'ini değerlendirirsin.
- Her zaman Türkçe yazarsın. Net, doğrudan ve eyleme dönüştürülebilir konuşursun.

ANALİZ PRENSİPLERİN:
1. RSI > 70 → Aşırı alım, SAT sinyali güçlü
2. RSI < 30 → Aşırı satım, AL fırsatı
3. MACD çapraz (yukarı) + pozitif histogram → Güçlü AL
4. MACD çapraz (aşağı) + negatif histogram → Güçlü SAT
5. Trend yukarı + RSI normal → TUT/AL güçlü
6. Trend aşağı + RSI yüksek → SAT
7. Bollinger üst bandı aştı → Aşırı uzanma, dikkat
8. Bollinger alt bandı kırdı → Toparlanma beklentisi

TAVSİYE FORMATIN (her hisse için):
**[SEMBOL] → [AL/SAT/TUT]** ⬆️/⬇️/➡️
- Güven skoru: X/10
- Gerekçe: (2-3 cümle somut)
- Risk: (ne zaman hatalı olabilirim)
- Hedef fiyat: (varsa teknik seviye)

ÖNEMLİ UYARILAR:
- "Bu analizler kişisel kullanım içindir, resmi yatırım tavsiyesi değildir" notu her analizin sonuna ekle.
- Asla kesin kazanç garantisi verme.
- Portföy çeşitlendirmesini her zaman hatırlat."""


def get_groq_client():
    return Groq(api_key=settings.GROQ_API_KEY)


def build_full_context():
    """
    Portföydeki her hisse için zengin veri seti oluşturur:
    - Güncel fiyat + değişim
    - Teknik indikatörler (RSI, MACD, Bollinger, EMA, S/R)
    - Son KAP haberleri
    """
    holdings = Portfolio.objects.all()
    if not holdings:
        return None, None

    portfolio_lines = []
    total_cost = 0.0
    total_value = 0.0
    portfolio_raw = []

    for holding in holdings:
        stock_data = get_stock_data(holding.symbol)
        if not stock_data:
            continue

        cost = float(holding.quantity * holding.avg_cost)
        value = float(holding.quantity) * stock_data['price']
        pl = value - cost
        pl_pct = (pl / cost * 100) if cost > 0 else 0

        total_cost += cost
        total_value += value

        # Teknik göstergeler
        tech = get_technical_indicators(holding.symbol)

        # KAP haberleri
        news_items = fetch_kap_news(symbol=holding.symbol, limit=5)
        if news_items:
            news_text = ' | '.join([n['title'][:80] for n in news_items[:3]])
        else:
            news_text = 'Son 24 saatte ilgili KAP bildirimi yok'

        line = (
            f"═══ {holding.symbol} ═══\n"
            f"  Pozisyon: {float(holding.quantity):.0f} adet | Maliyet: {float(holding.avg_cost):.2f} TL\n"
            f"  Güncel: {stock_data['price']:.2f} TL | Bugün: {stock_data['change_percent']:+.2f}%\n"
            f"  K/Z: {pl:+.2f} TL ({pl_pct:+.2f}%)\n"
            f"  RSI: {tech.get('rsi', '?')} | MACD hist: {tech.get('macd_histogram', '?')}\n"
            f"  Trend: {tech.get('trend', '?')} (güç: %{tech.get('trend_strength_pct', '?')})\n"
            f"  EMA20: {tech.get('ema20', '?')} | EMA50: {tech.get('ema50', '?')}\n"
            f"  Bollinger: Alt {tech.get('bb_lower', '?')} | Orta {tech.get('bb_mid', '?')} | Üst {tech.get('bb_upper', '?')}\n"
            f"  Destek: {tech.get('support', '?')} | Direnç: {tech.get('resistance', '?')}\n"
            f"  Teknik özet: {tech.get('summary', 'Veri yok')}\n"
            f"  KAP/Haberler: {news_text}"
        )
        portfolio_lines.append(line)

        portfolio_raw.append({
            'symbol': holding.symbol,
            'quantity': float(holding.quantity),
            'avg_cost': float(holding.avg_cost),
            'current_price': stock_data['price'],
            'cost': round(cost, 2),
            'value': round(value, 2),
            'profit_loss': round(pl, 2),
            'profit_loss_percent': round(pl_pct, 2),
            'change_percent_today': stock_data['change_percent'],
            'rsi': tech.get('rsi'),
            'trend': tech.get('trend'),
            'macd_histogram': tech.get('macd_histogram'),
            'tech_summary': tech.get('summary', ''),
        })

    if not portfolio_raw:
        return None, None

    total_pl = total_value - total_cost
    total_pl_pct = (total_pl / total_cost * 100) if total_cost > 0 else 0

    context_text = "\n\n".join(portfolio_lines)
    context_text += (
        f"\n\n{'═'*40}\n"
        f"PORTFÖY TOPLAM ÖZET:\n"
        f"  Toplam yatırım: {total_cost:.2f} TL\n"
        f"  Güncel değer: {total_value:.2f} TL\n"
        f"  Toplam K/Z: {total_pl:+.2f} TL ({total_pl_pct:+.2f}%)\n"
        f"  Hisse sayısı: {len(portfolio_raw)}"
    )

    return context_text, portfolio_raw


@api_view(['GET'])
def analyze_portfolio(request):
    """
    TAM PORTFÖY ANALİZİ — GET /api/advisor/analyze/
    RSI + MACD + Bollinger + KAP haberleri + fiyat → Groq ile analiz
    """
    context_text, portfolio_raw = build_full_context()

    if not portfolio_raw:
        return Response({'error': 'Portföyde hisse yok veya veri alınamadı'}, status=400)

    prompt = f"""Portföy verileri aşağıda. Kapsamlı analiz yap.

{context_text}

Şu başlıklar altında analiz et:

## 1. PORTFÖY GENEL SAĞLIĞI
Toplam K/Z değerlendirmesi, risk seviyesi, çeşitlendirme durumu.

## 2. HER HİSSE İÇİN ANALİZ
Her hisse için formatı uygula:
- K/Z durumu ve yorum
- RSI, MACD ve Bollinger yorumu
- Trend değerlendirmesi (EMA20 vs EMA50)
- Haber etkisi
- **TAVSİYE: AL / SAT / TUT** (güven skoru ve gerekçe)

## 3. RİSK UYARILARI
Portföydeki acil riskler. Hangi hisseler tehlikeli bölgede?

## 4. ÖNCELİKLİ EYLEM PLANI
Bugün veya bu hafta ne yapmalısın? Somut adımlar.

## 5. PORTFÖY OPTİMİZASYON ÖNERİSİ
Ağırlıklar doğru mu? Eksik çeşitlendirme var mı?"""

    try:
        client = get_groq_client()
        chat = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": ATHENA_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=3000,
        )
        return Response({
            'portfolio': portfolio_raw,
            'analysis': chat.choices[0].message.content,
            'model': GROQ_MODEL,
            'type': 'full_analysis',
        })

    except Exception as e:
        return _handle_groq_error(e)


@api_view(['POST'])
def ask_advisor(request):
    """
    SERBEST SORU (HAFIZALI) — POST /api/advisor/ask/
    Body: {
        "question": "MOGAN'ı satmalı mıyım?",
        "history": [  (opsiyonel — önceki mesajlar)
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]
    }
    """
    question = request.data.get('question', '').strip()
    history = request.data.get('history', [])  # Konuşma geçmişi

    if not question:
        return Response({'error': 'Soru boş olamaz'}, status=400)

    # Soru bir hisseyle ilgiliyse o hisseye özel teknik veri ekle
    context_text, _ = build_full_context()
    portfoy_bolumu = context_text if context_text else "Portföy henüz boş."

    # Hisse kodu geçiyor mu? Varsa ek teknik veri çek
    import re
    symbols_in_q = re.findall(r'\b([A-Z]{3,6})\b', question.upper())
    extra_tech = ""
    for sym in symbols_in_q[:2]:  # max 2 hisse için
        from stocks.services import get_technical_indicators, get_stock_data
        t = get_technical_indicators(sym)
        p = get_stock_data(sym)
        if t.get('rsi') and p:
            extra_tech += (
                f"\n\n{sym} güncel teknik verisi:\n"
                f"  Fiyat: {p['price']} TL ({p['change_percent']:+.2f}%)\n"
                f"  RSI: {t.get('rsi')} | MACD hist: {t.get('macd_histogram')}\n"
                f"  Trend: {t.get('trend')} | Bollinger: {t.get('bb_lower')}-{t.get('bb_upper')}\n"
                f"  {t.get('summary', '')}"
            )

    system_msg = ATHENA_SYSTEM_PROMPT
    user_prompt = (
        f"Mevcut portföy:\n{portfoy_bolumu}"
        f"{extra_tech}\n\n"
        f"Soru: {question}"
    )

    # Geçmiş mesajları dahil et (max son 10 mesaj — token tasarrufu)
    messages = [{"role": "system", "content": system_msg}]
    if history:
        messages.extend(history[-10:])
    messages.append({"role": "user", "content": user_prompt})

    try:
        client = get_groq_client()
        chat = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=1200,
        )
        answer = chat.choices[0].message.content
        return Response({
            'question': question,
            'answer': answer,
            'model': GROQ_MODEL,
        })

    except Exception as e:
        return _handle_groq_error(e)


@api_view(['GET'])
def quick_signal(request, symbol):
    """
    HIZLI SİNYAL (AI'sız, kural tabanlı) — GET /api/advisor/signal/MOGAN/
    RSI + MACD + Bollinger + trend → anlık AL/SAT/TUT
    API limiti harcamaz.
    """
    symbol = symbol.upper()
    stock = get_stock_data(symbol)
    if not stock:
        return Response({'error': f'{symbol} verisi alınamadı'}, status=404)

    tech = get_technical_indicators(symbol)
    rsi = tech.get('rsi')
    trend = tech.get('trend', '?')
    macd_hist = tech.get('macd_histogram', 0) or 0
    macd_cross_up = tech.get('macd_crossover', False)
    macd_cross_down = tech.get('macd_crossunder', False)
    bb_pos = tech.get('bb_position', '')
    change = stock['change_percent']

    # ─── Kural tabanlı sinyal motoru ──────────────────────────────────────
    puan = 0  # + = AL yönlü, - = SAT yönlü
    gerekceler = []

    # RSI kuralları
    if rsi:
        if rsi > 75:
            puan -= 3
            gerekceler.append(f'🔴 RSI {rsi} → Aşırı alım, satış baskısı beklenir')
        elif rsi > 65:
            puan -= 1
            gerekceler.append(f'🟡 RSI {rsi} → Aşırı alım bölgesine yakın')
        elif rsi < 25:
            puan += 3
            gerekceler.append(f'🟢 RSI {rsi} → Aşırı satım, toparlanma beklentisi')
        elif rsi < 35:
            puan += 1
            gerekceler.append(f'🟡 RSI {rsi} → Aşırı satım bölgesine yakın')
        else:
            gerekceler.append(f'⚪ RSI {rsi} → Normal bölge')

    # MACD kuralları
    if macd_cross_up:
        puan += 2
        gerekceler.append('🟢 MACD yukarı kesişti → Güçlü alım sinyali')
    elif macd_cross_down:
        puan -= 2
        gerekceler.append('🔴 MACD aşağı kesişti → Güçlü satım sinyali')
    elif macd_hist > 0:
        puan += 1
        gerekceler.append('🟢 MACD pozitif momentum sürüyor')
    elif macd_hist < 0:
        puan -= 1
        gerekceler.append('🔴 MACD negatif momentum sürüyor')

    # Trend kuralları
    if trend == 'yukari':
        puan += 1
        gerekceler.append(f'🟢 Trend yukarı (güç: %{tech.get("trend_strength_pct", "?")})')
    elif trend == 'asagi':
        puan -= 1
        gerekceler.append(f'🔴 Trend aşağı (güç: %{tech.get("trend_strength_pct", "?")})')

    # Bollinger kuralları
    if 'ust_band_ustunde' in bb_pos:
        puan -= 2
        gerekceler.append('🔴 Bollinger üst bandın üzerinde → Aşırı uzanma')
    elif 'alt_band_altinda' in bb_pos:
        puan += 2
        gerekceler.append('🟢 Bollinger alt bandın altında → Dip toparlanma beklentisi')

    # Günlük değişim
    if change > 6:
        puan -= 1
        gerekceler.append(f'🟡 Bugün %{change:.1f} yükseldi → Hızlı yükseliş sonrası dikkat')
    elif change < -5:
        puan += 1
        gerekceler.append(f'🟡 Bugün %{change:.1f} düştü → Aşırı satış, dip olabilir')

    # Puana göre karar
    if puan >= 3:
        sinyal = 'AL'
        guc = 'Güçlü'
        emoji = '🟢'
    elif puan >= 1:
        sinyal = 'AL'
        guc = 'Zayıf'
        emoji = '🟡'
    elif puan <= -3:
        sinyal = 'SAT'
        guc = 'Güçlü'
        emoji = '🔴'
    elif puan <= -1:
        sinyal = 'SAT'
        guc = 'Zayıf'
        emoji = '🟡'
    else:
        sinyal = 'TUT'
        guc = 'Nötr'
        emoji = '⚪'

    return Response({
        'symbol': symbol,
        'signal': sinyal,
        'signal_strength': guc,
        'signal_emoji': emoji,
        'score': puan,
        'price': stock['price'],
        'change_percent': change,
        'rsi': rsi,
        'trend': trend,
        'macd_histogram': macd_hist,
        'bb_position': bb_pos,
        'support': tech.get('support'),
        'resistance': tech.get('resistance'),
        'reasons': gerekceler,
        'note': 'Kural tabanlı hızlı sinyal. Tam AI analizi için /api/advisor/analyze/ kullanın.',
    })


@api_view(['GET'])
def market_overview(request):
    """
    BIST GENEL GÖRÜNÜMÜ — GET /api/advisor/market/
    Popüler hisseler için hızlı sinyal taraması
    """
    from stocks.services import POPULAR_BIST_STOCKS, get_stock_data, get_technical_indicators

    results = []
    al_count = sat_count = tut_count = 0

    for symbol in POPULAR_BIST_STOCKS[:15]:  # İlk 15 hisse
        stock = get_stock_data(symbol)
        if not stock:
            continue
        tech = get_technical_indicators(symbol)
        rsi = tech.get('rsi')
        macd_hist = tech.get('macd_histogram', 0) or 0
        trend = tech.get('trend', '?')

        # Basit skor
        puan = 0
        if rsi:
            if rsi > 70: puan -= 2
            elif rsi < 30: puan += 2
        if macd_hist > 0: puan += 1
        else: puan -= 1
        if trend == 'yukari': puan += 1
        else: puan -= 1

        if puan >= 2: signal = 'AL'; al_count += 1
        elif puan <= -2: signal = 'SAT'; sat_count += 1
        else: signal = 'TUT'; tut_count += 1

        results.append({
            'symbol': symbol,
            'price': stock['price'],
            'change_percent': stock['change_percent'],
            'rsi': rsi,
            'trend': trend,
            'signal': signal,
            'score': puan,
        })

    # En iyi ve en kötü hisseler
    results.sort(key=lambda x: x['score'], reverse=True)

    return Response({
        'summary': {
            'al': al_count,
            'sat': sat_count,
            'tut': tut_count,
            'market_sentiment': 'YUKARI' if al_count > sat_count else ('ASAGI' if sat_count > al_count else 'NOTR'),
        },
        'stocks': results,
        'top_al': [r for r in results if r['signal'] == 'AL'][:3],
        'top_sat': [r for r in sorted(results, key=lambda x: x['score'])[:3] if r['signal'] == 'SAT'],
    })


def _handle_groq_error(e):
    """Groq hata yönetimi"""
    err = str(e)
    if '429' in err or 'rate_limit' in err.lower():
        return Response({
            'error': 'Groq API istek limiti doldu. 1 dakika bekleyip tekrar dene.',
            'detail': 'RATE_LIMIT_EXCEEDED',
            'suggestion': 'Hızlı sinyal için /api/advisor/signal/{SYMBOL}/ endpoint\'ini kullan (AI limiti harcamaz)'
        }, status=429)
    if 'api_key' in err.lower() or 'authentication' in err.lower():
        return Response({
            'error': 'GROQ_API_KEY geçersiz veya .env dosyasında tanımlı değil.',
            'detail': 'AUTH_ERROR'
        }, status=500)
    return Response({'error': f'AI hatası: {err}'}, status=500)
