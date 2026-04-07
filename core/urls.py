from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/stocks/', include('stocks.urls')),
    path('api/portfolio/', include('portfolio.urls')),
    path('api/news/', include('news.urls')),
    path('api/advisor/', include('ai_advisor.urls')),
    path('api/monitor/', include('monitor.urls')),   # YENİ
]