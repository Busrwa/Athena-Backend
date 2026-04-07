"""
Django Management Komutu: python manage.py portfolio_watch
Portföydeki hisseleri anlık izler, stop-loss ve hedef uyarısı verir.

monitor/management/commands/portfolio_watch.py dosyasına koy.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal


class Command(BaseCommand):
    help = 'Portföyü anlık izle — stop-loss ve hedef fiyat uyarıları'

    def handle(self, *args, **options):
        from portfolio.models import Portfolio
        from monitor.models import InvestmentPlan
        from stocks.services import get_stock_data, get_technical_indicators
        from monitor.scanner import compute_score
        from monitor.email_service import send_signal_alert

        holdings = list(Portfolio.objects.all())
        if not holdings:
            self.stdout.write(self.style.WARNING("Portföyde hisse yok."))
            return

        self.stdout.write(self.style.HTTP_INFO(
            f"\n[{timezone.now():%H:%M:%S}] Portföy izleme — {len(holdings)} hisse\n"
        ))

        for holding in holdings:
            symbol = holding.symbol
            try:
                stock = get_stock_data(symbol)
                if not stock:
                    continue

                current = stock['price']
                cost    = float(holding.avg_cost)
                qty     = float(holding.quantity)
                pl_pct  = ((current - cost) / cost) * 100
                pl_tl   = (current - cost) * qty

                plan = InvestmentPlan.objects.filter(symbol=symbol, is_active=True).first()
                stop_pct   = float(plan.stop_loss_pct)    if plan else 8.0
                target_pct = float(plan.target_return_pct) if plan else 15.0

                # Durum ikonu
                if pl_pct <= -stop_pct:
                    ikon = "🔴 STOP-LOSS!"
                    stil = self.style.ERROR
                elif pl_pct >= target_pct:
                    ikon = "🟢 HEDEF!"
                    stil = self.style.SUCCESS
                elif pl_pct >= target_pct * 0.7:
                    ikon = "🟡 Hedefe yakın"
                    stil = self.style.WARNING
                elif pl_pct >= 0:
                    ikon = "✅ Kârda"
                    stil = self.style.SUCCESS
                else:
                    ikon = "🔻 Zararda"
                    stil = self.style.ERROR

                self.stdout.write(stil(
                    f"  {symbol:8s} | Maliyet: {cost:.2f} → Güncel: {current:.2f} TL | "
                    f"K/Z: {pl_pct:+.1f}% ({pl_tl:+.0f} TL) | "
                    f"Stop: -%{stop_pct:.0f} | Hedef: +%{target_pct:.0f} | {ikon}"
                ))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  {symbol}: {e}"))

        self.stdout.write("")