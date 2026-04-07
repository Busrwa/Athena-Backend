from django.urls import path
from . import views

urlpatterns = [
    path('analyze/', views.analyze_portfolio),       # GET  — Tam portföy analizi
    path('ask/', views.ask_advisor),                 # POST — Serbest soru (hafızalı)
    path('signal/<str:symbol>/', views.quick_signal), # GET  — Hızlı sinyal (AI'sız)
    path('market/', views.market_overview),           # GET  — BIST genel görünüm
]
