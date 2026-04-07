"""
Athena Monitor Views — Gelişmiş Yatırım Danışmanı
/api/monitor/ altındaki tüm endpoint'ler
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings
from stocks.services import (
    get_stock_data, get_technical_indicators, get_fundamental_data,
    get_market_overview, get_commodity_data, get_forex_data, get_crypto_data,
    POPULAR_BIST_STOCKS, COMMODITY_SYMBOLS, FOREX_SYMBOLS, CRYPTO_SYMBOLS,
)
from portfolio.models import Portfolio
from .models import AlertLog, InvestmentPlan
from .email_service import send_investment_advice_email
from .scanner import scan_and_alert, compute_score, _get_signal_label
from ai_advisor.views import GROQ_MODEL, ATHENA_SYSTEM_PROMPT, get_groq_client


@api_view(['POST'])
def run_scan(request):
    """Manuel tarama — POST /api/monitor/scan/"""
    alerts = scan_and_alert()
    return Response({
        'status': 'tarama tamamlandi',
        'alerts_sent': alerts,
        'email': settings.ATHENA_ALERT_EMAIL,
    })


@api_view(['GET'])
def alert_history(request):
    """Uyarı geçmişi — GET /api/monitor/alerts/"""
    symbol = request.query_params.get('symbol', '').upper()
    signal = request.query_params.get('signal', '').upper()
    qs = AlertLog.objects.all()
    if symbol: qs = qs.filter(symbol=symbol)
    if signal: qs = qs.filter(signal=signal)
    logs = qs[:100]
    data = [{
        'symbol': l.symbol, 'signal': l.signal, 'score': l.score,
        'price': float(l.price), 'email_sent': l.email_sent,
        'sent_at': l.sent_at, 'note': l.note,
    } for l in logs]
    return Response({'count': len(data), 'alerts': data})


@api_view(['GET'])
def market_dashboard(request):
    """
    Genel piyasa gösterge paneli — GET /api/monitor/market/
    BIST100, döviz, altın, kripto, öne çıkan hisseler
    """
    import django.utils.timezone as tz

    try:
        overview = get_market_overview()
    except Exception as e:
        overview = {'error': str(e)}

    # Öne çıkan hisseler (en yüksek ve en düşük değişim)
    top_movers = []
    for symbol in POPULAR_BIST_STOCKS[:20]:
        try:
            d = get_stock_data(symbol)
            if d and d.get('price', 0) > 0:
                top_movers.append({'symbol': symbol, 'price': d['price'],
                                   'change_percent': d['change_percent']})
        except:
            pass

    top_movers.sort(key=lambda x: x['change_percent'], reverse=True)
    gainers = top_movers[:5]
    losers  = top_movers[-5:][::-1]

    return Response({
        'overview': overview,
        'top_gainers': gainers,
        'top_losers': losers,
        'timestamp': tz.now().isoformat(),
    })


@api_view(['GET'])
def full_scan_results(request):
    """
    Sessiz tam tarama — sinyal göndermeden tüm skorları döner
    GET /api/monitor/scan/results/?limit=20
    """
    limit = int(request.query_params.get('limit', 20))
    min_score = int(request.query_params.get('min_score', 0))

    portfolio_symbols = list(Portfolio.objects.values_list('symbol', flat=True))
    watchlist_symbols = []
    try:
        from portfolio.models import Watchlist
        watchlist_symbols = list(Watchlist.objects.values_list('symbol', flat=True))
    except:
        pass

    scan_symbols = list(set(portfolio_symbols + watchlist_symbols + POPULAR_BIST_STOCKS[:25]))

    results = []
    for symbol in scan_symbols:
        try:
            stock = get_stock_data(symbol)
            if not stock or stock['price'] == 0:
                continue
            tech = get_technical_indicators(symbol)
            if not tech.get('rsi'):
                continue
            try:
                fund = get_fundamental_data(symbol)
            except:
                fund = None
            puan, gerekceler = compute_score(tech, stock, fund)
            if abs(puan) >= min_score:
                results.append({
                    'symbol': symbol,
                    'price': stock['price'],
                    'change_percent': stock['change_percent'],
                    'score': puan,
                    'signal': _get_signal_label(puan),
                    'rsi': tech.get('rsi'),
                    'trend': tech.get('trend'),
                    'volume_signal': tech.get('volume_signal'),
                    'reasons': gerekceler[:4],
                    'in_portfolio': symbol in portfolio_symbols,
                })
        except Exception as e:
            continue

    results.sort(key=lambda x: abs(x['score']), reverse=True)
    return Response({'count': len(results), 'results': results[:limit]})


@api_view(['GET'])
def commodity_overview(request):
    """
    Emtia/Döviz/Kripto özeti — GET /api/monitor/commodities/
    """
    result = {}
    for name in COMMODITY_SYMBOLS:
        d = get_commodity_data(name)
        if d: result[name] = d

    for pair in FOREX_SYMBOLS:
        d = get_forex_data(pair)
        if d: result[pair] = d

    for sym in CRYPTO_SYMBOLS:
        d = get_crypto_data(sym)
        if d: result[sym] = d

    return Response({'data': result, 'count': len(result)})


@api_view(['POST'])
def investment_advisor(request):
    """
    GELİŞMİŞ YATIRIM DANIŞMANI — POST /api/monitor/invest/
    Body: {
        "symbol": "THYAO",   (opsiyonel — boş bırakırsan en iyi hisse seçilir)
        "budget": 10000,
        "risk_level": "orta",    (dusuk / orta / yuksek)
        "strategy": "swing",     (scalp / swing / pozisyon / temetu)
        "market": "bist"         (bist / kripto / emtia / forex)
    }
    """
    symbol    = request.data.get('symbol', '').upper().strip()
    budget    = request.data.get('budget')
    risk_level= request.data.get('risk_level', 'orta').lower()
    strategy  = request.data.get('strategy', 'swing').lower()
    market    = request.data.get('market', 'bist').lower()

    if not budget:
        return Response({'error': 'budget zorunlu (örnek: 10000)'}, status=400)

    try:
        budget = float(budget)
        if budget < 100:
            return Response({'error': 'Minimum bütçe 100 TL'}, status=400)
    except Exception:
        return Response({'error': 'budget sayısal olmalı'}, status=400)

    # ── Piyasa seçimine göre sembol listesi ──────────────────────────────────
    if market == 'kripto' and not symbol:
        candidates = list(CRYPTO_SYMBOLS.keys())
    elif market == 'emtia' and not symbol:
        candidates = list(COMMODITY_SYMBOLS.keys())
    elif market == 'forex' and not symbol:
        candidates = list(FOREX_SYMBOLS.keys())
    else:
        candidates = POPULAR_BIST_STOCKS

    # ── Sembol belirtilmemişse en iyi hisse seç ──────────────────────────────
    if not symbol:
        best_symbol, best_score = None, -999
        for sym in candidates[:25]:
            try:
                stock = get_stock_data(sym)
                if not stock or stock['price'] == 0:
                    continue
                tech = get_technical_indicators(sym)
                if not tech.get('rsi'):
                    continue
                try:
                    fund = get_fundamental_data(sym)
                except:
                    fund = None
                puan, _ = compute_score(tech, stock, fund)
                if puan > best_score:
                    best_score = puan
                    best_symbol = sym
            except:
                continue
        if not best_symbol:
            return Response({'error': 'Uygun hisse bulunamadı, piyasa verisi alınamıyor'}, status=500)
        symbol = best_symbol

    # ── Seçilen hisse için veri ──────────────────────────────────────────────
    stock = get_stock_data(symbol)
    tech  = get_technical_indicators(symbol)
    try:
        fund = get_fundamental_data(symbol)
    except:
        fund = {}

    if not stock or stock['price'] == 0:
        return Response({'error': f'{symbol} verisi alınamadı'}, status=404)

    price = stock['price']
    puan, gerekceler = compute_score(tech, stock, fund)
    signal = _get_signal_label(puan)

    # ── Risk parametreleri (strateji bazlı) ──────────────────────────────────
    risk_params = {
        'dusuk':  {'stop': 4,  'target': 8,  'allocation': 0.60},
        'orta':   {'stop': 8,  'target': 15, 'allocation': 0.80},
        'yuksek': {'stop': 15, 'target': 30, 'allocation': 1.00},
    }
    strategy_params = {
        'scalp':     {'stop_mult': 0.5, 'target_mult': 0.5,  'desc': 'Kısa vadeli (günlük)'},
        'swing':     {'stop_mult': 1.0, 'target_mult': 1.0,  'desc': 'Orta vadeli (haftalık)'},
        'pozisyon':  {'stop_mult': 1.5, 'target_mult': 2.0,  'desc': 'Uzun vadeli (aylık)'},
        'temetu':    {'stop_mult': 1.2, 'target_mult': 3.0,  'desc': 'Temettü & büyüme'},
    }
    rp = risk_params.get(risk_level, risk_params['orta'])
    sp = strategy_params.get(strategy, strategy_params['swing'])

    # ATR tabanlı dinamik stop (daha akıllı)
    atr     = tech.get('atr', price * rp['stop'] / 100)
    atr_pct = tech.get('atr_pct', rp['stop'])

    final_stop_pct   = max(rp['stop'] * sp['stop_mult'], atr_pct * 1.5)
    final_target_pct = rp['target'] * sp['target_mult']

    investable  = budget * rp['allocation']
    qty         = int(investable / price)
    actual_cost = qty * price

    if qty < 1:
        return Response({
            'error': f'{symbol} fiyatı {price:.2f} TL — {budget:.0f} TL bütçeyle en az 1 adet alınamıyor'
        }, status=400)

    stop_price   = round(price * (1 - final_stop_pct / 100), 2)
    target_price = round(price * (1 + final_target_pct / 100), 2)
    risk_reward  = round(final_target_pct / final_stop_pct, 2)

    # Pivot destek/direnç'e göre stop ayarı
    pivot_support = tech.get('s1', stop_price)
    if pivot_support and pivot_support < price and pivot_support > stop_price:
        stop_price = round(min(stop_price, pivot_support * 0.99), 2)

    # ── Groq derin analiz ────────────────────────────────────────────────────
    fund_summary = ''
    if fund and fund.get('pe_ratio'):
        fund_summary = f"""
Temel Veriler:
- F/K: {fund.get('pe_ratio','?')} | PD/DD: {fund.get('pb_ratio','?')}
- ROE: %{fund.get('roe','?')} | Temettü: %{fund.get('dividend_yield','?')}
- Net Marj: %{fund.get('net_margin','?')} | Borç/Özkaynak: {fund.get('debt_to_equity','?')}
- Kâr büyümesi: %{fund.get('earnings_growth','?')}
- Sektör: {fund.get('sector','?')} — {fund.get('industry','?')}
Temel Notlar: {', '.join(fund.get('fundamental_notes',[])[:3])}
"""

    prompt = f"""Yatırım analizi talebi:
Hisse: {symbol} | Bütçe: {budget:,.2f} TL | Risk: {risk_level} | Strateji: {strategy} ({sp['desc']})

Anlık Durum:
- Fiyat: {price:.2f} TL | Değişim: {stock['change_percent']:+.2f}% bugün
- Alınacak: {qty} adet @ {actual_cost:,.2f} TL maliyet
- Stop-Loss: {stop_price:.2f} TL (-%{final_stop_pct:.1f})
- Hedef: {target_price:.2f} TL (+%{final_target_pct:.1f})
- Risk/Getiri oranı: 1/{risk_reward:.1f}
- Sinyal: {signal} (skor: {puan:+d}/25)

Teknik Durum:
- RSI: {tech.get('rsi','?')} | Stochastic: {tech.get('stoch_k','?')} | Williams %R: {tech.get('williams_r','?')}
- MACD hist: {tech.get('macd_histogram','?')} ({tech.get('macd_momentum','?')})
- Trend: {tech.get('trend','?')} | EMA20: {tech.get('ema20','?')} / EMA50: {tech.get('ema50','?')}
- Bollinger: {tech.get('bb_lower','?')} — {tech.get('bb_upper','?')} | Pozisyon: {tech.get('bb_position','?')}
- ATR: {tech.get('atr','?')} TL (%{tech.get('atr_pct','?')})
- Hacim: {tech.get('volume_signal','?')} ({tech.get('volume_ratio','?')}x ortalama)
- OBV: {tech.get('obv_trend','?')} | Mum: {tech.get('candle_pattern','?')}
- 5G getiri: %{tech.get('return_5d','?')} | 20G: %{tech.get('return_20d','?')} | 60G: %{tech.get('return_60d','?')}
- Destek: {tech.get('support','?')} | Direnç: {tech.get('resistance','?')}
- Pivot: {tech.get('pivot','?')} | R1: {tech.get('r1','?')} | S1: {tech.get('s1','?')}

{fund_summary}

Sinyal gerekçeleri: {', '.join(gerekceler[:5])}

Lütfen şunları belirt (Türkçe, net ve somut):

1. **GİRİŞ KARARI**: Bu hisseye şu an girmek akıllıca mı? Neden? (1-2 cümle)
2. **GİRİŞ STRATEJİSİ**: Hepsini birden mi al, kademeli mi? (örn: %50 şimdi, %50 {price*0.97:.2f} TL'de)
3. **STOP-LOSS**: {stop_price:.2f} TL mantıklı mı? Daha iyi bir seviye var mı?
4. **HEDEF**: {target_price:.2f} TL ({final_target_pct:.0f}%) gerçekçi mi? Kısmi kâr alım seviyeleri?
5. **SÜRE**: Kaç gün/hafta/ay beklenmeli?
6. **EN BÜYÜK RİSK**: 1 şey söyle.
7. **GENEL NOT**: Bu yatırımı 10 üzerinden kaç puan verirsin ve neden?

Kısa ve net tut. Gereksiz giriş cümlesi kullanma."""

    try:
        client = get_groq_client()
        chat = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": ATHENA_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.15,
            max_tokens=2000,
        )
        advice = chat.choices[0].message.content
    except Exception as e:
        advice = f"AI analizi alınamadı: {e}"

    # ── Plan DB'ye kaydet ────────────────────────────────────────────────────
    InvestmentPlan.objects.update_or_create(
        symbol=symbol,
        defaults={
            'budget_tl': budget,
            'entry_price': price,
            'target_return_pct': final_target_pct,
            'stop_loss_pct': final_stop_pct,
            'is_active': True,
            'athena_advice': advice[:1500],
        }
    )

    # ── Mail gönder ──────────────────────────────────────────────────────────
    send_investment_advice_email(
        symbol=symbol, budget=budget, advice=advice,
        recommended_qty=qty, entry_price=price,
        stop_price=stop_price, target_price=target_price,
        signal_score=puan, fundamental=fund,
    )

    return Response({
        'symbol': symbol,
        'signal': signal,
        'signal_score': puan,
        'signal_reasons': gerekceler,
        'budget': budget,
        'price': price,
        'change_today': stock['change_percent'],
        'recommended_quantity': qty,
        'estimated_cost': round(actual_cost, 2),
        'remaining_cash': round(budget - actual_cost, 2),
        'strategy': strategy,
        'risk_level': risk_level,
        # Fiyat seviyeleri
        'stop_loss_price': stop_price,
        'stop_loss_pct': round(final_stop_pct, 1),
        'target_price': target_price,
        'target_pct': round(final_target_pct, 1),
        'risk_reward_ratio': f'1/{risk_reward}',
        # Teknik özet
        'technical_summary': {
            'rsi': tech.get('rsi'),
            'trend': tech.get('trend'),
            'macd_crossover': tech.get('macd_crossover'),
            'stoch_signal': tech.get('stoch_signal'),
            'volume_signal': tech.get('volume_signal'),
            'bb_position': tech.get('bb_position'),
            'atr_pct': tech.get('atr_pct'),
        },
        # Fundamental özet
        'fundamental_summary': {
            'pe_ratio': fund.get('pe_ratio') if fund else None,
            'pb_ratio': fund.get('pb_ratio') if fund else None,
            'roe': fund.get('roe') if fund else None,
            'dividend_yield': fund.get('dividend_yield') if fund else None,
            'fundamental_score': fund.get('fundamental_score', 0) if fund else 0,
        },
        'advice': advice,
        'plan_status': 'izlemeye_alindi',
        'email_sent': True,
        'note': f'Plan aktif — stop -%{final_stop_pct:.1f}, hedef +%{final_target_pct:.1f}, R/R=1/{risk_reward}'
    })


@api_view(['GET'])
def active_plans(request):
    """Aktif planlar — GET /api/monitor/plans/"""
    plans = InvestmentPlan.objects.filter(is_active=True)
    result = []
    for p in plans:
        stock = get_stock_data(p.symbol)
        current = stock['price'] if stock else None
        entry   = float(p.entry_price) if p.entry_price else None
        pl_pct  = ((current - entry) / entry * 100) if (current and entry) else None
        stop_pct   = float(p.stop_loss_pct)
        target_pct = float(p.target_return_pct)

        status = 'beklemede'
        if pl_pct:
            if pl_pct <= -stop_pct:
                status = '🔴 stop_loss_bolgesi'
            elif pl_pct >= target_pct:
                status = '🟢 hedef_bolgesi'
            elif pl_pct >= target_pct * 0.5:
                status = '🟡 hedefe_yaklasıyor'

        result.append({
            'symbol': p.symbol,
            'budget': float(p.budget_tl),
            'entry_price': entry,
            'current_price': current,
            'pl_pct': round(pl_pct, 2) if pl_pct else None,
            'status': status,
            'stop_loss_pct': stop_pct,
            'target_pct': target_pct,
            'stop_price': round(entry * (1 - stop_pct / 100), 2) if entry else None,
            'target_price': round(entry * (1 + target_pct / 100), 2) if entry else None,
            'created_at': p.created_at,
        })
    return Response({'count': len(result), 'plans': result})


@api_view(['POST'])
def deactivate_plan(request, symbol):
    """Plan durdur — POST /api/monitor/plans/THYAO/deactivate/"""
    symbol = symbol.upper()
    updated = InvestmentPlan.objects.filter(symbol=symbol, is_active=True).update(is_active=False)
    if updated:
        return Response({'status': f'{symbol} planı durduruldu'})
    return Response({'error': 'Aktif plan bulunamadı'}, status=404)