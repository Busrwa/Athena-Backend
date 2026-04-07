"""
Django Management Komutu: python manage.py run_monitor
monitor/management/commands/run_monitor.py dosyasına koy.

Klasör yapısı:
monitor/
  management/
    __init__.py
    commands/
      __init__.py
      run_monitor.py   ← bu dosya
"""
from django.core.management.base import BaseCommand
from monitor.scanner import scan_and_alert
from django.utils import timezone


class Command(BaseCommand):
    help = 'Piyasayı tara, güçlü sinyallerde mail gönder'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Mail göndermeden sadece sinyalleri göster'
        )
        parser.add_argument(
            '--symbol', type=str, default='',
            help='Sadece belirli bir sembolü tara (örn: --symbol THYAO)'
        )

    def handle(self, *args, **options):
        now = timezone.now()
        self.stdout.write(
            self.style.HTTP_INFO(f"\n[{now:%Y-%m-%d %H:%M}] ⚡ Athena tarama başlıyor...")
        )

        dry_run = options.get('dry_run', False)
        symbol  = options.get('symbol', '').upper()

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] Mail gönderilmeyecek, sadece sinyaller gösterilecek"))
            self._dry_run(symbol)
        else:
            alerts = scan_and_alert()
            self.stdout.write(
                self.style.SUCCESS(f"[TAMAMLANDI] {alerts} uyarı maili gönderildi.")
            )

    def _dry_run(self, filter_symbol=''):
        """Mail atmadan tüm sinyalleri ekrana yaz"""
        from stocks.services import get_stock_data, get_technical_indicators, get_fundamental_data, POPULAR_BIST_STOCKS
        from portfolio.models import Portfolio, Watchlist
        from monitor.scanner import compute_score, _get_signal_label

        portfolio_symbols = list(Portfolio.objects.values_list('symbol', flat=True))
        watchlist_symbols = list(Watchlist.objects.values_list('symbol', flat=True))
        scan_symbols = list(set(portfolio_symbols + watchlist_symbols + POPULAR_BIST_STOCKS[:20]))

        if filter_symbol:
            scan_symbols = [filter_symbol]

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
                results.append((symbol, puan, gerekceler, stock))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  {symbol}: {e}"))

        results.sort(key=lambda x: abs(x[1]), reverse=True)

        self.stdout.write("\n" + "="*60)
        self.stdout.write("SİNYAL TABLOSU (en güçlüden en zayıfa)")
        self.stdout.write("="*60)

        for symbol, puan, gerekceler, stock in results:
            signal = _get_signal_label(puan)
            bar = "█" * min(abs(puan), 25)
            color = self.style.SUCCESS if puan > 0 else (self.style.ERROR if puan < 0 else self.style.WARNING)
            self.stdout.write(
                color(f"  {symbol:8s} | {signal:10s} | Skor: {puan:+3d} | {stock['price']:.2f} TL ({stock['change_percent']:+.1f}%) | {bar}")
            )
            if abs(puan) >= 3:
                for g in gerekceler[:3]:
                    self.stdout.write(f"           → {g}")
        self.stdout.write("="*60)