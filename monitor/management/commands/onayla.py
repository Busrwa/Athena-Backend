"""
Athena Onay Komutu
python manage.py onayla --kod BIMAS-061023

Günlük rapor mailindeki onay kodunu kullanarak
seçilen varlığı aktif izlemeye alır.
Bundan sonra Athena stop-loss / hedef fiyata ulaşınca mail atar.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Öneriyi onayla ve izlemeye al — python manage.py onayla --kod BIMAS-061023'

    def add_arguments(self, parser):
        parser.add_argument('--kod', type=str, required=True,
                            help='Maildeki onay kodu (örn: BIMAS-061023)')
        parser.add_argument('--liste', action='store_true',
                            help='Onay bekleyen önerileri listele')

    def handle(self, *args, **options):
        from monitor.models import InvestmentPlan
        from stocks.services import get_stock_data

        # Onay bekleyenleri listele
        if options['liste']:
            bekleyenler = InvestmentPlan.objects.filter(
                is_active=False,
                athena_advice__startswith='ONAY_BEKLENIYOR'
            )
            if not bekleyenler:
                self.stdout.write(self.style.WARNING("Onay bekleyen öneri yok."))
                return
            self.stdout.write(self.style.HTTP_INFO("\nOnay bekleyen öneriler:"))
            for p in bekleyenler:
                kod = ""
                for parca in p.athena_advice.split('|'):
                    if parca.startswith('KOD:'):
                        kod = parca.replace('KOD:', '')
                self.stdout.write(
                    f"  {p.symbol:12s} | {float(p.budget_tl):,.0f} TL | "
                    f"Giriş: {float(p.entry_price):.2f} | Kod: {kod}"
                )
            self.stdout.write("")
            return

        # Onay kodu ile aktifte
        kod = options['kod'].strip().upper()
        self.stdout.write(f"\n🔍 Onay kodu aranıyor: {kod}")

        # Kodu içeren planı bul
        plan = None
        for p in InvestmentPlan.objects.filter(is_active=False):
            if f'KOD:{kod}' in p.athena_advice or kod.startswith(p.symbol):
                plan = p
                break

        # Sembol adından da bul
        if not plan:
            sembol = kod.split('-')[0]
            plan = InvestmentPlan.objects.filter(
                symbol=sembol, is_active=False
            ).first()

        if not plan:
            self.stdout.write(self.style.ERROR(
                f"❌ '{kod}' kodu bulunamadı.\n"
                "Mevcut bekleyen önerileri görmek için:\n"
                "  python manage.py onayla --liste"
            ))
            return

        # Güncel fiyatı al
        try:
            stock = get_stock_data(plan.symbol)
            guncel_fiyat = stock['price'] if stock else float(plan.entry_price)
        except:
            guncel_fiyat = float(plan.entry_price)

        # Planı aktif et
        plan.is_active = True
        plan.entry_price = guncel_fiyat
        plan.athena_advice = (
            f"✅ {timezone.now():%d.%m.%Y %H:%M} tarihinde onaylandı. "
            f"Giriş: {guncel_fiyat:.2f} | "
            f"Stop: -%{float(plan.stop_loss_pct):.0f} | "
            f"Hedef: +%{float(plan.target_return_pct):.0f}"
        )
        plan.save()

        stop_fiyat = round(guncel_fiyat * (1 - float(plan.stop_loss_pct) / 100), 2)
        hedef_fiyat = round(guncel_fiyat * (1 + float(plan.target_return_pct) / 100), 2)

        self.stdout.write(self.style.SUCCESS(f"""
╔══════════════════════════════════════════════╗
  ✅ {plan.symbol} İZLEMEYE ALINDI
╚══════════════════════════════════════════════╝
  Giriş Fiyatı : {guncel_fiyat:.2f}
  Stop-Loss    : {stop_fiyat:.2f}  (-%{float(plan.stop_loss_pct):.0f})
  Hedef        : {hedef_fiyat:.2f}  (+%{float(plan.target_return_pct):.0f})
  Bütçe        : {float(plan.budget_tl):,.0f} TL

  Athena artık {plan.symbol}'i her taramada kontrol edecek.
  Stop veya hedefe ulaşınca mail atacak.

  İptal etmek için:
    python manage.py plans {plan.symbol} deactivate
"""))

        # Onay maili gönder
        try:
            self._onay_maili_gonder(plan, guncel_fiyat, stop_fiyat, hedef_fiyat)
            self.stdout.write(f"  📧 Onay maili gönderildi.")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  Mail gönderilemedi: {e}"))

    def _onay_maili_gonder(self, plan, giris, stop, hedef):
        from django.core.mail import send_mail
        from django.conf import settings

        html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'></head>
<body style='font-family:Segoe UI,Arial,sans-serif; background:#0a0a1a; color:#e0e0e0; padding:20px;'>
<div style='max-width:500px; margin:0 auto;'>
    <div style='background:linear-gradient(135deg,#0a2a1a,#16213e); padding:24px; border-radius:12px;
                text-align:center; border:2px solid #00cc66;'>
        <h1 style='color:#00ff88; margin:0; font-size:28px;'>✅ İZLEMEYE ALINDI</h1>
        <h2 style='color:#fff; margin:8px 0 0; font-size:22px;'>{plan.symbol}</h2>
    </div>
    <div style='background:#16213e; border-radius:10px; padding:20px; margin:16px 0; border:1px solid #2a2a4e;'>
        <div style='display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2a2a4e;'>
            <span style='color:#7070a0;'>Giriş Fiyatı</span>
            <span style='color:#fff; font-weight:bold;'>{giris:.2f}</span>
        </div>
        <div style='display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2a2a4e;'>
            <span style='color:#7070a0;'>Stop-Loss (SAT!)</span>
            <span style='color:#ff6666; font-weight:bold;'>{stop:.2f} (-%{float(plan.stop_loss_pct):.0f})</span>
        </div>
        <div style='display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2a2a4e;'>
            <span style='color:#7070a0;'>Hedef Fiyat (KÂR AL!)</span>
            <span style='color:#00ff88; font-weight:bold;'>{hedef:.2f} (+%{float(plan.target_return_pct):.0f})</span>
        </div>
        <div style='display:flex; justify-content:space-between; padding:8px 0;'>
            <span style='color:#7070a0;'>Bütçe</span>
            <span style='color:#ffcc00; font-weight:bold;'>{float(plan.budget_tl):,.0f} TL</span>
        </div>
    </div>
    <p style='color:#7070a0; font-size:12px; text-align:center;'>
        Athena her 30 dakikada bir kontrol edecek.<br>
        Stop veya hedefe ulaşınca tekrar mail atacak.
    </p>
</div>
</body></html>"""

        send_mail(
            subject=f"✅ {plan.symbol} İzlemeye Alındı — Athena",
            message=f"{plan.symbol} izlemeye alındı. Stop: {stop} | Hedef: {hedef}",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.ATHENA_ALERT_EMAIL],
            html_message=html,
            fail_silently=True,
        )
