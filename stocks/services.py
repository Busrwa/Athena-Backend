"""
Athena — Piyasa Veri Servisi
Hisseler, altın, gümüş, döviz, kripto, emtia
Teknik analiz: RSI, MACD, Bollinger, Stochastic, ATR, Williams %R, OBV, VWAP
Fundamental analiz: F/K, PD/DD, ROE, temettü verimi
"""
import yfinance as yf
import time
from datetime import datetime

# ─── Sembol Listeleri ─────────────────────────────────────────────────────────

# Geriye dönük uyumluluk için eski liste (kısa)
POPULAR_BIST_STOCKS = [
    'THYAO', 'GARAN', 'AKBNK', 'EREGL', 'BIMAS',
    'ASELS', 'KRDMD', 'TUPRS', 'SISE', 'KCHOL',
    'MOGAN', 'FROTO', 'TOASO', 'PGSUS', 'TAVHL',
    'YKBNK', 'HEKTS', 'PETKM', 'SAHOL', 'VESTL',
    'TKFEN', 'MGROS', 'ARCLK', 'DOHOL',
    'ENKAI', 'EKGYO', 'KOZAL', 'KONTR', 'TCELL',
    'ISCTR', 'VAKBN', 'HALKB', 'TTKOM', 'LOGO',
    'NTHOL', 'ODAS', 'EUPWR', 'MAVI', 'BRSAN',
]

# Kapsamlı BIST hisse listesi — tüm taranan semboller
# yfinance üzerinden .IS uzantısıyla çekiliyor
ALL_BIST_STOCKS = [
    # ── BIST30 ─────────────────────────────────────────────────────────────
    'THYAO', 'GARAN', 'AKBNK', 'EREGL', 'BIMAS',
    'ASELS', 'KRDMD', 'TUPRS', 'SISE', 'KCHOL',
    'FROTO', 'TOASO', 'PGSUS', 'TAVHL', 'YKBNK',
    'SAHOL', 'ARCLK', 'ENKAI', 'EKGYO', 'TCELL',
    'ISCTR', 'VAKBN', 'HALKB', 'TTKOM', 'KOZAL',
    'KONTR', 'PETKM', 'MGROS', 'DOHOL', 'AKSEN',

    # ── BIST100 ────────────────────────────────────────────────────────────
    'HEKTS', 'VESTL', 'TKFEN', 'LOGO', 'NTHOL',
    'ODAS',  'EUPWR', 'MAVI',  'BRSAN', 'MOGAN',
    'AEFES', 'ALARK', 'ANACM', 'BERA',  'BTCIM',
    'CIMSA', 'CLEBI', 'CWENE', 'DOAS',  'EGEEN',
    'ENJSA', 'EREGL', 'FENER', 'FLAP',  'GESAN',
    'GSDHO', 'GUBRF', 'INDES', 'ISGYO', 'ISMEN',
    'IZENR', 'JANTS', 'KAREL', 'KARTN', 'KATMR',
    'KAYSE', 'KCAER', 'KENT',  'KLRHO', 'KMPUR',
    'KNFRT', 'KONYA', 'KOZAA', 'KRDMB', 'KRONT',
    'KRPLS', 'KRSAN', 'KRVGD', 'KTSKR', 'KUTPO',
    'LMKDC', 'LUKSK', 'LYDHO', 'MACKO', 'MAKIM',
    'MAKTK', 'MANAS', 'MEGMT', 'MEPET', 'MERCN',
    'MERIT', 'MERKO', 'METRO', 'MIATK', 'MIPAZ',
    'MMCAS', 'MOBTL', 'MPARK', 'MSGYO', 'MTRKS',
    'NATEN', 'NETAS', 'NTTUR', 'NUGYO', 'NUHCM',
    'NVSN',  'OBASE', 'ODINE', 'ONCSM', 'ORCAY',
    'ORGE',  'OSMEN', 'OSTIM', 'OTKAR', 'OYAKC',
    'OYLUM', 'OZGYO', 'OZKGY', 'OZRDN', 'PAGYO',
    'PAPIL', 'PARSN', 'PASEU', 'PCILT', 'PEHOL',
    'PENGD', 'PETUN', 'PKART', 'PNLSN', 'POLHO',
    'PRDGS', 'PRKAB', 'PRKME', 'PRZMA', 'PSDTC',
    'QUAGR', 'RAYSG', 'RHEAG', 'RNPOL', 'RODRG',
    'RTALB', 'RUBNS', 'RYSAS', 'SAFKR', 'SAGYO',
    'SARKY', 'SASA',  'SELEC', 'SEYKM', 'SILVR',
    'SISE',  'SKBNK', 'SNGYO', 'SNKRN', 'SNPAM',
    'SODSN', 'SOKE',  'SOKM',  'SONME', 'SRVGY',
    'SUMAS', 'SUWEN', 'TATGD', 'TATEN', 'TAVHL',
    'TBORG', 'TDGYO', 'TEKTU', 'TEZOL', 'TGSAS',
    'TKFEN', 'TKNSA', 'TLMAN', 'TMSN',  'TNZTP',
    'TOASO', 'TRCAS', 'TRGYO', 'TRILC', 'TSPOR',
    'TTRAK', 'TUCLK', 'TUDDF', 'TUKAS', 'TURGZ',
    'TURSG', 'ULKER', 'UMPAS', 'UNYEC', 'USAK',
    'UZERB', 'VBTS',  'VERUS', 'VESTL', 'VKGYO',
    'VKING', 'YAPRK', 'YATAS', 'YAYLA', 'YGYO',
    'YKSLN', 'YONGA', 'YUNSA', 'ZOREN', 'ZRGYO',
]

# Altın, gümüş, döviz, kripto sembolleri
COMMODITY_SYMBOLS = {
    'ALTIN_USD':  'GC=F',   # Altın Vadeli (USD/ons)
    'GUMUS_USD':  'SI=F',   # Gümüş Vadeli (USD/ons)
    'PETROL_WTI': 'CL=F',   # Ham Petrol WTI
    'DOGALGAZ':   'NG=F',   # Doğalgaz
    'BAKIR':      'HG=F',   # Bakır
    'PLATIN':     'PL=F',   # Platin
    'PALMIYE':    'KO=F',   # Palm Yağı
    'MISIR':      'ZC=F',   # Mısır
    'BUGDAY':     'ZW=F',   # Buğday
}

FOREX_SYMBOLS = {
    'USDTRY': 'USDTRY=X',
    'EURTRY': 'EURTRY=X',
    'GBPTRY': 'GBPTRY=X',
    'JPYTRY': 'JPYTRY=X',
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    'CHFTRY': 'CHFTRY=X',
}

CRYPTO_SYMBOLS = {
    'BTC':  'BTC-USD',
    'ETH':  'ETH-USD',
    'BNB':  'BNB-USD',
    'SOL':  'SOL-USD',
    'AVAX': 'AVAX-USD',
    'XRP':  'XRP-USD',
    'ADA':  'ADA-USD',
    'DOT':  'DOT-USD',
    'LINK': 'LINK-USD',
    'MATIC':'MATIC-USD',
}

# Endeksler
INDEX_SYMBOLS = {
    'BIST100':  'XU100.IS',
    'BIST30':   'XU030.IS',
    'SP500':    '^GSPC',
    'NASDAQ':   '^IXIC',
    'DAX':      '^GDAXI',
    'GOLD_TR':  'GLDTR.IS',   # Altın ETF BIST
}

# Tarama için tüm sembol kategorileri
ALL_SCAN_SYMBOLS = {
    'hisse':   ALL_BIST_STOCKS,
    'emtia':   list(COMMODITY_SYMBOLS.keys()),
    'doviz':   list(FOREX_SYMBOLS.keys()),
    'kripto':  list(CRYPTO_SYMBOLS.keys()),
}

# ─── Bellek Cache ─────────────────────────────────────────────────────────────
_price_cache: dict[str, dict] = {}
_tech_cache:  dict[str, dict] = {}
_fund_cache:  dict[str, dict] = {}
_PRICE_TTL = 180    # 3 dakika
_TECH_TTL  = 600    # 10 dakika
_FUND_TTL  = 3600   # 1 saat


def _cache_get(store: dict, key: str, ttl: int):
    entry = store.get(key)
    if entry and (time.time() - entry['ts']) < ttl:
        return entry['data']
    return None


def _cache_set(store: dict, key: str, data: dict):
    store[key] = {'data': data, 'ts': time.time()}


# ─── Hisse Verisi ─────────────────────────────────────────────────────────────

def get_stock_data(symbol: str) -> dict | None:
    """Hisse fiyat verisi — 3 dk cache"""
    cached = _cache_get(_price_cache, symbol, _PRICE_TTL)
    if cached:
        return cached

    try:
        # Özel semboller
        yf_symbol = symbol
        if symbol in FOREX_SYMBOLS:
            yf_symbol = FOREX_SYMBOLS[symbol]
        elif symbol in CRYPTO_SYMBOLS:
            yf_symbol = CRYPTO_SYMBOLS[symbol]
        elif symbol in COMMODITY_SYMBOLS:
            yf_symbol = COMMODITY_SYMBOLS[symbol]
        elif symbol in INDEX_SYMBOLS:
            yf_symbol = INDEX_SYMBOLS[symbol]
        else:
            yf_symbol = f"{symbol}.IS"

        ticker = yf.Ticker(yf_symbol)
        info = ticker.fast_info

        price = float(info.last_price or 0)
        prev_close = float(info.previous_close or 0)
        change_pct = round(((price - prev_close) / prev_close) * 100, 2) if prev_close else 0.0

        data = {
            'symbol':         symbol,
            'yf_symbol':      yf_symbol,
            'price':          round(price, 4 if price < 1 else 2),
            'previous_close': round(prev_close, 2),
            'change_percent': change_pct,
            'volume':         int(info.three_month_average_volume or 0),
            'market_cap':     int(info.market_cap or 0),
            'cached':         False,
            'updated_at':     datetime.now().isoformat(),
        }
        _cache_set(_price_cache, symbol, data)
        return data

    except Exception as e:
        print(f"Fiyat hatası ({symbol}): {e}")
        old = _price_cache.get(symbol)
        if old:
            d = old['data'].copy()
            d['cached'] = True
            return d
        return None


def get_commodity_data(name: str) -> dict | None:
    """Altın, gümüş, petrol vb. emtia verisi"""
    yf_sym = COMMODITY_SYMBOLS.get(name)
    if not yf_sym:
        return None
    try:
        t = yf.Ticker(yf_sym)
        info = t.fast_info
        price = float(info.last_price or 0)
        prev = float(info.previous_close or 0)
        chg = round(((price - prev) / prev) * 100, 2) if prev else 0
        return {'name': name, 'yf_symbol': yf_sym, 'price': round(price, 2),
                'previous_close': round(prev, 2), 'change_percent': chg}
    except Exception as e:
        print(f"Emtia hatası ({name}): {e}")
        return None


def get_forex_data(pair: str = 'USDTRY') -> dict | None:
    """Döviz kuru"""
    yf_sym = FOREX_SYMBOLS.get(pair, f"{pair}=X")
    try:
        t = yf.Ticker(yf_sym)
        info = t.fast_info
        price = float(info.last_price or 0)
        prev = float(info.previous_close or 0)
        chg = round(((price - prev) / prev) * 100, 2) if prev else 0
        return {'pair': pair, 'rate': round(price, 4), 'previous_close': round(prev, 4),
                'change_percent': chg}
    except Exception as e:
        print(f"Döviz hatası ({pair}): {e}")
        return None


def get_crypto_data(symbol: str) -> dict | None:
    """Kripto para verisi"""
    yf_sym = CRYPTO_SYMBOLS.get(symbol, f"{symbol}-USD")
    try:
        t = yf.Ticker(yf_sym)
        info = t.fast_info
        price = float(info.last_price or 0)
        prev = float(info.previous_close or 0)
        chg = round(((price - prev) / prev) * 100, 2) if prev else 0
        return {'symbol': symbol, 'price_usd': round(price, 2), 'previous_close': round(prev, 2),
                'change_percent': chg}
    except Exception as e:
        print(f"Kripto hatası ({symbol}): {e}")
        return None


def get_market_overview() -> dict:
    """Genel piyasa özeti: BIST100, döviz, altın, kripto"""
    result = {}

    # BIST endeksler
    for name, sym in INDEX_SYMBOLS.items():
        try:
            t = yf.Ticker(sym)
            fi = t.fast_info
            p = float(fi.last_price or 0)
            pr = float(fi.previous_close or 0)
            chg = round(((p - pr) / pr) * 100, 2) if pr else 0
            if p > 0:
                result[name] = {'price': round(p, 2), 'change_percent': chg}
        except Exception as e:
            print(f"Endeks hatası ({name}): {e}")

    # Döviz
    for pair in ['USDTRY', 'EURTRY', 'EURUSD']:
        try:
            d = get_forex_data(pair)
            if d and d.get('rate', 0) > 0:
                result[pair] = d
        except Exception as e:
            print(f"Döviz hatası ({pair}): {e}")

    # Altın/Gümüş/Petrol
    for com in ['ALTIN_USD', 'GUMUS_USD', 'PETROL_WTI']:
        try:
            d = get_commodity_data(com)
            if d and d.get('price', 0) > 0:
                result[com] = d
        except Exception as e:
            print(f"Emtia hatası ({com}): {e}")

    # Ana kripto
    for crypto in ['BTC', 'ETH']:
        try:
            d = get_crypto_data(crypto)
            if d and d.get('price_usd', 0) > 0:
                result[crypto] = d
        except Exception as e:
            print(f"Kripto hatası ({crypto}): {e}")

    return result


# ─── Fundamental Analiz ───────────────────────────────────────────────────────

def get_fundamental_data(symbol: str) -> dict:
    """
    Şirket temelleri: F/K, PD/DD, ROE, ROA, temettü, büyüme, borç/özsermaye
    """
    cached = _cache_get(_fund_cache, symbol, _FUND_TTL)
    if cached:
        return cached

    try:
        ticker = yf.Ticker(f"{symbol}.IS")
        info = ticker.info

        pe      = info.get('trailingPE')
        pb      = info.get('priceToBook')
        ps      = info.get('priceToSalesTrailing12Months')
        roe     = info.get('returnOnEquity')
        roa     = info.get('returnOnAssets')
        debt_eq = info.get('debtToEquity')
        div_yld = info.get('dividendYield')
        eps     = info.get('trailingEps')
        rev_g   = info.get('revenueGrowth')
        earn_g  = info.get('earningsGrowth')
        curr_r  = info.get('currentRatio')
        gross_m = info.get('grossMargins')
        oper_m  = info.get('operatingMargins')
        net_m   = info.get('profitMargins')
        mkt_cap   = info.get('marketCap')
        sector    = info.get('sector', '')
        industry  = info.get('industry', '')
        employees = info.get('fullTimeEmployees')

        fund_score = 0
        fund_notes = []

        if pe:
            if pe < 8:
                fund_score += 3; fund_notes.append(f'✅ F/K {pe:.1f} — çok ucuz')
            elif pe < 15:
                fund_score += 2; fund_notes.append(f'✅ F/K {pe:.1f} — makul')
            elif pe < 25:
                fund_score += 1; fund_notes.append(f'🟡 F/K {pe:.1f} — orta')
            elif pe > 40:
                fund_score -= 2; fund_notes.append(f'⚠️ F/K {pe:.1f} — pahalı')
            else:
                fund_notes.append(f'🔵 F/K {pe:.1f}')

        if pb:
            if pb < 1:
                fund_score += 2; fund_notes.append(f'✅ PD/DD {pb:.2f} — defter değerinin altında')
            elif pb < 2:
                fund_score += 1; fund_notes.append(f'✅ PD/DD {pb:.2f} — makul')
            elif pb > 5:
                fund_score -= 1; fund_notes.append(f'⚠️ PD/DD {pb:.2f} — yüksek')

        if roe:
            roe_pct = roe * 100
            if roe_pct > 20:
                fund_score += 2; fund_notes.append(f'✅ ROE %{roe_pct:.1f} — yüksek karlılık')
            elif roe_pct > 10:
                fund_score += 1; fund_notes.append(f'✅ ROE %{roe_pct:.1f} — iyi')
            elif roe_pct < 0:
                fund_score -= 2; fund_notes.append(f'🔴 ROE %{roe_pct:.1f} — zarar ediyor')

        if div_yld:
            dy = div_yld * 100
            if dy > 5:
                fund_score += 2; fund_notes.append(f'✅ Temettü %{dy:.1f} — yüksek verim')
            elif dy > 2:
                fund_score += 1; fund_notes.append(f'✅ Temettü %{dy:.1f}')

        if debt_eq:
            if debt_eq > 200:
                fund_score -= 2; fund_notes.append(f'⚠️ Borç/Özsermaye {debt_eq:.0f}% — yüksek borç')
            elif debt_eq < 50:
                fund_score += 1; fund_notes.append(f'✅ Borç/Özsermaye {debt_eq:.0f}% — düşük borç')

        if earn_g and earn_g > 0.2:
            fund_score += 1; fund_notes.append(f'✅ Kâr büyümesi %{earn_g * 100:.0f}')

        data = {
            'symbol':           symbol,
            'pe_ratio':         round(pe, 2)         if pe       else None,
            'pb_ratio':         round(pb, 2)         if pb       else None,
            'ps_ratio':         round(ps, 2)         if ps       else None,
            'roe':              round(roe * 100, 2)  if roe      else None,
            'roa':              round(roa * 100, 2)  if roa      else None,
            'debt_to_equity':   round(debt_eq, 1)    if debt_eq  else None,
            'dividend_yield':   round(div_yld * 100, 2) if div_yld else None,
            'eps':              round(eps, 2)         if eps      else None,
            'revenue_growth':   round(rev_g * 100, 2)  if rev_g  else None,
            'earnings_growth':  round(earn_g * 100, 2) if earn_g else None,
            'current_ratio':    round(curr_r, 2)     if curr_r   else None,
            'gross_margin':     round(gross_m * 100, 2) if gross_m else None,
            'operating_margin': round(oper_m * 100, 2)  if oper_m else None,
            'net_margin':       round(net_m * 100, 2)   if net_m  else None,
            'market_cap':       mkt_cap,
            'sector':           sector,
            'industry':         industry,
            'employees':        employees,
            'fundamental_score': fund_score,
            'fundamental_notes': fund_notes,
        }
        _cache_set(_fund_cache, symbol, data)
        return data

    except Exception as e:
        print(f"Fundamental hatası ({symbol}): {e}")
        return {'symbol': symbol, 'fundamental_score': 0, 'fundamental_notes': [], 'error': str(e)}


# ─── Teknik Analiz ────────────────────────────────────────────────────────────

def get_technical_indicators(symbol: str, period: str = '1y') -> dict:
    """
    Kapsamlı teknik analiz:
    RSI (Wilder), MACD (12,26,9), Bollinger, EMA20/50/200,
    Stochastic %K/%D, ATR (volatilite), Williams %R,
    OBV (On-Balance Volume), Hacim analizi, Destek/Direnç,
    Pivot noktaları, Trend gücü
    """
    cached = _cache_get(_tech_cache, symbol, _TECH_TTL)
    if cached:
        return cached

    try:
        yf_sym = f"{symbol}.IS"
        if symbol in FOREX_SYMBOLS:
            yf_sym = FOREX_SYMBOLS[symbol]
        elif symbol in CRYPTO_SYMBOLS:
            yf_sym = CRYPTO_SYMBOLS[symbol]
        elif symbol in COMMODITY_SYMBOLS:
            yf_sym = COMMODITY_SYMBOLS[symbol]

        ticker = yf.Ticker(yf_sym)
        hist = ticker.history(period=period)

        if hist.empty or len(hist) < 50:
            return {'error': 'Yeterli veri yok (min 50 gün)', 'rsi': None, 'symbol': symbol}

        close  = hist['Close']
        high   = hist['High']
        low    = hist['Low']
        volume = hist['Volume']

        n = len(close)

        # ── RSI (Wilder's Smoothing) ─────────────────────────────────────────
        delta    = close.diff()
        gain     = delta.clip(lower=0)
        loss     = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, float('nan'))
        rsi_series = 100 - (100 / (1 + rs))
        rsi      = round(float(rsi_series.iloc[-1]), 1)
        rsi_prev = round(float(rsi_series.iloc[-2]), 1)
        rsi_5d   = round(float(rsi_series.iloc[-5:].mean()), 1)

        # ── MACD (12, 26, 9) ────────────────────────────────────────────────
        ema12       = close.ewm(span=12, adjust=False).mean()
        ema26       = close.ewm(span=26, adjust=False).mean()
        macd_line   = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_val    = round(float(macd_line.iloc[-1]), 3)
        signal_val  = round(float(signal_line.iloc[-1]), 3)
        macd_hist   = round(macd_val - signal_val, 3)
        macd_hist_p = round(float((macd_line - signal_line).iloc[-2]), 3) if n > 1 else macd_hist
        macd_crossover  = (macd_hist > 0 and macd_hist_p <= 0)
        macd_crossunder = (macd_hist < 0 and macd_hist_p >= 0)
        macd_momentum   = 'artiyor' if macd_hist > macd_hist_p else 'azaliyor'

        # ── EMA Trendler ────────────────────────────────────────────────────
        ema20  = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema50  = float(close.ewm(span=50, adjust=False).mean().iloc[-1]) if n >= 50 else ema20
        ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1]) if n >= 200 else ema50
        cur    = float(close.iloc[-1])

        if cur > ema20 > ema50 > ema200:
            trend = 'guclu_yukari'
        elif cur > ema50 and ema20 > ema50:
            trend = 'yukari'
        elif cur < ema20 < ema50 < ema200:
            trend = 'guclu_asagi'
        elif cur < ema50 and ema20 < ema50:
            trend = 'asagi'
        else:
            trend = 'yatay'

        trend_guc = round(abs((ema20 - ema50) / ema50) * 100, 2) if ema50 else 0

        # ── Bollinger Bands (20 gün, 2 std) ─────────────────────────────────
        bb_mid    = close.rolling(20).mean()
        bb_std    = close.rolling(20).std()
        bb_upper  = round(float((bb_mid + 2 * bb_std).iloc[-1]), 2)
        bb_lower  = round(float((bb_mid - 2 * bb_std).iloc[-1]), 2)
        bb_mid_v  = round(float(bb_mid.iloc[-1]), 2)
        bb_width  = round((bb_upper - bb_lower) / bb_mid_v * 100, 2) if bb_mid_v else 0

        if cur >= bb_upper:
            bb_position = 'ust_band_ustunde'
        elif cur <= bb_lower:
            bb_position = 'alt_band_altinda'
        else:
            bb_pct = (cur - bb_lower) / (bb_upper - bb_lower) * 100 if (bb_upper - bb_lower) else 50
            bb_position = f'bant_ici_{round(bb_pct)}pct'

        # ── Stochastic Oscillator (%K %D) ───────────────────────────────────
        low14       = low.rolling(14).min()
        high14      = high.rolling(14).max()
        stoch_k_raw = 100 * (close - low14) / (high14 - low14 + 1e-10)
        stoch_k     = round(float(stoch_k_raw.rolling(3).mean().iloc[-1]), 1)
        stoch_d     = round(float(stoch_k_raw.rolling(3).mean().rolling(3).mean().iloc[-1]), 1)
        stoch_k_p   = round(float(stoch_k_raw.rolling(3).mean().iloc[-2]), 1) if n > 1 else stoch_k

        stoch_crossover  = (stoch_k > stoch_d and stoch_k_p <= stoch_d)
        stoch_crossunder = (stoch_k < stoch_d and stoch_k_p >= stoch_d)
        stoch_signal     = 'asiri_satim' if stoch_k < 20 else ('asiri_alim' if stoch_k > 80 else 'normal')

        # ── Williams %R ─────────────────────────────────────────────────────
        high14w = high.rolling(14).max()
        low14w  = low.rolling(14).min()
        will_r  = round(float(-100 * (high14w.iloc[-1] - cur) / (high14w.iloc[-1] - low14w.iloc[-1] + 1e-10)), 1)
        will_signal = 'asiri_satim' if will_r < -80 else ('asiri_alim' if will_r > -20 else 'normal')

        # ── ATR (Average True Range) ─────────────────────────────────────────
        import pandas as pd
        prev_close = close.shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr     = round(float(tr.ewm(span=14, adjust=False).mean().iloc[-1]), 2)
        atr_pct = round(atr / cur * 100, 2) if cur else 0

        # ── OBV ─────────────────────────────────────────────────────────────
        obv_series = (volume * ((close > close.shift(1)).astype(int) - (close < close.shift(1)).astype(int))).cumsum()
        obv_trend  = 'yukari' if float(obv_series.iloc[-1]) > float(obv_series.iloc[-5]) else 'asagi'

        # ── Hacim Analizi ────────────────────────────────────────────────────
        vol_avg20  = float(volume.tail(20).mean())
        vol_today  = float(volume.iloc[-1])
        vol_ratio  = round(vol_today / vol_avg20, 2) if vol_avg20 > 0 else 1
        vol_signal = 'cok_yuksek' if vol_ratio > 3 else (
            'yuksek' if vol_ratio > 1.5 else ('dusuk' if vol_ratio < 0.5 else 'normal'))

        # ── Destek / Direnç ──────────────────────────────────────────────────
        recent_high_20 = round(float(high.tail(20).max()), 2)
        recent_low_20  = round(float(low.tail(20).min()), 2)
        recent_high_60 = round(float(high.tail(60).max()), 2)
        recent_low_60  = round(float(low.tail(60).min()), 2)

        p_high = float(high.iloc[-2])
        p_low  = float(low.iloc[-2])
        p_close = float(close.iloc[-2])
        pivot  = round((p_high + p_low + p_close) / 3, 2)
        r1     = round(2 * pivot - p_low, 2)
        s1     = round(2 * pivot - p_high, 2)
        r2     = round(pivot + (p_high - p_low), 2)
        s2     = round(pivot - (p_high - p_low), 2)

        # ── Mum Formasyonu ───────────────────────────────────────────────────
        o1 = float(hist['Open'].iloc[-1])
        c1 = float(close.iloc[-1])
        h1 = float(high.iloc[-1])
        l1 = float(low.iloc[-1])
        body       = abs(c1 - o1)
        upper_wick = h1 - max(c1, o1)
        lower_wick = min(c1, o1) - l1
        candle_pattern = 'normal'
        if body < (h1 - l1) * 0.1:
            candle_pattern = 'doji'
        elif lower_wick > body * 2 and upper_wick < body * 0.5:
            candle_pattern = 'cekic' if c1 > o1 else 'asilan_adam'
        elif upper_wick > body * 2 and lower_wick < body * 0.5:
            candle_pattern = 'ters_cekic'

        # ── Fiyat Momentumu ──────────────────────────────────────────────────
        returns_5d  = round((cur / float(close.iloc[-6])  - 1) * 100, 2) if n > 6  else 0
        returns_20d = round((cur / float(close.iloc[-21]) - 1) * 100, 2) if n > 21 else 0
        returns_60d = round((cur / float(close.iloc[-61]) - 1) * 100, 2) if n > 61 else 0

        # ── Özet ─────────────────────────────────────────────────────────────
        yorumlar = []
        if rsi > 75:
            yorumlar.append(f'RSI {rsi} — aşırı alım, düşüş riski')
        elif rsi < 25:
            yorumlar.append(f'RSI {rsi} — aşırı satım, toparlanma beklentisi')
        else:
            yorumlar.append(f'RSI {rsi} — normal bölge')

        if macd_crossover:
            yorumlar.append('MACD alım sinyali (yukarı kesiş)')
        elif macd_crossunder:
            yorumlar.append('MACD satım sinyali (aşağı kesiş)')

        if stoch_k < 20 and stoch_crossover:
            yorumlar.append(f'Stochastic aşırı satım + yukarı kesiş ({stoch_k})')
        elif stoch_k > 80 and stoch_crossunder:
            yorumlar.append(f'Stochastic aşırı alım + aşağı kesiş ({stoch_k})')

        yorumlar.append(f'Trend: {trend} (EMA güç: %{trend_guc})')
        yorumlar.append(f'Hacim: {vol_signal} ({vol_ratio}x ortalama)')

        result = {
            'symbol': symbol, 'current_price': round(cur, 2),
            'rsi': rsi, 'rsi_prev': rsi_prev, 'rsi_5d_avg': rsi_5d,
            'macd': macd_val, 'macd_signal': signal_val, 'macd_histogram': macd_hist,
            'macd_crossover': macd_crossover, 'macd_crossunder': macd_crossunder,
            'macd_momentum': macd_momentum, 'macd_hist_prev': macd_hist_p,
            'ema20': round(ema20, 2), 'ema50': round(ema50, 2), 'ema200': round(ema200, 2),
            'trend': trend, 'trend_strength_pct': trend_guc,
            'bb_upper': bb_upper, 'bb_mid': bb_mid_v, 'bb_lower': bb_lower,
            'bb_position': bb_position, 'bb_width': bb_width,
            'stoch_k': stoch_k, 'stoch_d': stoch_d,
            'stoch_crossover': stoch_crossover, 'stoch_crossunder': stoch_crossunder,
            'stoch_signal': stoch_signal,
            'williams_r': will_r, 'williams_signal': will_signal,
            'atr': atr, 'atr_pct': atr_pct,
            'obv_trend': obv_trend,
            'volume_ratio': vol_ratio, 'volume_signal': vol_signal, 'volume_avg20': round(vol_avg20),
            'support': recent_low_20, 'resistance': recent_high_20,
            'support_60d': recent_low_60, 'resistance_60d': recent_high_60,
            'pivot': pivot, 'r1': r1, 's1': s1, 'r2': r2, 's2': s2,
            'candle_pattern': candle_pattern,
            'return_5d': returns_5d, 'return_20d': returns_20d, 'return_60d': returns_60d,
            'summary': ', '.join(yorumlar),
        }
        _cache_set(_tech_cache, symbol, result)
        return result

    except Exception as e:
        print(f"Teknik analiz hatası ({symbol}): {e}")
        return {'error': str(e), 'rsi': None, 'symbol': symbol, 'summary': 'Teknik veri alınamadı'}


# ─── Yardımcı ─────────────────────────────────────────────────────────────────

def search_bist_stocks(query: str) -> list:
    query = query.upper().strip()
    matched = [s for s in ALL_BIST_STOCKS if query in s]
    if not matched and len(query) >= 2:
        matched = [query]
    results = []
    for sym in matched[:8]:
        data = get_stock_data(sym)
        if data and data['price'] > 0:
            results.append({'symbol': sym, 'price': data['price'], 'change_percent': data['change_percent']})
    return results


def update_stock_in_db(symbol: str):
    from .models import Stock
    data = get_stock_data(symbol)
    if data:
        Stock.objects.update_or_create(
            symbol=symbol,
            defaults={
                'name': symbol, 'price': data['price'],
                'previous_close': data['previous_close'],
                'change_percent': data['change_percent'],
                'volume': data['volume'], 'market_cap': data['market_cap'],
            }
        )
        return data
    return None