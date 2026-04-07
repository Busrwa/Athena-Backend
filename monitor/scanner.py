"""
Athena Piyasa Tarayıcısı — Gelişmiş Versiyon
Multi-factor skorlama: Teknik + Fundamental + Hacim + Momentum
BIST hisseleri + altın + döviz izleme
"""
from stocks.services import (
    get_stock_data, get_technical_indicators, get_fundamental_data,
    POPULAR_BIST_STOCKS, get_commodity_data, get_forex_data
)
from portfolio.models import Portfolio, Watchlist
from .email_service import send_signal_alert
from django.conf import settings


# ─── Ana Skorlama Motoru ──────────────────────────────────────────────────────

def compute_score(tech: dict, stock: dict, fundamental: dict = None) -> tuple[int, list]:
    """
    Çok katmanlı AL/SAT skoru.
    Teknik (max ±14) + Fundamental (max ±5) + Hacim (max ±3) + Momentum (max ±3)
    Toplam: -25 ile +25 arasında
    """
    puan = 0
    gerekceler = []

    rsi         = tech.get('rsi')
    macd_hist   = tech.get('macd_histogram', 0) or 0
    macd_hist_p = tech.get('macd_hist_prev', macd_hist)
    trend       = tech.get('trend', 'yatay')
    macd_cross_up   = tech.get('macd_crossover', False)
    macd_cross_down = tech.get('macd_crossunder', False)
    bb_pos      = tech.get('bb_position', '')
    change      = stock.get('change_percent', 0)
    stoch_k     = tech.get('stoch_k', 50) or 50
    stoch_d     = tech.get('stoch_d', 50) or 50
    stoch_cross_up  = tech.get('stoch_crossover', False)
    stoch_cross_down= tech.get('stoch_crossunder', False)
    stoch_sig   = tech.get('stoch_signal', 'normal')
    will_r      = tech.get('williams_r', -50) or -50
    will_sig    = tech.get('williams_signal', 'normal')
    vol_ratio   = tech.get('volume_ratio', 1) or 1
    vol_sig     = tech.get('volume_signal', 'normal')
    obv_trend   = tech.get('obv_trend', 'yatay')
    macd_mom    = tech.get('macd_momentum', 'azaliyor')
    r5d         = tech.get('return_5d', 0) or 0
    r20d        = tech.get('return_20d', 0) or 0
    candle      = tech.get('candle_pattern', 'normal')
    atr_pct     = tech.get('atr_pct', 2) or 2
    bb_width    = tech.get('bb_width', 5) or 5

    # ── 1. RSI ────────────────────────────────────────────────────────────────
    if rsi:
        if rsi > 80:
            puan -= 3; gerekceler.append(f'🔴 RSI {rsi} — Aşırı alım (kritik)')
        elif rsi > 70:
            puan -= 2; gerekceler.append(f'🔴 RSI {rsi} — Aşırı alım bölgesi')
        elif rsi > 65:
            puan -= 1; gerekceler.append(f'🟡 RSI {rsi} — Aşırı alıma yaklaşıyor')
        elif rsi < 20:
            puan += 3; gerekceler.append(f'🟢 RSI {rsi} — Aşırı satım (kritik), güçlü toparlanma beklentisi')
        elif rsi < 30:
            puan += 2; gerekceler.append(f'🟢 RSI {rsi} — Aşırı satım bölgesi')
        elif rsi < 35:
            puan += 1; gerekceler.append(f'🟡 RSI {rsi} — Aşırı satıma yaklaşıyor')

    # ── 2. MACD ───────────────────────────────────────────────────────────────
    if macd_cross_up:
        puan += 3; gerekceler.append('🟢 MACD yukarı kesiş — Güçlü alım sinyali')
    elif macd_cross_down:
        puan -= 3; gerekceler.append('🔴 MACD aşağı kesiş — Güçlü satım sinyali')
    elif macd_hist > 0:
        if macd_mom == 'artiyor':
            puan += 2; gerekceler.append('🟢 MACD pozitif ve artıyor — Momentum güçleniyor')
        else:
            puan += 1; gerekceler.append('🟢 MACD pozitif momentum')
    elif macd_hist < 0:
        if macd_mom == 'azaliyor':
            puan -= 2; gerekceler.append('🔴 MACD negatif ve azalıyor — Baskı artıyor')
        else:
            puan -= 1; gerekceler.append('🔴 MACD negatif momentum')

    # ── 3. Trend ─────────────────────────────────────────────────────────────
    if trend == 'guclu_yukari':
        puan += 2; gerekceler.append('🟢 Güçlü yükseliş trendi (EMA20 > EMA50 > EMA200)')
    elif trend == 'yukari':
        puan += 1; gerekceler.append('🟢 Yükseliş trendi')
    elif trend == 'guclu_asagi':
        puan -= 2; gerekceler.append('🔴 Güçlü düşüş trendi (EMA20 < EMA50 < EMA200)')
    elif trend == 'asagi':
        puan -= 1; gerekceler.append('🔴 Düşüş trendi')

    # ── 4. Bollinger Bands ───────────────────────────────────────────────────
    if 'ust_band_ustunde' in bb_pos:
        puan -= 2; gerekceler.append('🔴 Bollinger üst bandı aştı — Aşırı uzanma')
    elif 'alt_band_altinda' in bb_pos:
        puan += 2; gerekceler.append('🟢 Bollinger alt bandı kırdı — Toparlanma beklentisi')

    # BB sıkışması → büyük hareket öncesi
    if bb_width < 3:
        gerekceler.append(f'⚡ Bollinger sıkışması (bant genişliği {bb_width}%) — Yakında sert hareket bekleniyor')

    # ── 5. Stochastic ────────────────────────────────────────────────────────
    if stoch_cross_up and stoch_sig == 'asiri_satim':
        puan += 2; gerekceler.append(f'🟢 Stochastic aşırı satımdan çıkış ({stoch_k:.0f}) — Alım sinyali')
    elif stoch_cross_down and stoch_sig == 'asiri_alim':
        puan -= 2; gerekceler.append(f'🔴 Stochastic aşırı alımdan çıkış ({stoch_k:.0f}) — Satım sinyali')
    elif stoch_sig == 'asiri_satim':
        puan += 1; gerekceler.append(f'🟡 Stochastic aşırı satım bölgesinde ({stoch_k:.0f})')
    elif stoch_sig == 'asiri_alim':
        puan -= 1; gerekceler.append(f'🟡 Stochastic aşırı alım bölgesinde ({stoch_k:.0f})')

    # ── 6. Williams %R ───────────────────────────────────────────────────────
    if will_sig == 'asiri_satim':
        puan += 1; gerekceler.append(f'🟢 Williams %R aşırı satım bölgesinde ({will_r})')
    elif will_sig == 'asiri_alim':
        puan -= 1; gerekceler.append(f'🔴 Williams %R aşırı alım bölgesinde ({will_r})')

    # ── 7. Hacim Analizi ─────────────────────────────────────────────────────
    if vol_sig in ('cok_yuksek', 'yuksek') and trend in ('yukari', 'guclu_yukari'):
        puan += 1; gerekceler.append(f'🟢 Yüksek hacimle yükseliş — Güçlü alım baskısı ({vol_ratio:.1f}x)')
    elif vol_sig in ('cok_yuksek', 'yuksek') and trend in ('asagi', 'guclu_asagi'):
        puan -= 1; gerekceler.append(f'🔴 Yüksek hacimle düşüş — Güçlü satış baskısı ({vol_ratio:.1f}x)')
    elif vol_sig == 'dusuk':
        gerekceler.append(f'🟡 Düşük hacim — Hareket güvenilirliği azaldı')

    if obv_trend == 'yukari' and trend in ('yukari', 'guclu_yukari'):
        puan += 1; gerekceler.append('🟢 OBV yükseliş — Akıllı para alıyor')
    elif obv_trend == 'asagi' and trend in ('asagi', 'guclu_asagi'):
        puan -= 1; gerekceler.append('🔴 OBV düşüş — Akıllı para satıyor')

    # ── 8. Mum Formasyonu ────────────────────────────────────────────────────
    if candle == 'cekic':
        puan += 1; gerekceler.append('🟢 Çekiç formasyonu — Dip dönüş sinyali')
    elif candle == 'asilan_adam':
        puan -= 1; gerekceler.append('🔴 Asılan adam formasyonu — Tepe dönüş riski')
    elif candle == 'doji':
        gerekceler.append('⚡ Doji formasyonu — Kararsızlık, yön değişimi olabilir')

    # ── 9. Fiyat Momentumu ───────────────────────────────────────────────────
    if r5d < -8:
        puan += 1; gerekceler.append(f'🟡 Son 5 gün %{r5d:.1f} — Aşırı satış sonrası fırsat?')
    elif r5d > 12:
        puan -= 1; gerekceler.append(f'🟡 Son 5 gün %{r5d:.1f} — Hızlı yükseliş, dikkatli ol')

    if change > 7:
        puan -= 1; gerekceler.append(f'🟡 Bugün %{change:.1f} yükseldi — Aşırı tepki riski')
    elif change < -6:
        puan += 1; gerekceler.append(f'🟡 Bugün %{change:.1f} düştü — Aşırı satış')

    # ── 10. Fundamental Skor (varsa) ─────────────────────────────────────────
    if fundamental and 'fundamental_score' in fundamental:
        fs = fundamental['fundamental_score']
        if fs >= 4:
            puan += 2; gerekceler.append(f'✅ Güçlü temel değerler (puan: {fs})')
        elif fs >= 2:
            puan += 1; gerekceler.append(f'✅ İyi temel değerler (puan: {fs})')
        elif fs <= -3:
            puan -= 2; gerekceler.append(f'⚠️ Zayıf temel değerler (puan: {fs})')
        elif fs <= -1:
            puan -= 1; gerekceler.append(f'⚠️ Orta temel değerler (puan: {fs})')
        # PE ve PB özel vurgu
        if fundamental.get('pe_ratio') and fundamental['pe_ratio'] < 8:
            gerekceler.append(f'✅ F/K {fundamental["pe_ratio"]} — çok cazip fiyat')
        if fundamental.get('dividend_yield') and fundamental['dividend_yield'] > 5:
            gerekceler.append(f'✅ Temettü verimi %{fundamental["dividend_yield"]}')

    return puan, gerekceler


def _get_signal_label(puan: int) -> str:
    if puan >= 6:   return 'GÜÇLÜ_AL'
    elif puan >= 3: return 'AL'
    elif puan <= -6: return 'GÜÇLÜ_SAT'
    elif puan <= -3: return 'SAT'
    else:            return 'BEKLE'


# ─── Ana Tarama Fonksiyonu ───────────────────────────────────────────────────

def scan_and_alert():
    """
    Tüm sembolleri tara, güçlü sinyallerde mail at.
    Portföy için stop-loss / hedef kontrolü yap.
    """
    threshold = getattr(settings, 'SIGNAL_ALERT_THRESHOLD', 3)
    alerts_sent = 0

    portfolio_symbols = list(Portfolio.objects.values_list('symbol', flat=True))
    watchlist_symbols = list(Watchlist.objects.values_list('symbol', flat=True))
    scan_symbols = list(set(portfolio_symbols + watchlist_symbols + POPULAR_BIST_STOCKS[:15]))

    print(f"[TARAMA] {len(scan_symbols)} sembol taranıyor...")

    for symbol in scan_symbols:
        try:
            stock = get_stock_data(symbol)
            if not stock or stock['price'] == 0:
                continue

            tech = get_technical_indicators(symbol)
            if not tech.get('rsi'):
                continue

            # Fundamental veri (sessizce dene)
            try:
                fund = get_fundamental_data(symbol)
            except:
                fund = None

            puan, gerekceler = compute_score(tech, stock, fund)

            if abs(puan) >= threshold:
                signal = _get_signal_label(puan)
                print(f"[SİNYAL] {symbol} → {signal} (skor: {puan})")
                sent = send_signal_alert(
                    symbol=symbol, signal=signal,
                    score=abs(puan), price=stock['price'],
                    reasons=gerekceler, tech=tech,
                    change_pct=stock['change_percent'],
                    fundamental=fund,
                )
                if sent:
                    alerts_sent += 1

            if symbol in portfolio_symbols:
                _check_portfolio_alerts(symbol, stock, tech, fund, puan, gerekceler)

        except Exception as e:
            print(f"[HATA] {symbol}: {e}")
            continue

    # Altın ve döviz özel kontrol
    _check_commodity_alerts()

    # Onaylanan aktif planları kontrol et (stop/hedef)
    _check_active_plans()

    print(f"[TARAMA TAMAMLANDI] {alerts_sent} mail gönderildi.")
    return alerts_sent


def _check_commodity_alerts():
    """Altın, döviz önemli hareketlerde uyar"""
    from .email_service import send_commodity_alert
    commodity_watch = [
        ('ALTIN_USD', 'emtia'),
        ('GUMUS_USD', 'emtia'),
        ('PETROL_WTI', 'emtia'),
    ]
    forex_watch = [
        ('USDTRY', 'forex'),
        ('EURTRY', 'forex'),
    ]
    all_watch = commodity_watch + forex_watch

    for name, category in all_watch:
        try:
            if category == 'emtia':
                data = get_commodity_data(name)
            else:
                data = get_forex_data(name)

            if not data:
                continue

            chg = data.get('change_percent', 0)
            # %2'den fazla hareket → uyar
            if abs(chg) >= 2:
                send_commodity_alert(name=name, data=data, category=category)
        except Exception as e:
            print(f"[EMTIA HATA] {name}: {e}")


def _check_portfolio_alerts(symbol, stock, tech, fund, puan, gerekceler):
    """Portföydeki hisse için stop-loss ve hedef fiyat kontrolü"""
    from .models import InvestmentPlan
    from .email_service import send_signal_alert

    try:
        holding = Portfolio.objects.get(symbol=symbol)
        current = stock['price']
        cost    = float(holding.avg_cost)
        pl_pct  = ((current - cost) / cost) * 100

        plan = InvestmentPlan.objects.filter(symbol=symbol, is_active=True).first()
        stop_pct   = float(plan.stop_loss_pct)    if plan else 8.0
        target_pct = float(plan.target_return_pct) if plan else 15.0

        if pl_pct <= -stop_pct:
            reasons = [
                f'🔴 STOP-LOSS TETİKLENDİ! Zarar: %{pl_pct:.1f}',
                f'Maliyet: {cost:.2f} TL → Güncel: {current:.2f} TL',
                f'Stop seviyesi: -%{stop_pct:.0f}',
                f'ATR Volatilite: %{tech.get("atr_pct", "?")}',
            ] + gerekceler[:2]
            send_signal_alert(symbol=symbol, signal='SAT', score=8,
                              price=current, reasons=reasons, tech=tech,
                              change_pct=stock['change_percent'], fundamental=fund)

        elif pl_pct >= target_pct:
            reasons = [
                f'🟢 HEDEF KARINA ULAŞILDI! Kâr: %{pl_pct:.1f}',
                f'Maliyet: {cost:.2f} TL → Güncel: {current:.2f} TL',
                f'Hedef: +%{target_pct:.0f} → SATIŞ değerlendir',
            ] + gerekceler[:2]
            send_signal_alert(symbol=symbol, signal='SAT', score=5,
                              price=current, reasons=reasons, tech=tech,
                              change_pct=stock['change_percent'], fundamental=fund)

        # Ara uyarı: %50 hedef yolunda
        elif pl_pct >= target_pct * 0.5 and pl_pct < target_pct:
            print(f"[BİLGİ] {symbol} hedefin %50'sinde, takipte. (K/Z: %{pl_pct:.1f})")

    except Portfolio.DoesNotExist:
        pass
    except Exception as e:
        print(f"[PORTFÖY KONTROL HATA] {symbol}: {e}")

def _check_active_plans():
    """
    Onaylanan tüm aktif planları kontrol et.
    Stop-loss veya hedef fiyata ulaşıldıysa SAT maili at.
    """
    from .models import InvestmentPlan
    from .email_service import send_signal_alert
    from stocks.services import get_stock_data

    planlar = InvestmentPlan.objects.filter(
        is_active=True
    ).exclude(athena_advice__startswith='ONAY_BEKLENIYOR')

    for plan in planlar:
        try:
            stock = get_stock_data(plan.symbol)
            if not stock or stock.get('price', 0) == 0:
                continue

            guncel = stock['price']
            giris = float(plan.entry_price) if plan.entry_price else None
            if not giris:
                continue

            kz_pct = ((guncel - giris) / giris) * 100
            stop_pct = float(plan.stop_loss_pct)
            hedef_pct = float(plan.target_return_pct)

            if kz_pct <= -stop_pct:
                # STOP-LOSS tetiklendi
                print(f"[⛔ STOP-LOSS] {plan.symbol} | Zarar: %{kz_pct:.1f}")
                send_signal_alert(
                    symbol=plan.symbol, signal='SAT', score=10,
                    price=guncel,
                    reasons=[
                        f"⛔ STOP-LOSS TETİKLENDİ — Zarar: %{kz_pct:.1f}",
                        f"Giriş: {giris:.2f} → Güncel: {guncel:.2f}",
                        f"Stop seviyesi: -%{stop_pct:.0f} aşıldı",
                        "🔴 Yapıkredi uygulamasından SAT!",
                    ],
                    tech={}, change_pct=stock['change_percent'], fundamental=None,
                )
                plan.is_active = False
                plan.athena_advice += f" | ⛔ STOP tetiklendi {guncel:.2f} TL"
                plan.save()

            elif kz_pct >= hedef_pct:
                # HEDEF'e ulaşıldı
                print(f"[🎯 HEDEF] {plan.symbol} | Kâr: %{kz_pct:.1f}")
                send_signal_alert(
                    symbol=plan.symbol, signal='SAT', score=8,
                    price=guncel,
                    reasons=[
                        f"🎯 HEDEF KARINA ULAŞILDI — Kâr: %{kz_pct:.1f}",
                        f"Giriş: {giris:.2f} → Güncel: {guncel:.2f}",
                        f"Hedef: +%{hedef_pct:.0f} tutturuldu",
                        "🟢 Yapıkredi uygulamasından SAT ve kârı al!",
                    ],
                    tech={}, change_pct=stock['change_percent'], fundamental=None,
                )
                plan.is_active = False
                plan.athena_advice += f" | 🎯 Hedef tutturuldu {guncel:.2f} TL"
                plan.save()

            elif kz_pct >= hedef_pct * 0.6:
                # Hedefe %60 yaklaştı — bilgi maili
                print(f"[🟡 HEDEFE YAKLAŞIYOR] {plan.symbol} | K/Z: %{kz_pct:.1f}")

        except Exception as e:
            print(f"[PLAN KONTROL HATA] {plan.symbol}: {e}")
