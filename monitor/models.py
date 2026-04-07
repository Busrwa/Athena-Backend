from django.db import models


class AlertLog(models.Model):
    symbol = models.CharField(max_length=20)
    signal = models.CharField(max_length=10)
    score = models.IntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    email_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    def __str__(self):
        return f"{self.sent_at:%Y-%m-%d %H:%M} | {self.symbol} → {self.signal} ({self.score})"

    class Meta:
        ordering = ['-sent_at']


class InvestmentPlan(models.Model):
    symbol = models.CharField(max_length=20)
    budget_tl = models.DecimalField(max_digits=12, decimal_places=2)
    entry_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_return_pct = models.DecimalField(max_digits=6, decimal_places=2, default=15)
    stop_loss_pct = models.DecimalField(max_digits=6, decimal_places=2, default=7)
    is_active = models.BooleanField(default=True)
    athena_advice = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.symbol} — {self.budget_tl} TL plan"

    class Meta:
        ordering = ['-created_at']


class PaperTrade(models.Model):
    STRATEJI_CHOICES = [
        ('kisa', 'Kısa Vade (3-7 gün)'),
        ('uzun', 'Uzun Vade (1-3 ay)'),
    ]
    DURUM_CHOICES = [
        ('acik',   'Açık'),
        ('kapali', 'Normal Kapandı'),
        ('stop',   'Stop-Loss'),
        ('hedef',  'Hedef Tuttu'),
    ]

    sembol        = models.CharField(max_length=20)
    strateji      = models.CharField(max_length=10, choices=STRATEJI_CHOICES, default='kisa')
    giris_fiyat   = models.DecimalField(max_digits=12, decimal_places=4)
    adet          = models.DecimalField(max_digits=12, decimal_places=4, default=1)
    sanal_butce   = models.DecimalField(max_digits=12, decimal_places=2, default=1000)
    stop_pct      = models.DecimalField(max_digits=6,  decimal_places=2)
    hedef_pct     = models.DecimalField(max_digits=6,  decimal_places=2)
    giris_skoru   = models.IntegerField(default=0)
    giris_sinyali = models.CharField(max_length=20, default='AL')
    acilis_tarihi = models.DateTimeField(auto_now_add=True)

    durum         = models.CharField(max_length=10, choices=DURUM_CHOICES, default='acik')
    cikis_fiyat   = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    cikis_tarihi  = models.DateTimeField(null=True, blank=True)
    kaz_kayip_pct = models.DecimalField(max_digits=8,  decimal_places=2,  null=True, blank=True)
    kaz_kayip_tl  = models.DecimalField(max_digits=12, decimal_places=2,  null=True, blank=True)
    not_alani     = models.TextField(blank=True)

    @property
    def stop_fiyat(self):
        return round(float(self.giris_fiyat) * (1 - float(self.stop_pct) / 100), 4)

    @property
    def hedef_fiyat(self):
        return round(float(self.giris_fiyat) * (1 + float(self.hedef_pct) / 100), 4)

    @property
    def mevcut_deger_tl(self):
        return round(float(self.giris_fiyat) * float(self.adet), 2)

    def __str__(self):
        return f"{self.acilis_tarihi:%Y-%m-%d} | {self.sembol} [{self.strateji}] | {self.durum}"

    class Meta:
        ordering = ['-acilis_tarihi']


class BudgetPlan(models.Model):
    """Kullanıcının bütçesi — Athena bu bütçeyle piyasayı tarar ve yönetir."""
    RISK_CHOICES = [
        ('dusuk',   'Düşük Risk'),
        ('orta',    'Orta Risk'),
        ('yuksek',  'Yüksek Risk'),
    ]

    toplam_butce     = models.DecimalField(max_digits=14, decimal_places=2)
    risk_profili     = models.CharField(max_length=10, choices=RISK_CHOICES, default='orta')
    max_hisse_sayisi = models.IntegerField(default=3)
    is_active        = models.BooleanField(default=True)
    aciklama         = models.TextField(blank=True)
    athena_analiz    = models.TextField(blank=True)
    son_tarama       = models.DateTimeField(null=True, blank=True)
    olusturuldu      = models.DateTimeField(auto_now_add=True)
    guncellendi      = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bütçe: {self.toplam_butce} TL | Risk: {self.risk_profili} | Aktif: {self.is_active}"

    class Meta:
        ordering = ['-olusturuldu']
        verbose_name = "Bütçe Planı"
        verbose_name_plural = "Bütçe Planları"


class BudgetPosition(models.Model):
    """BudgetPlan'a bağlı açık pozisyonlar — Athena takip eder."""
    DURUM_CHOICES = [
        ('bekliyor',  'Athena önerdi, henüz alınmadı'),
        ('acik',      'Alındı — Açık Pozisyon'),
        ('hedef',     'Hedef Fiyata Ulaştı'),
        ('stop',      'Stop-Loss Tetiklendi'),
        ('kapali',    'Kapatıldı'),
    ]

    plan           = models.ForeignKey(BudgetPlan, on_delete=models.CASCADE,
                                       related_name='pozisyonlar')
    sembol         = models.CharField(max_length=20)
    adet           = models.DecimalField(max_digits=12, decimal_places=2)
    giris_fiyat    = models.DecimalField(max_digits=12, decimal_places=4)
    stop_fiyat     = models.DecimalField(max_digits=12, decimal_places=4)
    hedef_fiyat    = models.DecimalField(max_digits=12, decimal_places=4)
    giris_skoru    = models.IntegerField(default=0)
    durum          = models.CharField(max_length=15, choices=DURUM_CHOICES, default='bekliyor')
    acilis_tarihi  = models.DateTimeField(auto_now_add=True)
    kapanis_tarihi = models.DateTimeField(null=True, blank=True)
    cikis_fiyat    = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    kaz_kayip_tl   = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    kaz_kayip_pct  = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    athena_not     = models.TextField(blank=True)

    def __str__(self):
        return f"{self.sembol} | {self.durum} | {self.giris_fiyat} TL"

    @property
    def maliyet_tl(self):
        return round(float(self.adet) * float(self.giris_fiyat), 2)

    class Meta:
        ordering = ['-acilis_tarihi']
        verbose_name = "Bütçe Pozisyonu"
        verbose_name_plural = "Bütçe Pozisyonları"