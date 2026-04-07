"""
Athena Email Servisi — Gelişmiş HTML Bildirimleri
Hisse sinyalleri, emtia uyarıları, yatırım planları
"""
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import AlertLog


def _already_sent(symbol: str, signal: str, hours: int = 6) -> bool:
    cutoff = timezone.now() - timedelta(hours=hours)
    return AlertLog.objects.filter(
        symbol=symbol, signal=signal, email_sent=True, sent_at__gte=cutoff
    ).exists()


def _base_style() -> str:
    return """
    <style>
      body { font-family: 'Segoe UI', Arial, sans-serif; background: #0a0a1a; color: #e0e0e0; margin: 0; padding: 0; }
      .container { max-width: 640px; margin: 0 auto; padding: 20px; }
      .header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                padding: 24px; border-radius: 12px; text-align: center; margin-bottom: 16px;
                border: 1px solid #2a2a4e; }
      .header h1 { color: #e94560; margin: 0; font-size: 28px; letter-spacing: 4px; }
      .header p  { color: #7070a0; margin: 6px 0 0; font-size: 13px; }
      .card { background: #16213e; border-radius: 10px; padding: 20px; margin: 12px 0;
              border: 1px solid #2a2a4e; }
      .signal-card { text-align: center; padding: 24px; border-radius: 12px; margin: 16px 0; }
      .al  { background: #0a2a1a; border: 2px solid #00cc66; }
      .sat { background: #2a0a0a; border: 2px solid #cc2200; }
      .bekle { background: #1a1a0a; border: 2px solid #ccaa00; }
      .signal-text-al  { color: #00ff88; font-size: 42px; font-weight: bold; }
      .signal-text-sat { color: #ff4444; font-size: 42px; font-weight: bold; }
      .signal-text-bekle { color: #ffcc00; font-size: 42px; font-weight: bold; }
      .metric-row { display: flex; justify-content: space-between; padding: 10px 0;
                    border-bottom: 1px solid #2a2a4e; }
      .metric-label { color: #7070a0; font-size: 13px; }
      .metric-value { color: #ffffff; font-weight: 600; font-size: 14px; }
      .tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px;
             font-weight: 600; margin: 2px; }
      .tag-green { background: #0a2a1a; color: #00ff88; border: 1px solid #00cc66; }
      .tag-red   { background: #2a0a0a; color: #ff6666; border: 1px solid #cc2200; }
      .tag-yellow{ background: #1a1a0a; color: #ffcc00; border: 1px solid #cc9900; }
      .tag-blue  { background: #0a1a2a; color: #6699ff; border: 1px solid #3366cc; }
      .disclaimer { background: #150505; border: 1px solid #441111; border-radius: 8px;
                    padding: 12px; margin-top: 16px; }
      .disclaimer p { color: #884444; font-size: 11px; margin: 0; line-height: 1.6; }
      .footer { text-align: center; color: #444466; font-size: 11px; margin-top: 16px; }
      h3 { color: #e94560; margin: 0 0 12px; font-size: 15px; text-transform: uppercase;
           letter-spacing: 1px; }
      ul { color: #c0c0d0; padding-left: 20px; line-height: 2; margin: 0; }
      li { font-size: 13px; }
    </style>
    """


def send_signal_alert(symbol: str, signal: str, score: int, price: float,
                      reasons: list, tech: dict, change_pct: float,
                      fundamental: dict = None) -> bool:
    """Güçlü AL/SAT sinyali gelince mail gönderir"""

    if _already_sent(symbol, signal, hours=4):
        print(f"[SPAM ÖNLEME] {symbol} {signal} için son 4 saatte zaten mail gönderildi.")
        return False

    # Sinyal sınıfı
    is_al  = 'AL' in signal
    is_sat = 'SAT' in signal
    emoji  = '🚀' if is_al else ('🔻' if is_sat else '⏸️')
    signal_class = 'al' if is_al else ('sat' if is_sat else 'bekle')
    signal_text_class = f'signal-text-{signal_class}'
    signal_color = '#00ff88' if is_al else ('#ff4444' if is_sat else '#ffcc00')

    subject = f"{emoji} Athena: {symbol} → {signal} (Skor: {score}/25)"

    # Teknik göstergeler renklendirme
    rsi = tech.get('rsi', '-')
    rsi_color = '#ff4444' if (rsi and rsi > 70) else ('#00ff88' if (rsi and rsi < 30) else '#ffffff')

    trend = tech.get('trend', '-').replace('_', ' ').title()
    trend_color = '#00ff88' if 'Yukari' in trend else ('#ff4444' if 'Asagi' in trend else '#ffcc00')

    macd_hist = tech.get('macd_histogram', '-')
    macd_color = '#00ff88' if (macd_hist and macd_hist > 0) else '#ff4444'

    stoch_k = tech.get('stoch_k', '-')
    stoch_color = '#00ff88' if (stoch_k and stoch_k < 25) else ('#ff4444' if (stoch_k and stoch_k > 75) else '#ffffff')

    will_r = tech.get('williams_r', '-')
    will_color = '#00ff88' if (will_r and will_r < -80) else ('#ff4444' if (will_r and will_r > -20) else '#ffffff')

    vol_ratio = tech.get('volume_ratio', '-')
    vol_color = '#00ff88' if (vol_ratio and vol_ratio > 1.5) else ('#ff4444' if (vol_ratio and vol_ratio < 0.5) else '#ffffff')

    returns_5d  = tech.get('return_5d', 0)
    returns_20d = tech.get('return_20d', 0)
    r5_color  = '#00ff88' if returns_5d  > 0 else '#ff4444'
    r20_color = '#00ff88' if returns_20d > 0 else '#ff4444'

    # Gerekçe HTML
    reasons_html = "".join(f"<li>{r}</li>" for r in reasons)

    # Pivot noktaları
    pivot = tech.get('pivot', '-')
    r1    = tech.get('r1', '-')
    s1    = tech.get('s1', '-')
    r2    = tech.get('r2', '-')
    s2    = tech.get('s2', '-')

    # Bollinger sıkışma uyarısı
    bb_width = tech.get('bb_width', 0)
    bb_squeeze_html = ''
    if bb_width and bb_width < 3:
        bb_squeeze_html = f'<p style="color:#ffcc00;font-size:12px;margin:8px 0;">⚡ Bollinger Sıkışması ({bb_width}%) — Yakında sert hareket bekleniyor!</p>'

    # Fundamental HTML (varsa)
    fund_html = ''
    if fundamental and fundamental.get('pe_ratio'):
        pe   = fundamental.get('pe_ratio', '-')
        pb   = fundamental.get('pb_ratio', '-')
        roe  = fundamental.get('roe', '-')
        div  = fundamental.get('dividend_yield', '-')
        fs   = fundamental.get('fundamental_score', 0)
        fn   = fundamental.get('fundamental_notes', [])
        fn_html = "".join(f"<li>{n}</li>" for n in fn[:4])
        fund_html = f"""
        <div class="card">
          <h3>📊 Temel Analiz</h3>
          <div class="metric-row">
            <span class="metric-label">F/K Oranı</span>
            <span class="metric-value">{pe}</span>
          </div>
          <div class="metric-row">
            <span class="metric-label">PD/DD</span>
            <span class="metric-value">{pb}</span>
          </div>
          <div class="metric-row">
            <span class="metric-label">ROE</span>
            <span class="metric-value">%{roe}</span>
          </div>
          <div class="metric-row">
            <span class="metric-label">Temettü Verimi</span>
            <span class="metric-value">%{div}</span>
          </div>
          <div class="metric-row">
            <span class="metric-label">Temel Skor</span>
            <span class="metric-value" style="color: {'#00ff88' if fs > 0 else '#ff4444'}">{fs:+d}</span>
          </div>
          <ul style="margin-top:12px;">{fn_html}</ul>
        </div>
        """

    body_html = f"""
<html>
<head>{_base_style()}</head>
<body>
<div class="container">

  <div class="header">
    <h1>⚡ ATHENA</h1>
    <p>Yapay Zeka Yatırım Danışmanı — BIST & Global Piyasalar</p>
  </div>

  <div class="signal-card {signal_class}">
    <div class="{signal_text_class}">{emoji} {symbol} → {signal}</div>
    <p style="color:#aaaaaa; font-size:16px; margin:8px 0 0;">Sinyal Gücü: 
      <strong style="color:{signal_color};">{score}/25</strong>
    </p>
    <p style="color:#cccccc; font-size:20px; margin:8px 0;">
      <strong style="color:white;">{price:.2f} TL</strong>
      <span style="color:{('#00ff88' if change_pct > 0 else '#ff4444')}; font-size:14px;"> 
        ({change_pct:+.2f}% bugün)
      </span>
    </p>
    {bb_squeeze_html}
  </div>

  <div class="card">
    <h3>📋 Sinyal Gerekçeleri ({len(reasons)} faktör)</h3>
    <ul>{reasons_html}</ul>
  </div>

  <div class="card">
    <h3>📈 Teknik Göstergeler</h3>
    <div class="metric-row">
      <span class="metric-label">RSI (14)</span>
      <span class="metric-value" style="color:{rsi_color};">{rsi}</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Stochastic %K/%D</span>
      <span class="metric-value" style="color:{stoch_color};">{stoch_k} / {tech.get('stoch_d','-')}</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Williams %R</span>
      <span class="metric-value" style="color:{will_color};">{will_r}</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">MACD Histogram</span>
      <span class="metric-value" style="color:{macd_color};">{macd_hist}</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">MACD Momentumu</span>
      <span class="metric-value">{tech.get('macd_momentum','-')}</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Trend (EMA)</span>
      <span class="metric-value" style="color:{trend_color};">{trend}</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">EMA 20 / 50 / 200</span>
      <span class="metric-value">{tech.get('ema20','-')} / {tech.get('ema50','-')} / {tech.get('ema200','-')}</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Bollinger Bandı</span>
      <span class="metric-value">{tech.get('bb_lower','-')} — {tech.get('bb_upper','-')} TL</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">ATR (Volatilite)</span>
      <span class="metric-value">{tech.get('atr','-')} TL (%{tech.get('atr_pct','-')})</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Hacim Durumu</span>
      <span class="metric-value" style="color:{vol_color};">{tech.get('volume_signal','-')} ({vol_ratio}x)</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">OBV Trendi</span>
      <span class="metric-value">{tech.get('obv_trend','-')}</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Mum Formasyonu</span>
      <span class="metric-value">{tech.get('candle_pattern','-')}</span>
    </div>
  </div>

  <div class="card">
    <h3>🎯 Fiyat Seviyeleri</h3>
    <div class="metric-row">
      <span class="metric-label">Destek (20 gün)</span>
      <span class="metric-value" style="color:#00ff88;">{tech.get('support','-')} TL</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Direnç (20 gün)</span>
      <span class="metric-value" style="color:#ff4444;">{tech.get('resistance','-')} TL</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Pivot</span>
      <span class="metric-value">{pivot} TL</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">R1 / R2</span>
      <span class="metric-value" style="color:#ff8888;">{r1} / {r2} TL</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">S1 / S2</span>
      <span class="metric-value" style="color:#88ff88;">{s1} / {s2} TL</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Getiri (5G / 20G)</span>
      <span class="metric-value">
        <span style="color:{r5_color};">%{returns_5d:+.1f}</span> /
        <span style="color:{r20_color};">%{returns_20d:+.1f}</span>
      </span>
    </div>
  </div>

  {fund_html}

  <div class="disclaimer">
    <p>⚠️ Bu analiz kişisel kullanım içindir ve resmi yatırım tavsiyesi değildir.
    Geçmiş performans gelecekteki sonuçları garanti etmez. Yatırım kararlarınızı
    kendi araştırmanız ve risk toleransınıza göre alın. Son karar her zaman size aittir.</p>
  </div>

  <div class="footer">
    <p>⚡ Athena — BIST Yapay Zeka Danışmanı | {timezone.now().strftime('%d.%m.%Y %H:%M')} TSİ</p>
  </div>

</div>
</body>
</html>
"""

    try:
        send_mail(
            subject=subject,
            message=f"Athena: {symbol} → {signal} | {price:.2f} TL | Skor: {score}",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.ATHENA_ALERT_EMAIL],
            html_message=body_html,
            fail_silently=False,
        )
        AlertLog.objects.create(
            symbol=symbol, signal=signal, score=score,
            price=price, email_sent=True,
            note=", ".join(reasons[:4])
        )
        print(f"[EMAIL ✅] {symbol} {signal} → {settings.ATHENA_ALERT_EMAIL}")
        return True
    except Exception as e:
        print(f"[EMAIL ❌] {e}")
        AlertLog.objects.create(
            symbol=symbol, signal=signal, score=score,
            price=price, email_sent=False, note=str(e)
        )
        return False


def send_commodity_alert(name: str, data: dict, category: str):
    """Altın/döviz önemli hareketi bildirimi"""
    chg = data.get('change_percent', 0)
    price = data.get('price') or data.get('rate', 0)
    direction = '🚀 YUKARI' if chg > 0 else '🔻 AŞAĞI'
    emoji = '🥇' if 'ALTIN' in name else ('💵' if category == 'forex' else '📦')

    subject = f"{emoji} Athena: {name} {direction} %{abs(chg):.2f}"
    body = f"""
<html><head>{_base_style()}</head><body><div class="container">
  <div class="header"><h1>⚡ ATHENA</h1><p>Emtia/Döviz Uyarısı</p></div>
  <div class="signal-card {'al' if chg > 0 else 'sat'}">
    <div class="{'signal-text-al' if chg > 0 else 'signal-text-sat'}">{emoji} {name}</div>
    <p style="color:#ccc;font-size:20px;">{price:.4f} 
       <span style="color:{'#00ff88' if chg>0 else '#ff4444'};">({chg:+.2f}%)</span></p>
  </div>
  <div class="footer"><p>Athena | {timezone.now().strftime('%d.%m.%Y %H:%M')} TSİ</p></div>
</div></body></html>
"""
    try:
        send_mail(subject=subject, message=f"{name}: {price} ({chg:+.2f}%)",
                  from_email=settings.EMAIL_HOST_USER,
                  recipient_list=[settings.ATHENA_ALERT_EMAIL],
                  html_message=body, fail_silently=True)
        print(f"[EMAIL ✅] {name} emtia uyarısı gönderildi.")
    except Exception as e:
        print(f"[EMAIL ❌] Emtia: {e}")


def send_investment_advice_email(symbol: str, budget: float, advice: str,
                                  recommended_qty: int, entry_price: float,
                                  stop_price: float = None, target_price: float = None,
                                  signal_score: int = 0, fundamental: dict = None):
    """Yatırım planı tavsiyesini mail ile gönderir"""
    subject = f"🎯 Athena Yatırım Planı: {symbol} — {budget:,.0f} TL"

    fund_html = ''
    if fundamental and fundamental.get('pe_ratio'):
        fn = fundamental.get('fundamental_notes', [])
        fn_html = "".join(f"<li>{n}</li>" for n in fn[:4])
        fund_html = f"""
        <div class="card"><h3>📊 Şirket Temelleri</h3><ul>{fn_html}</ul></div>
        """

    body_html = f"""
<html><head>{_base_style()}</head><body><div class="container">

  <div class="header">
    <h1>⚡ ATHENA</h1>
    <p>Kişisel Yatırım Danışmanı</p>
  </div>

  <div class="signal-card al">
    <div class="signal-text-al">🎯 {symbol}</div>
    <p style="color:#aaa;">Yatırım Planı Hazırlandı</p>
  </div>

  <div class="card">
    <h3>💰 Plan Özeti</h3>
    <div class="metric-row">
      <span class="metric-label">Bütçe</span>
      <span class="metric-value">{budget:,.2f} TL</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Önerilen Giriş Fiyatı</span>
      <span class="metric-value">{entry_price:.2f} TL</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Alınabilecek Adet</span>
      <span class="metric-value">{recommended_qty} adet</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Stop-Loss Fiyatı</span>
      <span class="metric-value" style="color:#ff6666;">{stop_price:.2f} TL</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Hedef Fiyat</span>
      <span class="metric-value" style="color:#00ff88;">{target_price:.2f} TL</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Sinyal Gücü</span>
      <span class="metric-value" style="color:#{'00ff88' if signal_score > 0 else 'ff4444'}">{signal_score:+d}/25</span>
    </div>
  </div>

  {fund_html}

  <div class="card">
    <h3>💬 Athena'nın Analizi</h3>
    <div style="color:#c0c0d0; line-height:1.8; font-size:13px; white-space:pre-wrap;">{advice}</div>
  </div>

  <div class="disclaimer">
    <p>⚠️ Kişisel kullanım içindir. Resmi yatırım tavsiyesi değildir. Son karar her zaman size aittir.</p>
  </div>
  <div class="footer"><p>Athena | {timezone.now().strftime('%d.%m.%Y %H:%M')} TSİ</p></div>

</div></body></html>
"""

    try:
        send_mail(
            subject=subject,
            message=f"Athena Yatırım Planı: {symbol} — {budget} TL",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.ATHENA_ALERT_EMAIL],
            html_message=body_html,
            fail_silently=False,
        )
        print(f"[EMAIL ✅] Yatırım planı maili gönderildi: {symbol}")
        return True
    except Exception as e:
        print(f"[EMAIL ❌] {e}")
        return False