from rest_framework.decorators import api_view
from rest_framework.response import Response
from .services import (
    get_stock_data, get_technical_indicators,
    update_stock_in_db, search_bist_stocks, POPULAR_BIST_STOCKS
)
from .models import Stock


@api_view(['GET'])
def stock_price(request, symbol):
    """Tek hisse fiyati: GET /api/stocks/MOGAN/"""
    symbol = symbol.upper()
    data = get_stock_data(symbol)
    if data:
        return Response(data)
    return Response({'error': f'{symbol} bulunamadi veya BIST\'te islem gormuyor'}, status=404)


@api_view(['GET'])
def stock_technical(request, symbol):
    """
    Detayli teknik analiz: GET /api/stocks/MOGAN/technical/
    RSI, MACD, Bollinger, EMA, Support/Resistance
    """
    symbol = symbol.upper()
    data = get_technical_indicators(symbol)
    return Response(data)


@api_view(['GET'])
def popular_stocks(request):
    """
    Populer BIST hisseleri: GET /api/stocks/popular/
    Fiyat + gunluk degisim
    """
    results = []
    for symbol in POPULAR_BIST_STOCKS:
        data = get_stock_data(symbol)
        if data:
            results.append(data)
    return Response({
        'count': len(results),
        'stocks': results
    })


@api_view(['GET'])
def search_stocks(request):
    """
    Hisse arama: GET /api/stocks/search/?q=MOG
    Portfoye eklemeden once sembol bulmak icin
    """
    query = request.query_params.get('q', '').strip()
    if len(query) < 2:
        return Response({'error': 'En az 2 karakter girin'}, status=400)

    results = search_bist_stocks(query)
    return Response({
        'query': query.upper(),
        'count': len(results),
        'results': results
    })


@api_view(['GET'])
def refresh_stock(request, symbol):
    """DB\'ye kaydet: GET /api/stocks/MOGAN/refresh/"""
    symbol = symbol.upper()
    data = update_stock_in_db(symbol)
    if data:
        return Response({'status': 'guncellendi', 'data': data})
    return Response({'error': 'Guncellenemedi'}, status=400)
