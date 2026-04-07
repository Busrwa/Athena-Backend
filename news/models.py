from django.db import models


class NewsItem(models.Model):
    title = models.CharField(max_length=500)
    summary = models.TextField(blank=True, default='')
    link = models.URLField(max_length=1000, unique=True)
    source = models.CharField(max_length=100, default='KAP')
    symbol = models.CharField(max_length=20, blank=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.symbol or 'GENEL'}] {self.title[:60]}"

    class Meta:
        ordering = ['-published_at', '-fetched_at']
        indexes = [
            models.Index(fields=['symbol']),
            models.Index(fields=['published_at']),
        ]
