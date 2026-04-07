"""
Athena Günlük Rapor Komutu
python manage.py gunluk_rapor --butce 1000

Tüm varlık sınıflarını tarar (BIST + Altın + Döviz + Kripto),
bütçeye göre en iyi Top 3 fırsatı mail ile gönderir.
Her öneri için onay kodu içerir — onaylayınca izlemeye alınır.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings


class Command(BaseCommand):
    help = 'Günlük Top 3 yatırım önerisi — python manage.py gunluk_rapor --butce 1000'

    def add_arguments(self, parser):
        parser.add_argument('--butce', type=float, default=1000,
                            help='Yatırım bütçesi (TL)')
        parser.add_argument('--risk', type=str, default='orta',
                            choices=['dusuk', 'orta', 'yuksek'],
                            help='Risk seviyesi')
        parser.add_argument('--dry-run', action='store_true',
                            help='Mail atmadan ekrana yaz')

    def handle(self, *args, **options):
        butce = options['butce']
        risk = options['risk']
        dry_run = options['dry_run']

        self.stdout.write(self.style.HTTP_INFO(
            f"\n[{timezone.now():%H:%M}] ⚡ Athena günlük rapor başlıyor... "
            f"(Bütçe: {butce:,.0f} TL | Risk: {risk})"
        ))

        adaylar = self._tum_varliklari_tara(butce)

        if not adaylar:
            self.stdout.write(self.style.ERROR("Hiç veri alınamadı."))
            return

        # Skora göre sırala, Top 3 seç
        adaylar.sort(key=lambda x: x['skor'], reverse=True)
        top3 = adaylar[:3]

        self.stdout.write(self.style.SUCCESS(f"\n✅ {len(adaylar)} varlık tarandı, Top 3 seçildi:\n"))
        for i, a in enumerate(top3, 1):
            self.stdout.write(f"  {i}. {a['sembol']:12s} | Skor: {a['skor']:+d} | "
                              f"{a['fiyat_str']:>12s} | {a['sinyal']} | {a['tip']}")

        if not dry_run:
            self._mail_gonder(top3, butce, risk)
            self.stdout.write(self.style.SUCCESS(
                f"\n📧 Öneri maili gönderildi → {settings.ATHENA_ALERT_EMAIL}"
            ))
            self.stdout.write(
                "\nMaildeki ONAY KODUNU kullanarak onaylamak için:\n"
                "  python manage.py onayla --kod BIMAS-AL-123\n"
            )
        else:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] Mail gönderilmedi."))

    # ─── Tüm varlıkları tara ───────────────────────────────────────────────

    def _tum_varliklari_tara(self, butce: float) -> list:
        from stocks.services import (
            get_stock_data, get_technical_indicators, get_fundamental_data,
            get_commodity_data, get_forex_data, get_crypto_data,
            POPULAR_BIST_STOCKS, COMMODITY_SYMBOLS, FOREX_SYMBOLS, CRYPTO_SYMBOLS,
        )
        from monitor.scanner import compute_score, _get_signal_label

        adaylar = []

        # ── 1. BIST Hisseleri ──────────────────────────────────────────────
        self.stdout.write("  📈 BIST hisseleri taranıyor...")
        for sembol in POPULAR_BIST_STOCKS[:30]:
            try:
                stock = get_stock_data(sembol)
                if not stock or stock.get('price', 0) == 0:
                    continue
                tech = get_technical_indicators(sembol)
                if not tech.get('rsi'):
                    continue
                try:
                    fund = get_fundamental_data(sembol)
                except:
                    fund = None
                puan, gerekceler = compute_score(tech, stock, fund)
                if puan < 2:  # Zayıf sinyalleri ele
                    continue
                fiyat = stock['price']
                adet = int(butce * 0.8 / fiyat)
                if adet < 1:
                    continue
                adaylar.append({
                    'tip': 'BIST Hisse',
                    'sembol': sembol,
                    'skor': puan,
                    'sinyal': _get_signal_label(puan),
                    'fiyat': fiyat,
                    'fiyat_str': f"{fiyat:.2f} TL",
                    'degisim': stock['change_percent'],
                    'adet': adet,
                    'maliyet': round(adet * fiyat, 2),
                    'gerekceler': gerekceler[:4],
                    'tech': tech,
                    'fund': fund,
                })
            except Exception as e:
                continue

        # ── 2. Altın (gram TL) ────────────────────────────────────────────
        self.stdout.write("  🥇 Altın taranıyor...")
        altin_tl = self._altin_gram_tl()
        if altin_tl:
            puan = self._altin_skoru(altin_tl)
            if puan >= 2:
                fiyat = altin_tl['fiyat']
                gram = round(butce * 0.8 / fiyat, 2)
                adaylar.append({
                    'tip': 'Altın (gram)',
                    'sembol': 'ALTIN_TL',
                    'skor': puan,
                    'sinyal': 'AL' if puan >= 3 else 'BEKLE',
                    'fiyat': fiyat,
                    'fiyat_str': f"{fiyat:.2f} TL/gr",
                    'degisim': altin_tl['degisim'],
                    'adet': gram,
                    'maliyet': round(gram * fiyat, 2),
                    'gerekceler': altin_tl['gerekceler'],
                    'tech': {},
                    'fund': None,
                    'extra': altin_tl,
                })

        # ── 3. Döviz ─────────────────────────────────────────────────────
        self.stdout.write("  💵 Döviz taranıyor...")
        for pair in ['USDTRY', 'EURTRY']:
            try:
                d = get_forex_data(pair)
                if not d or d.get('rate', 0) == 0:
                    continue
                puan = self._doviz_skoru(d)
                if puan < 2:
                    continue
                fiyat = d['rate']
                adet = round(butce * 0.8 / fiyat, 2)
                birim = 'USD' if 'USD' in pair else 'EUR'
                adaylar.append({
                    'tip': f'Döviz ({birim})',
                    'sembol': pair,
                    'skor': puan,
                    'sinyal': 'AL' if puan >= 3 else 'BEKLE',
                    'fiyat': fiyat,
                    'fiyat_str': f"{fiyat:.4f} TL",
                    'degisim': d['change_percent'],
                    'adet': adet,
                    'maliyet': round(adet * fiyat, 2),
                    'gerekceler': [
                        f"📊 {pair}: {fiyat:.4f} TL",
                        f"📈 Günlük: {d['change_percent']:+.2f}%",
                    ],
                    'tech': {},
                    'fund': None,
                })
            except:
                continue

        # ── 4. Kripto ─────────────────────────────────────────────────────
        self.stdout.write("  🪙 Kripto taranıyor...")
        usdtry = self._usdtry_kuru()
        for sym in ['BTC', 'ETH', 'BNB', 'SOL', 'AVAX']:
            try:
                d = get_crypto_data(sym)
                if not d or d.get('price_usd', 0) == 0:
                    continue
                puan = self._kripto_skoru(d)
                if puan < 2:
                    continue
                fiyat_usd = d['price_usd']
                fiyat_tl = round(fiyat_usd * usdtry, 2) if usdtry else None
                fiyat_str = f"${fiyat_usd:,.2f}" + (f" ({fiyat_tl:,.0f} TL)" if fiyat_tl else "")
                adet = round(butce * 0.8 / (fiyat_tl or fiyat_usd * 40), 6)
                adaylar.append({
                    'tip': 'Kripto',
                    'sembol': sym,
                    'skor': puan,
                    'sinyal': 'AL' if puan >= 3 else 'BEKLE',
                    'fiyat': fiyat_usd,
                    'fiyat_str': fiyat_str,
                    'degisim': d['change_percent'],
                    'adet': adet,
                    'maliyet': round(butce * 0.8, 2),
                    'gerekceler': [
                        f"💰 Fiyat: ${fiyat_usd:,.2f}",
                        f"📈 Günlük: {d['change_percent']:+.2f}%",
                    ],
                    'tech': {},
                    'fund': None,
                })
            except:
                continue

        return adaylar

    # ─── Altın gram TL hesapla ─────────────────────────────────────────────

    def _altin_gram_tl(self) -> dict | None:
        """Altın gram TL = Altın USD/ons * USDTRY / 32.1507"""
        from stocks.services import get_commodity_data, get_forex_data
        try:
            altin = get_commodity_data('ALTIN_USD')
            kur = get_forex_data('USDTRY')
            if not altin or not kur:
                return None
            ons_usd = altin['price']
            usd_tl = kur['rate']
            gram_tl = round(ons_usd * usd_tl / 32.1507, 2)
            degisim = round(altin['change_percent'] + kur['change_percent'], 2)
            gerekceler = [
                f"🥇 Altın: ${ons_usd:,.2f}/ons",
                f"💱 USD/TRY: {usd_tl:.4f}",
                f"📊 Gram fiyat: {gram_tl:,.2f} TL",
                f"📈 Günlük değişim: {degisim:+.2f}%",
            ]
            return {'fiyat': gram_tl, 'degisim': degisim, 'gerekceler': gerekceler,
                    'ons_usd': ons_usd, 'usd_tl': usd_tl}
        except Exception as e:
            self.stdout.write(f"  Altın hatası: {e}")
            return None

    def _usdtry_kuru(self) -> float:
        from stocks.services import get_forex_data
        try:
            d = get_forex_data('USDTRY')
            return d['rate'] if d else 40.0
        except:
            return 40.0

    # ─── Basit skorlama (teknik veri olmayan varlıklar için) ───────────────

    def _altin_skoru(self, altin: dict) -> int:
        """Altın için basit momentum skoru"""
        puan = 0
        degisim = altin.get('degisim', 0)
        if degisim > 1.5:
            puan += 2
        elif degisim > 0.5:
            puan += 1
        elif degisim < -1.5:
            puan -= 2
        # Altın her zaman bir değer saklama aracı — minimum 1 puan
        puan += 1
        return puan

    def _doviz_skoru(self, d: dict) -> int:
        puan = 0
        degisim = d.get('change_percent', 0)
        if degisim > 0.5:
            puan += 2
        elif degisim > 0.2:
            puan += 1
        elif degisim < -0.5:
            puan -= 1
        return puan

    def _kripto_skoru(self, d: dict) -> int:
        puan = 0
        degisim = d.get('change_percent', 0)
        if degisim > 3:
            puan += 2
        elif degisim > 1:
            puan += 1
        elif degisim < -3:
            puan -= 2
        elif degisim < -1:
            puan -= 1
        return puan

    # ─── Mail gönder ──────────────────────────────────────────────────────

    def _mail_gonder(self, top3: list, butce: float, risk: str):
        import random, string
        from django.core.mail import send_mail
        from django.conf import settings

        simdi = timezone.now()

        # Onay kodları üret ve DB'ye kaydet
        kodlar = []
        for a in top3:
            kod = f"{a['sembol']}-{simdi.strftime('%d%H%M')}"
            kodlar.append(kod)
            # InvestmentPlan'a "beklemede" olarak kaydet
            try:
                from monitor.models import InvestmentPlan
                InvestmentPlan.objects.update_or_create(
                    symbol=a['sembol'],
                    defaults={
                        'budget_tl': butce,
                        'entry_price': a['fiyat'],
                        'is_active': False,  # Onay bekliyor
                        'athena_advice': f"ONAY_BEKLENIYOR|KOD:{kod}|TIP:{a['tip']}",
                        'target_return_pct': 15 if risk == 'orta' else (8 if risk == 'dusuk' else 30),
                        'stop_loss_pct': 8 if risk == 'orta' else (4 if risk == 'dusuk' else 15),
                    }
                )
            except:
                pass

        risk_tablosu = {
            'dusuk':  {'stop': 4,  'hedef': 8},
            'orta':   {'stop': 8,  'hedef': 15},
            'yuksek': {'stop': 15, 'hedef': 30},
        }
        rt = risk_tablosu.get(risk, risk_tablosu['orta'])

        html = self._html_rapor(top3, butce, risk, rt, kodlar, simdi)

        send_mail(
            subject=f"⚡ Athena Top 3 Öneri — {simdi:%d %b %H:%M} | Bütçe: {butce:,.0f} TL",
            message="HTML görüntüleyici gerekli.",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.ATHENA_ALERT_EMAIL],
            html_message=html,
            fail_silently=False,
        )

    def _html_rapor(self, top3, butce, risk, rt, kodlar, simdi):
        risk_renk = {'dusuk': '#00aaff', 'orta': '#ffaa00', 'yuksek': '#ff4444'}
        renk = risk_renk.get(risk, '#ffaa00')

        oneriler_html = ""
        for i, (a, kod) in enumerate(zip(top3, kodlar), 1):
            sinyal_renk = '#00ff88' if 'AL' in a['sinyal'] else '#ffcc00'
            gerekce_html = "".join(
                f"<li style='margin:4px 0; color:#ccc;'>{g}</li>"
                for g in a['gerekceler']
            )
            stop_fiyat = round(a['fiyat'] * (1 - rt['stop'] / 100), 2) if a['tip'] not in ['Altın (gram)', 'Döviz (USD)', 'Döviz (EUR)'] else None
            hedef_fiyat = round(a['fiyat'] * (1 + rt['hedef'] / 100), 2) if stop_fiyat else None

            stop_satir = f"""
            <div style='display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2a2a4e;'>
                <span style='color:#7070a0;'>Stop-Loss</span>
                <span style='color:#ff6666; font-weight:600;'>{stop_fiyat} TL (-%{rt['stop']})</span>
            </div>
            <div style='display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2a2a4e;'>
                <span style='color:#7070a0;'>Hedef Fiyat</span>
                <span style='color:#00ff88; font-weight:600;'>{hedef_fiyat} TL (+%{rt['hedef']})</span>
            </div>""" if stop_fiyat else ""

            oneriler_html += f"""
            <div style='background:#16213e; border-radius:12px; padding:20px; margin:16px 0;
                        border:2px solid {sinyal_renk}; position:relative;'>
                <div style='position:absolute; top:12px; right:12px; background:{sinyal_renk};
                            color:#000; font-weight:bold; padding:4px 10px; border-radius:20px;
                            font-size:12px;'>#{i}</div>
                <div style='display:flex; align-items:center; gap:12px; margin-bottom:16px;'>
                    <div style='font-size:28px; font-weight:900; color:{sinyal_renk};'>{a['sembol']}</div>
                    <div>
                        <div style='color:#7070a0; font-size:12px;'>{a['tip']}</div>
                        <div style='color:{sinyal_renk}; font-weight:bold;'>{a['sinyal']}</div>
                    </div>
                </div>
                <div style='display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2a2a4e;'>
                    <span style='color:#7070a0;'>Güncel Fiyat</span>
                    <span style='color:#fff; font-weight:600;'>{a['fiyat_str']}</span>
                </div>
                <div style='display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2a2a4e;'>
                    <span style='color:#7070a0;'>Bugünkü Değişim</span>
                    <span style='color:{"#00ff88" if a["degisim"] >= 0 else "#ff4444"}; font-weight:600;'>{a['degisim']:+.2f}%</span>
                </div>
                <div style='display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2a2a4e;'>
                    <span style='color:#7070a0;'>Önerilen Miktar</span>
                    <span style='color:#fff; font-weight:600;'>{a['adet']} adet ≈ {a['maliyet']:,.0f} TL</span>
                </div>
                {stop_satir}
                <div style='display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2a2a4e;'>
                    <span style='color:#7070a0;'>Teknik Skor</span>
                    <span style='color:{sinyal_renk}; font-weight:600;'>{a['skor']:+d} / 25</span>
                </div>
                <div style='margin:12px 0;'>
                    <div style='color:#7070a0; font-size:12px; margin-bottom:6px;'>📋 Gerekçeler:</div>
                    <ul style='margin:0; padding-left:18px;'>{gerekce_html}</ul>
                </div>
                <div style='background:#0a1a0a; border:1px solid #00cc44; border-radius:8px;
                            padding:12px; margin-top:12px; text-align:center;'>
                    <div style='color:#7070a0; font-size:11px; margin-bottom:6px;'>Onaylamak için terminalde çalıştır:</div>
                    <code style='color:#00ff88; font-size:14px; font-weight:bold;
                                 background:#0d2a0d; padding:6px 12px; border-radius:4px; display:block;'>
                        python manage.py onayla --kod {kod}
                    </code>
                </div>
            </div>"""

        return f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'></head>
<body style='font-family: Segoe UI, Arial, sans-serif; background:#0a0a1a; color:#e0e0e0; margin:0; padding:20px;'>
<div style='max-width:640px; margin:0 auto;'>

    <div style='background:linear-gradient(135deg, #1a1a2e, #16213e); padding:28px; border-radius:14px;
                text-align:center; margin-bottom:20px; border:1px solid #2a2a4e;'>
        <h1 style='color:#e94560; margin:0; font-size:32px; letter-spacing:4px;'>⚡ ATHENA</h1>
        <p style='color:#7070a0; margin:8px 0 0; font-size:13px;'>Günlük Yatırım Raporu — {simdi:%d %B %Y %H:%M}</p>
        <div style='margin-top:12px; display:flex; justify-content:center; gap:20px;'>
            <div style='text-align:center;'>
                <div style='color:#ffcc00; font-size:20px; font-weight:bold;'>{butce:,.0f} TL</div>
                <div style='color:#7070a0; font-size:11px;'>Bütçe</div>
            </div>
            <div style='text-align:center;'>
                <div style='color:{renk}; font-size:20px; font-weight:bold; text-transform:uppercase;'>{risk}</div>
                <div style='color:#7070a0; font-size:11px;'>Risk</div>
            </div>
            <div style='text-align:center;'>
                <div style='color:#00ff88; font-size:20px; font-weight:bold;'>TOP 3</div>
                <div style='color:#7070a0; font-size:11px;'>Öneri</div>
            </div>
        </div>
    </div>

    <div style='background:#16213e; border-radius:10px; padding:16px; margin-bottom:16px;
                border:1px solid #2a2a4e;'>
        <p style='margin:0; color:#aaa; font-size:13px; line-height:1.7;'>
            📌 <strong style='color:#fff;'>Nasıl kullanılır?</strong><br>
            1. Aşağıdaki 3 öneriyi incele<br>
            2. Beğendiğini Yapıkredi uygulamasından al<br>
            3. Terminalde onay komutunu çalıştır → Athena izlemeye başlar<br>
            4. Stop-loss veya hedef fiyata ulaşınca Athena sana mail atar
        </p>
    </div>

    {oneriler_html}

    <div style='background:#150505; border:1px solid #441111; border-radius:8px;
                padding:12px; margin-top:20px;'>
        <p style='color:#884444; font-size:11px; margin:0; line-height:1.6;'>
            ⚠️ Bu analizler kişisel bilgilendirme amaçlıdır, yatırım tavsiyesi değildir.
            Geçmiş performans gelecek getiriyi garanti etmez.
        </p>
    </div>
</div>
</body></html>"""
