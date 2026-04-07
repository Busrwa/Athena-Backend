from django.db import models

class Stock(models.Model):
    symbol = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    previous_close = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    change_percent = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    volume = models.BigIntegerField(null=True)
    market_cap = models.BigIntegerField(null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.symbol} - {self.price}"

    class Meta:
        ordering = ['symbol']