from django.urls import path
from . import views
from . import budget_views
from . import paper_trading
from . import push_views

urlpatterns = [
    # ── Mevcut Endpointler ────────────────────────────────────────────────
    path('scan/',                views.run_scan),
    path('scan/results/',        views.full_scan_results),
    path('alerts/',              views.alert_history),
    path('market/',              views.market_dashboard),
    path('commodities/',         views.commodity_overview),
    path('invest/',              views.investment_advisor),
    path('plans/',               views.active_plans),
    path('plans/<str:symbol>/deactivate/', views.deactivate_plan),

    # ── Bütçe Yönetimi ────────────────────────────────────────────────────
    path('butce/olustur/',       budget_views.butce_olustur),
    path('butce/durum/',         budget_views.butce_durum),
    path('butce/yeni-firsat/',   budget_views.yeni_firsat_tara),
    path('butce/gecmis/',        budget_views.butce_gecmis),
    path('butce/pozisyon/<int:pozisyon_id>/alindi/',  budget_views.pozisyon_alindi),
    path('butce/pozisyon/<int:pozisyon_id>/kapat/',   budget_views.pozisyon_kapat),
    path('butce/pozisyon/<int:pozisyon_id>/sil/',     budget_views.pozisyon_sil),

    # ── Paper Trading (Sanal İşlem) ───────────────────────────────────────
    path('paper/ac/',                       paper_trading.pozisyon_ac),
    path('paper/pozisyonlar/',              paper_trading.pozisyonlar),
    path('paper/guncelle/<int:pozisyon_id>/', paper_trading.pozisyon_guncelle),
    path('paper/hepsi-guncelle/',           paper_trading.hepsini_guncelle),
    path('paper/istatistik/',               paper_trading.istatistik),
    path('paper/kapat/<int:pozisyon_id>/',  paper_trading.pozisyon_kapat_manuel),
    path('paper/backtest/',                 paper_trading.backtest),

    # ── Push Notification ─────────────────────────────────────────────────
    path('push/register/',      push_views.push_register),
    path('push/test/',          push_views.push_test),
]