from django.contrib import admin
from .models import AlertLog, InvestmentPlan, PaperTrade, BudgetPlan, BudgetPosition


@admin.register(AlertLog)
class AlertLogAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'signal', 'score', 'price', 'email_sent', 'sent_at')
    list_filter  = ('signal', 'email_sent')
    search_fields = ('symbol',)


@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'budget_tl', 'is_active', 'created_at')
    list_filter  = ('is_active',)


@admin.register(PaperTrade)
class PaperTradeAdmin(admin.ModelAdmin):
    list_display = ('sembol', 'strateji', 'giris_fiyat', 'giris_skoru', 'durum', 'acilis_tarihi')
    list_filter  = ('strateji', 'durum')
    search_fields = ('sembol',)


class BudgetPositionInline(admin.TabularInline):
    model  = BudgetPosition
    extra  = 0
    fields = ('sembol', 'adet', 'giris_fiyat', 'stop_fiyat', 'hedef_fiyat', 'giris_skoru', 'durum')
    readonly_fields = ('acilis_tarihi',)


@admin.register(BudgetPlan)
class BudgetPlanAdmin(admin.ModelAdmin):
    list_display  = ('toplam_butce', 'risk_profili', 'max_hisse_sayisi', 'is_active', 'son_tarama', 'olusturuldu')
    list_filter   = ('is_active', 'risk_profili')
    inlines       = [BudgetPositionInline]
    readonly_fields = ('olusturuldu', 'guncellendi', 'son_tarama')


@admin.register(BudgetPosition)
class BudgetPositionAdmin(admin.ModelAdmin):
    list_display  = ('sembol', 'plan', 'adet', 'giris_fiyat', 'stop_fiyat',
                     'hedef_fiyat', 'durum', 'kaz_kayip_tl', 'acilis_tarihi')
    list_filter   = ('durum',)
    search_fields = ('sembol',)
    readonly_fields = ('acilis_tarihi', 'kapanis_tarihi')