from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def health(request):
    return JsonResponse({'status': 'ok'})

urlpatterns = [
    path('', health),
    path('health/', health),
    path('admin/', admin.site.urls),
    path('api/stocks/', include('stocks.urls')),
    path('api/portfolio/', include('portfolio.urls')),
    path('api/news/', include('news.urls')),
    path('api/advisor/', include('ai_advisor.urls')),
    path('api/monitor/', include('monitor.urls')),
]