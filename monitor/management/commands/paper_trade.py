"""
Athena Paper Trading — Sanal Para ile Test
==========================================

Kullanım:
  python manage.py paper_trade --baslat          → Tüm piyasayı tara, en iyi fırsatları aç
  python manage.py paper_trade --guncelle        → Açık işlemleri güncelle, stop/hedef kontrolü
  python manage.py paper_trade --rapor           → Detaylı performans raporu + mail at
  python manage.py paper_trade --baslat --butce 5000 --risk yuksek
  python manage.py paper_trade --baslat --kategori hisse   → Sadece BIST hisseleri
  python manage.py paper_trade --baslat --kategori emtia   → Sadece altın/gümüş/petrol
  python manage.py paper_trade --baslat --kategori kripto  → Sadece kripto
  python manage.py paper_trade --baslat --kategori doviz   → Sadece döviz

Kısa vade: stop -%7, hedef +%12, max 7 gün
Uzun vade: stop -%12, hedef +%25, max 90 gün
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import django.utils.timezone as tz


class Command(BaseCommand):
    help = 'Paper trading — sanal para ile Athena sinyallerini test et'

    def add_arguments(self, parser):
        parser.add_argument('--baslat',    action='store_true', help='Yeni sanal işlemler aç')
        parser.add_argument('--guncelle',  action='store_true', help='Açık işlemleri güncelle')
        parser.add_argument('--rapor',     action='store_true', help='Performans raporu')
        parser.add_argument('--butce',     type=float, default=1000, help='Her işlem için sanal bütçe (TL)')
        parser.add_argument('--risk',      type=str, default='orta',
                            choices=['dusuk', 'orta', 'yuksek'])
        parser.add_argument('--temizle',   action='store_true', help='Tüm paper trade kayıtlarını sil')
        parser.add_argument('--max_islem', type=int, default=5,
                            help='En fazla kaç yeni işlem açılsın (varsayılan: 5)')
        parser.add_argument('--kategori',  type=str, default='hepsi',
                            choices=['hepsi', 'hisse', 'emtia', 'doviz', 'kripto'],
                            help='Hangi kategori taransın (varsayılan: hepsi)')

    def handle(self, *args, **options):
        if options['temizle']:
            self._temizle()
            return

        if options['baslat']:
            self._yeni_islemler_ac(
                butce=options['butce'],
                risk=options['risk'],
                max_islem=options['max_islem'],
                kategori=options['kategori'],
            )

        if options['guncelle']:
            self._islemleri_guncelle()

        if options['rapor']:
            self._rapor_goster_ve_mail_at()

        # Hiçbir flag verilmemişse hepsini yap
        if not any([options['baslat'], options['guncelle'], options['rapor'], options['temizle']]):
            self._yeni_islemler_ac(
                butce=options['butce'],
                risk=options['risk'],
                max_islem=options['max_islem'],
                kategori=options['kategori'],
            )
            self._islemleri_guncelle()
            self._rapor_goster_ve_mail_at()

    # ─────────────────────────────────────────────────────────────────────────
    def _yeni_islemler_ac(self, butce: float, risk: str, max_islem: int, kategori: str):
        from stocks.services import (
            get_stock_data, get_technical_indicators, get_fundamental_data,
            ALL_BIST_STOCKS, COMMODITY_SYMBOLS, FOREX_SYMBOLS, CRYPTO_SYMBOLS,
        )
        from monitor.scanner import compute_score, _get_signal_label
        from monitor.models import PaperTrade

        risk_params = {
            'dusuk':  {'kisa_stop': 4,  'kisa_hedef': 8,  'uzun_stop': 7,  'uzun_hedef': 15},
            'orta':   {'kisa_stop': 7,  'kisa_hedef': 12, 'uzun_stop': 12, 'uzun_hedef': 25},
            'yuksek': {'kisa_stop': 10, 'kisa_hedef': 20, 'uzun_stop': 15, 'uzun_hedef': 40},
        }
        rp = risk_params.get(risk, risk_params['orta'])

        # ── Taranacak Semboller ───────────────────────────────────────────────
        semboller_by_kategori = {
            'hisse': ALL_BIST_STOCKS,
            'emtia': list(COMMODITY_SYMBOLS.keys()),
            'doviz': list(FOREX_SYMBOLS.keys()),
            'kripto': list(CRYPTO_SYMBOLS.keys()),
        }

        if kategori == 'hepsi':
            # Tümünü birleştir, hisseler önce
            tum_semboller = (
                ALL_BIST_STOCKS
                + list(COMMODITY_SYMBOLS.keys())
                + list(FOREX_SYMBOLS.keys())
                + list(CRYPTO_SYMBOLS.keys())
            )
        else:
            tum_semboller = semboller_by_kategori.get(kategori, ALL_BIST_STOCKS)

        self.stdout.write(self.style.HTTP_INFO(
            f"\n[{tz.now():%H:%M}] Piyasa taraması başlıyor... "
            f"({len(tum_semboller)} sembol | Bütçe: {butce:,.0f} TL | Risk: {risk} | Kategori: {kategori})"
        ))

        adaylar = []
        hata_sayisi = 0

        for sembol in tum_semboller:
            try:
                stock = get_stock_data(sembol)
                if not stock or stock.get('price', 0) == 0:
                    continue

                tech = get_technical_indicators(sembol)
                if not tech.get('rsi'):
                    continue

                # Hisseler için fundamental, emtia/döviz/kripto için yok
                fund = None
                if sembol in ALL_BIST_STOCKS:
                    try:
                        fund = get_fundamental_data(sembol)
                    except Exception:
                        pass

                puan, gerekceler = compute_score(tech, stock, fund)

                if puan >= 3:
                    # Kategori etiketi ekle
                    if sembol in COMMODITY_SYMBOLS:
                        kat = 'emtia'
                    elif sembol in FOREX_SYMBOLS:
                        kat = 'doviz'
                    elif sembol in CRYPTO_SYMBOLS:
                        kat = 'kripto'
                    else:
                        kat = 'hisse'

                    adaylar.append({
                        'sembol':    sembol,
                        'puan':      puan,
                        'sinyal':    _get_signal_label(puan),
                        'fiyat':     stock['price'],
                        'gerekceler': gerekceler,
                        'kategori':  kat,
                    })

                if len(adaylar) % 20 == 0 and adaylar:
                    self.stdout.write(f"  [{len(adaylar)} aday bulundu, tarama devam ediyor...]")

            except Exception as e:
                hata_sayisi += 1
                continue

        self.stdout.write(
            f"\n  Tarama tamamlandı: {len(tum_semboller)} sembol tarandı, "
            f"{len(adaylar)} aday bulundu, {hata_sayisi} hata"
        )

        # En yüksek puandan sırala, en iyi N tane al
        adaylar.sort(key=lambda x: x['puan'], reverse=True)
        en_iyiler = adaylar[:max_islem]

        acilan = 0

        for a in en_iyiler:
            for strateji, stop_k, hedef_k in [
                ('kisa', 'kisa_stop', 'kisa_hedef'),
                ('uzun', 'uzun_stop', 'uzun_hedef'),
            ]:
                if PaperTrade.objects.filter(sembol=a['sembol'], strateji=strateji, durum='acik').exists():
                    self.stdout.write(f"  Atla: {a['sembol']} [{strateji}] zaten açık")
                    continue

                adet = butce / a['fiyat']
                pt = PaperTrade.objects.create(
                    sembol=a['sembol'],
                    strateji=strateji,
                    giris_fiyat=a['fiyat'],
                    adet=adet,
                    sanal_butce=butce,
                    stop_pct=rp[stop_k],
                    hedef_pct=rp[hedef_k],
                    giris_skoru=a['puan'],
                    giris_sinyali=a['sinyal'],
                    not_alani=f"[{a['kategori'].upper()}] " + ' | '.join(a['gerekceler'][:3]),
                )
                acilan += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  ✅ [{'KISA' if strateji=='kisa' else 'UZUN'}] "
                    f"[{a['kategori'].upper()}] {a['sembol']:10s} | "
                    f"Giriş: {a['fiyat']:.4f} | Stop: {pt.stop_fiyat:.4f} | "
                    f"Hedef: {pt.hedef_fiyat:.4f} | Skor: {a['puan']:+d}"
                ))

        self.stdout.write(f"\n  {acilan} yeni paper trade açıldı.")

    # ─────────────────────────────────────────────────────────────────────────
    def _islemleri_guncelle(self):
        from monitor.models import PaperTrade
        from stocks.services import get_stock_data

        aciklar = PaperTrade.objects.filter(durum='acik')
        if not aciklar.exists():
            self.stdout.write("  Açık paper trade yok.")
            return

        self.stdout.write(self.style.HTTP_INFO(
            f"\n[{tz.now():%H:%M}] {aciklar.count()} açık işlem güncelleniyor..."
        ))

        for pt in aciklar:
            try:
                stock = get_stock_data(pt.sembol)
                if not stock or stock.get('price', 0) == 0:
                    continue

                guncel    = stock['price']
                giris     = float(pt.giris_fiyat)
                kz_pct    = ((guncel - giris) / giris) * 100
                kz_tl     = (guncel - giris) * float(pt.adet)
                maks_gun  = 7 if pt.strateji == 'kisa' else 90
                gecen_gun = (tz.now() - pt.acilis_tarihi).days
                kapandi   = False

                if kz_pct <= -float(pt.stop_pct):
                    pt.durum = 'stop'
                    ikon     = "⛔ STOP-LOSS"
                    kapandi  = True
                elif kz_pct >= float(pt.hedef_pct):
                    pt.durum = 'hedef'
                    ikon     = "🎯 HEDEF"
                    kapandi  = True
                elif gecen_gun >= maks_gun:
                    pt.durum = 'kapali'
                    ikon     = "⏰ SÜRE DOLDU"
                    kapandi  = True
                else:
                    ikon = "📊 açık"

                if kapandi:
                    pt.cikis_fiyat  = guncel
                    pt.cikis_tarihi = tz.now()
                    pt.kaz_kayip_pct = round(kz_pct, 2)
                    pt.kaz_kayip_tl  = round(kz_tl, 2)

                pt.save()

                renk = self.style.SUCCESS if kz_pct >= 0 else self.style.ERROR
                self.stdout.write(renk(
                    f"  [{pt.get_strateji_display()[:4]}] {pt.sembol:10s} | "
                    f"Giriş: {giris:.4f} → Şimdi: {guncel:.4f} | "
                    f"K/Z: {kz_pct:+.2f}% ({kz_tl:+.0f} TL)"
                    + (f"  → {ikon}" if kapandi else "")
                ))

                # Yapıkredi uyarısı: stop veya hedefe yaklaşıldıysa ekranda belirt
                if not kapandi:
                    if kz_pct <= -float(pt.stop_pct) * 0.8:
                        self.stdout.write(self.style.WARNING(
                            f"    ⚠️ STOP'A YAKLAŞIYOR! Stop: {pt.stop_fiyat:.4f} | "
                            f"Yapıkredi'de dikkatli izle!"
                        ))
                    elif kz_pct >= float(pt.hedef_pct) * 0.8:
                        self.stdout.write(self.style.SUCCESS(
                            f"    🔔 HEDEFE YAKLAŞIYOR! Hedef: {pt.hedef_fiyat:.4f} | "
                            f"Yapıkredi'den satmayı değerlendir!"
                        ))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  {pt.sembol}: {e}"))

    # ─────────────────────────────────────────────────────────────────────────
    def _rapor_goster_ve_mail_at(self):
        from monitor.models import PaperTrade

        simdi   = tz.now()
        aciklar = PaperTrade.objects.filter(durum='acik')
        kapalilar = PaperTrade.objects.exclude(durum='acik')

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("  ATHENA PAPER TRADING RAPORU")
        self.stdout.write(f"  {simdi:%d.%m.%Y %H:%M}")
        self.stdout.write("=" * 70)

        if kapalilar.exists():
            for strateji in ['kisa', 'uzun']:
                islemler = kapalilar.filter(strateji=strateji)
                if not islemler.exists():
                    continue
                kazananlar = islemler.filter(kaz_kayip_pct__gt=0).count()
                toplam_kz_tl = sum(float(i.kaz_kayip_tl or 0) for i in islemler)
                ort_kz  = sum(float(i.kaz_kayip_pct or 0) for i in islemler) / islemler.count()
                basari  = kazananlar / islemler.count() * 100
                etiket  = "KISA VADE" if strateji == 'kisa' else "UZUN VADE"
                renk = self.style.SUCCESS if toplam_kz_tl >= 0 else self.style.ERROR
                self.stdout.write(renk(
                    f"\n  [{etiket}] {islemler.count()} işlem | "
                    f"Başarı: %{basari:.0f} | Ort K/Z: {ort_kz:+.2f}% | Net: {toplam_kz_tl:+.0f} TL"
                ))
                for i in islemler.order_by('-kaz_kayip_pct'):
                    d_ikon = {'hedef': '🎯 HEDEF', 'stop': '⛔ STOP', 'kapali': '⏰ SÜRE'}.get(i.durum, '?')
                    kk  = float(i.kaz_kayip_pct or 0)
                    r   = self.style.SUCCESS if kk >= 0 else self.style.ERROR
                    gun = (i.cikis_tarihi - i.acilis_tarihi).days if i.cikis_tarihi else '?'
                    self.stdout.write(r(
                        f"    {d_ikon:10s} {i.sembol:10s} | "
                        f"Giriş: {float(i.giris_fiyat):.4f} → Çıkış: {float(i.cikis_fiyat):.4f} | "
                        f"{kk:+.2f}% ({float(i.kaz_kayip_tl or 0):+.0f} TL) | "
                        f"{gun} gün | Skor: {i.giris_skoru:+d}"
                    ))

        if aciklar.exists():
            self.stdout.write(self.style.HTTP_INFO("\n  AÇIK İŞLEMLER:"))
            from stocks.services import get_stock_data
            for pt in aciklar:
                try:
                    stock  = get_stock_data(pt.sembol)
                    guncel = stock['price'] if stock else float(pt.giris_fiyat)
                    giris  = float(pt.giris_fiyat)
                    kz_pct = ((guncel - giris) / giris) * 100
                    kz_tl  = (guncel - giris) * float(pt.adet)
                    gecen  = (simdi - pt.acilis_tarihi).days
                    r = self.style.SUCCESS if kz_pct >= 0 else self.style.ERROR
                    self.stdout.write(r(
                        f"  [{pt.get_strateji_display()[:4]}] {pt.sembol:10s} | "
                        f"Giriş: {giris:.4f} → Şimdi: {guncel:.4f} | "
                        f"{kz_pct:+.2f}% ({kz_tl:+.0f} TL) | {gecen} gün | "
                        f"Stop: {pt.stop_fiyat:.4f} | Hedef: {pt.hedef_fiyat:.4f}"
                    ))
                except Exception:
                    pass

        if kapalilar.exists():
            toplam_net = sum(float(i.kaz_kayip_tl or 0) for i in kapalilar)
            kazanan    = kapalilar.filter(kaz_kayip_pct__gt=0).count()
            toplam     = kapalilar.count()
            self.stdout.write("\n" + "=" * 70)
            r = self.style.SUCCESS if toplam_net >= 0 else self.style.ERROR
            self.stdout.write(r(
                f"  GENEL: {toplam} kapalı işlem | "
                f"Başarı: %{kazanan/toplam*100:.0f} | Net: {toplam_net:+.0f} TL"
            ))
            self.stdout.write("=" * 70)
            try:
                self._rapor_maili_gonder(kapalilar, aciklar, simdi)
                from django.conf import settings
                self.stdout.write(f"\n  📧 Mail gönderildi: {settings.ATHENA_ALERT_EMAIL}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Mail hatası: {e}"))
        else:
            self.stdout.write("  Henüz kapanan işlem yok.")
            self.stdout.write("=" * 70)

    # ─────────────────────────────────────────────────────────────────────────
    def _rapor_maili_gonder(self, kapalilar, aciklar, simdi):
        from django.core.mail import send_mail
        from django.conf import settings
        from stocks.services import get_stock_data

        toplam_net = sum(float(i.kaz_kayip_tl or 0) for i in kapalilar)
        kazanan    = kapalilar.filter(kaz_kayip_pct__gt=0).count()
        toplam     = kapalilar.count()
        basari     = kazanan / toplam * 100 if toplam else 0
        net_renk   = '#00ff88' if toplam_net >= 0 else '#ff4444'

        satirlar = ""
        for i in kapalilar.order_by('-kaz_kayip_pct'):
            d_ikon = {'hedef': '🎯', 'stop': '⛔', 'kapali': '⏰'}.get(i.durum, '?')
            kk     = float(i.kaz_kayip_pct or 0)
            kk_tl  = float(i.kaz_kayip_tl or 0)
            r      = '#00ff88' if kk >= 0 else '#ff4444'
            gun    = (i.cikis_tarihi - i.acilis_tarihi).days if i.cikis_tarihi else '-'
            # Kategori bilgisi not_alani'ndan parse et
            kat    = i.not_alani[:10] if i.not_alani else ''
            satirlar += f"""<tr>
                <td style='padding:8px;color:#fff;'>{d_ikon} {i.sembol}</td>
                <td style='padding:8px;color:#aaa;font-size:11px;'>{kat}</td>
                <td style='padding:8px;color:#aaa;'>{i.get_strateji_display()[:4]}</td>
                <td style='padding:8px;color:#aaa;'>{float(i.giris_fiyat):.4f}</td>
                <td style='padding:8px;color:#aaa;'>{float(i.cikis_fiyat):.4f}</td>
                <td style='padding:8px;color:{r};font-weight:bold;'>{kk:+.2f}%</td>
                <td style='padding:8px;color:{r};font-weight:bold;'>{kk_tl:+.0f} TL</td>
                <td style='padding:8px;color:#aaa;'>{gun} gün</td>
                <td style='padding:8px;color:#6699ff;'>{i.giris_skoru:+d}</td>
            </tr>"""

        acik_satirlar = ""
        for pt in aciklar:
            try:
                stock  = get_stock_data(pt.sembol)
                guncel = stock['price'] if stock else float(pt.giris_fiyat)
                giris  = float(pt.giris_fiyat)
                kz_pct = ((guncel - giris) / giris) * 100
                kz_tl  = (guncel - giris) * float(pt.adet)
                r      = '#00ff88' if kz_pct >= 0 else '#ff4444'
                gecen  = (simdi - pt.acilis_tarihi).days
                acik_satirlar += f"""<tr>
                    <td style='padding:8px;color:#fff;'>📈 {pt.sembol}</td>
                    <td style='padding:8px;color:#aaa;font-size:11px;'></td>
                    <td style='padding:8px;color:#aaa;'>{pt.get_strateji_display()[:4]}</td>
                    <td style='padding:8px;color:#aaa;'>{giris:.4f}</td>
                    <td style='padding:8px;color:#aaa;'>{guncel:.4f}</td>
                    <td style='padding:8px;color:{r};font-weight:bold;'>{kz_pct:+.2f}%</td>
                    <td style='padding:8px;color:{r};font-weight:bold;'>{kz_tl:+.0f} TL</td>
                    <td style='padding:8px;color:#aaa;'>{gecen} gün</td>
                    <td style='padding:8px;color:#6699ff;'>{pt.giris_skoru:+d}</td>
                </tr>"""
            except Exception:
                pass

        th = "<th style='padding:10px;color:#7070a0;text-align:left;font-size:12px;'>"
        thead = (
            "<thead><tr style='background:#0a0a2e;'>"
            + th + "Sembol</th>" + th + "Kat.</th>" + th + "Tip</th>"
            + th + "Giriş</th>" + th + "Çıkış</th>" + th + "K/Z %</th>"
            + th + "K/Z TL</th>" + th + "Süre</th>" + th + "Skor</th>"
            + "</tr></thead>"
        )

        tablo = f"<table style='width:100%;border-collapse:collapse;background:#16213e;border-radius:10px;'>{thead}<tbody>{satirlar}</tbody></table>"

        acik_tablo = ""
        if acik_satirlar:
            acik_tablo = f"<h3 style='color:#fff;margin:20px 0 10px;'>Açık İşlemler</h3><table style='width:100%;border-collapse:collapse;background:#16213e;border-radius:10px;'>{thead}<tbody>{acik_satirlar}</tbody></table>"

        html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'></head>
<body style='font-family:Segoe UI,Arial,sans-serif;background:#0a0a1a;color:#e0e0e0;padding:20px;'>
<div style='max-width:800px;margin:0 auto;'>
  <div style='background:linear-gradient(135deg,#1a1a2e,#16213e);padding:24px;border-radius:12px;
              text-align:center;margin-bottom:20px;border:1px solid #2a2a4e;'>
    <h1 style='color:#e94560;margin:0;font-size:26px;letter-spacing:3px;'>ATHENA</h1>
    <h2 style='color:#fff;margin:8px 0 0;font-size:18px;'>Paper Trading Raporu</h2>
    <p style='color:#7070a0;margin:4px 0 0;font-size:12px;'>{simdi:%d %B %Y %H:%M}</p>
  </div>
  <div style='display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;'>
    <div style='flex:1;background:#16213e;border-radius:10px;padding:16px;
                border:2px solid {net_renk};text-align:center;min-width:120px;'>
      <div style='color:{net_renk};font-size:24px;font-weight:900;'>{toplam_net:+.0f} TL</div>
      <div style='color:#7070a0;font-size:11px;margin-top:4px;'>Net K/Z</div>
    </div>
    <div style='flex:1;background:#16213e;border-radius:10px;padding:16px;
                border:1px solid #2a2a4e;text-align:center;min-width:120px;'>
      <div style='color:#00ff88;font-size:24px;font-weight:900;'>%{basari:.0f}</div>
      <div style='color:#7070a0;font-size:11px;margin-top:4px;'>Başarı Oranı</div>
    </div>
    <div style='flex:1;background:#16213e;border-radius:10px;padding:16px;
                border:1px solid #2a2a4e;text-align:center;min-width:120px;'>
      <div style='color:#6699ff;font-size:24px;font-weight:900;'>{toplam}</div>
      <div style='color:#7070a0;font-size:11px;margin-top:4px;'>Toplam İşlem</div>
    </div>
    <div style='flex:1;background:#16213e;border-radius:10px;padding:16px;
                border:1px solid #2a2a4e;text-align:center;min-width:120px;'>
      <div style='color:#ffcc00;font-size:24px;font-weight:900;'>{aciklar.count()}</div>
      <div style='color:#7070a0;font-size:11px;margin-top:4px;'>Açık</div>
    </div>
  </div>
  <h3 style='color:#fff;margin:20px 0 10px;'>Kapalı İşlemler</h3>
  {tablo}
  {acik_tablo}
  <div style='margin-top:20px;padding:16px;background:#16213e;border-radius:10px;
              border:1px solid #2a2a4e;'>
    <p style='color:#7070a0;font-size:12px;margin:0;'>
      💡 Yapıkredi Mobil üzerinden işlem yapın. Stop-loss ve hedef fiyatlara göre hareket edin.
    </p>
  </div>
</div></body></html>"""

        send_mail(
            subject=f"Athena Paper Trading | {simdi:%d %b} | Net: {toplam_net:+.0f} TL | %{basari:.0f} başarı",
            message=f"{toplam} işlem, net {toplam_net:+.0f} TL",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.ATHENA_ALERT_EMAIL],
            html_message=html,
            fail_silently=False,
        )

    # ─────────────────────────────────────────────────────────────────────────
    def _temizle(self):
        from monitor.models import PaperTrade
        sayi = PaperTrade.objects.count()
        PaperTrade.objects.all().delete()
        self.stdout.write(self.style.WARNING(f"  {sayi} paper trade kaydı silindi."))