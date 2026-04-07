from django.urls import path
from . import views
from . import budget_views

urlpatterns = [
    # ── Mevcut Endpointler ────────────────────────────────────────────────
    path('scan/',                views.run_scan),              # POST — Manuel tarama
    path('scan/results/',        views.full_scan_results),     # GET  — Tüm skorlar
    path('alerts/',              views.alert_history),         # GET  — Uyarı geçmişi
    path('market/',              views.market_dashboard),      # GET  — Piyasa paneli
    path('commodities/',         views.commodity_overview),    # GET  — Emtia/Döviz
    path('invest/',              views.investment_advisor),    # POST — Yatırım danışmanı
    path('plans/',               views.active_plans),          # GET  — Aktif planlar
    path('plans/<str:symbol>/deactivate/', views.deactivate_plan),

    # ── YENİ: Bütçe Yönetimi ─────────────────────────────────────────────
    path('butce/olustur/',       budget_views.butce_olustur),          # POST — Bütçe gir, Athena tarar
    path('butce/durum/',         budget_views.butce_durum),            # GET  — Anlık takip
    path('butce/yeni-firsat/',   budget_views.yeni_firsat_tara),       # POST — Ek fırsat tara
    path('butce/gecmis/',        budget_views.butce_gecmis),           # GET  — Performans geçmişi
    path('butce/pozisyon/<int:pozisyon_id>/alindi/',  budget_views.pozisyon_alindi),  # POST — "Aldım"
    path('butce/pozisyon/<int:pozisyon_id>/kapat/',   budget_views.pozisyon_kapat),   # POST — Kapat
]