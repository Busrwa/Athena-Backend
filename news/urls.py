from django.urls import path
from . import views

urlpatterns = [
    path('', views.latest_news),
    path('cached/', views.cached_news),
    path('<str:symbol>/', views.news_for_symbol),
]
