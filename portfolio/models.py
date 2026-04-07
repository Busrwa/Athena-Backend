from django.db import models


class Watchlist(models.Model):
    """Takip listesi — portfoy disindaki hisseler"""
    symbol = models.CharField(max_length=20, unique=True)
    added_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Watchlist: {self.symbol}"

    class Meta:
        ordering = ['-added_at']


class Portfolio(models.Model):
    symbol = models.CharField(max_length=20, unique=True)  # unique eklendi
    name = models.CharField(max_length=200, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    avg_cost = models.DecimalField(max_digits=12, decimal_places=2)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.symbol} x{self.quantity} @ {self.avg_cost}"

    class Meta:
        ordering = ['-added_at']


class Transaction(models.Model):
    BUY = 'buy'
    SELL = 'sell'
    TYPE_CHOICES = [(BUY, 'Alış'), (SELL, 'Satış')]

    symbol = models.CharField(max_length=20)
    transaction_type = models.CharField(max_length=4, choices=TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.transaction_type.upper()} {self.symbol} x{self.quantity} @ {self.price}"

    class Meta:
        ordering = ['-date']
