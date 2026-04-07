from django.urls import path
from . import views

urlpatterns = [
    # ── Watchlist (önce tanımlanmalı!) ──────────────────────────
    path('watchlist/', views.watchlist),                      # GET
    path('watchlist/add/', views.watchlist_add),              # POST
    path('watchlist/<str:symbol>/', views.watchlist_remove),  # DELETE

    # ── Portföy işlemleri ────────────────────────────────────────
    path('', views.portfolio_summary),                        # GET
    path('add/', views.add_holding),                          # POST
    path('sell/', views.sell_holding),                        # POST
    path('transactions/', views.transaction_history),         # GET

    # ── Bu EN SONA olmalı — diğer path'leri yutar ───────────────
    path('<str:symbol>/', views.remove_holding),              # DELETE
]