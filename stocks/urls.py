from django.urls import path
from . import views

urlpatterns = [
    path('popular/', views.popular_stocks),       # /api/stocks/popular/
    path('search/', views.search_stocks),         # /api/stocks/search/?q=MOG
    path('<str:symbol>/', views.stock_price),     # /api/stocks/MOGAN/
    path('<str:symbol>/technical/', views.stock_technical),  # /api/stocks/MOGAN/technical/
    path('<str:symbol>/refresh/', views.refresh_stock),      # /api/stocks/MOGAN/refresh/
]
