from django.urls import path
from . import views
from . import budget_views
from . import paper_trading

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

    # ── Bütçe Yönetimi ────────────────────────────────────────────────────
    path('butce/olustur/',       budget_views.butce_olustur),
    path('butce/durum/',         budget_views.butce_durum),
    path('butce/yeni-firsat/',   budget_views.yeni_firsat_tara),
    path('butce/gecmis/',        budget_views.butce_gecmis),
    path('butce/pozisyon/<int:pozisyon_id>/alindi/',  budget_views.pozisyon_alindi),
    path('butce/pozisyon/<int:pozisyon_id>/kapat/',   budget_views.pozisyon_kapat),

    # ── Paper Trading (Sanal İşlem) ───────────────────────────────────────
    path('paper/ac/',                       paper_trading.pozisyon_ac),           # POST
    path('paper/pozisyonlar/',              paper_trading.pozisyonlar),            # GET
    path('paper/guncelle/<int:pozisyon_id>/', paper_trading.pozisyon_guncelle),   # POST
    path('paper/hepsi-guncelle/',           paper_trading.hepsini_guncelle),      # POST
    path('paper/istatistik/',               paper_trading.istatistik),            # GET
    path('paper/kapat/<int:pozisyon_id>/',  paper_trading.pozisyon_kapat_manuel), # POST
    path('paper/backtest/',                 paper_trading.backtest),               # POST
]