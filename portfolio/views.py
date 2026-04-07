from rest_framework.decorators import api_view
from rest_framework.response import Response
from decimal import Decimal
from .models import Portfolio, Transaction, Watchlist
from stocks.services import get_stock_data


# ─────────────────────────────────────────────────────────────────────────────
# PORTFÖY
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def portfolio_summary(request):
    """Tum portfoy ozeti - GET /api/portfolio/"""
    holdings = Portfolio.objects.all()
    total_cost = Decimal('0')
    total_value = Decimal('0')
    result = []

    for holding in holdings:
        stock_data = get_stock_data(holding.symbol)
        current_price = Decimal(str(stock_data['price'])) if stock_data else holding.avg_cost
        change_pct = stock_data['change_percent'] if stock_data else 0

        cost = holding.quantity * holding.avg_cost
        value = holding.quantity * current_price
        profit_loss = value - cost
        profit_loss_percent = (profit_loss / cost * 100) if cost > 0 else Decimal('0')

        total_cost += cost
        total_value += value

        result.append({
            'symbol': holding.symbol,
            'quantity': float(holding.quantity),
            'avg_cost': float(holding.avg_cost),
            'current_price': float(current_price),
            'cost': round(float(cost), 2),
            'value': round(float(value), 2),
            'profit_loss': round(float(profit_loss), 2),
            'profit_loss_percent': round(float(profit_loss_percent), 2),
            'change_percent_today': change_pct,
        })

    total_pl = total_value - total_cost
    total_pl_pct = (total_pl / total_cost * 100) if total_cost > 0 else Decimal('0')

    return Response({
        'holdings': result,
        'summary': {
            'total_cost': round(float(total_cost), 2),
            'total_value': round(float(total_value), 2),
            'total_profit_loss': round(float(total_pl), 2),
            'total_profit_loss_percent': round(float(total_pl_pct), 2),
            'holding_count': len(result),
        }
    })


@api_view(['POST'])
def add_holding(request):
    """
    Hisse al - POST /api/portfolio/add/
    Body: { symbol, quantity, avg_cost }
    Ayni sembol varsa ortalama maliyet hesaplanir.
    """
    symbol = request.data.get('symbol', '').upper().strip()
    quantity = request.data.get('quantity')
    avg_cost = request.data.get('avg_cost')

    if not all([symbol, quantity, avg_cost]):
        return Response({'error': 'symbol, quantity, avg_cost zorunlu'}, status=400)

    try:
        quantity = Decimal(str(quantity))
        avg_cost = Decimal(str(avg_cost))
        if quantity <= 0 or avg_cost <= 0:
            raise ValueError
    except Exception:
        return Response({'error': 'quantity ve avg_cost pozitif sayi olmali'}, status=400)

    holding, created = Portfolio.objects.get_or_create(
        symbol=symbol,
        defaults={'quantity': quantity, 'avg_cost': avg_cost}
    )

    if not created:
        # Agirlikli ortalama maliyet
        old_total = holding.quantity * holding.avg_cost
        new_total = quantity * avg_cost
        new_quantity = holding.quantity + quantity
        holding.avg_cost = (old_total + new_total) / new_quantity
        holding.quantity = new_quantity
        holding.save()

    Transaction.objects.create(
        symbol=symbol,
        transaction_type=Transaction.BUY,
        quantity=quantity,
        price=avg_cost,
    )

    # Watchlist'ten cikar (artik portfoyumuzde)
    Watchlist.objects.filter(symbol=symbol).delete()

    return Response({
        'status': 'eklendi' if created else 'guncellendi',
        'symbol': symbol,
        'quantity': float(holding.quantity),
        'avg_cost': float(holding.avg_cost),
        'message': f'{symbol} portfoyune {"eklendi" if created else "uzerine eklendi"}'
    })


@api_view(['POST'])
def sell_holding(request):
    """
    Hisse sat - POST /api/portfolio/sell/
    Body: { symbol, quantity, sell_price }
    Kar/zarari hesaplayip Transaction'a kaydeder.
    """
    symbol = request.data.get('symbol', '').upper().strip()
    quantity = request.data.get('quantity')
    sell_price = request.data.get('sell_price')

    if not all([symbol, quantity, sell_price]):
        return Response({'error': 'symbol, quantity, sell_price zorunlu'}, status=400)

    try:
        quantity = Decimal(str(quantity))
        sell_price = Decimal(str(sell_price))
        if quantity <= 0 or sell_price <= 0:
            raise ValueError
    except Exception:
        return Response({'error': 'quantity ve sell_price pozitif sayi olmali'}, status=400)

    try:
        holding = Portfolio.objects.get(symbol=symbol)
    except Portfolio.DoesNotExist:
        return Response({'error': f'{symbol} portfoyunde bulunamadi'}, status=404)

    if quantity > holding.quantity:
        return Response({
            'error': f'Yetersiz adet. Portfoyde {float(holding.quantity)} adet var.'
        }, status=400)

    cost_per_share = holding.avg_cost
    profit_loss = (sell_price - cost_per_share) * quantity
    profit_loss_percent = (
        (sell_price - cost_per_share) / cost_per_share * 100
    ) if cost_per_share > 0 else Decimal('0')

    Transaction.objects.create(
        symbol=symbol,
        transaction_type=Transaction.SELL,
        quantity=quantity,
        price=sell_price,
        notes=f'K/Z: {float(profit_loss):.2f} TL ({float(profit_loss_percent):.2f}%)',
    )

    remaining = holding.quantity - quantity
    if remaining <= 0:
        holding.delete()
        msg = f'{symbol} portfoyden tamamen cikarildi'
    else:
        holding.quantity = remaining
        holding.save()
        msg = f'{float(quantity)} adet satildi, {float(remaining)} adet kaldi'

    return Response({
        'status': 'satildi',
        'symbol': symbol,
        'quantity_sold': float(quantity),
        'sell_price': float(sell_price),
        'cost_per_share': float(cost_per_share),
        'profit_loss': round(float(profit_loss), 2),
        'profit_loss_percent': round(float(profit_loss_percent), 2),
        'message': msg,
    })


@api_view(['DELETE'])
def remove_holding(request, symbol):
    """Hisseyi sat kaydı olmadan sil - DELETE /api/portfolio/MOGAN/"""
    symbol = symbol.upper()
    try:
        holding = Portfolio.objects.get(symbol=symbol)
        holding.delete()
        return Response({'status': f'{symbol} portfoyden silindi'})
    except Portfolio.DoesNotExist:
        return Response({'error': 'Hisse bulunamadi'}, status=404)


@api_view(['GET'])
def transaction_history(request):
    """
    Islem gecmisi - GET /api/portfolio/transactions/
    ?symbol=MOGAN (opsiyonel filtre)
    """
    symbol = request.query_params.get('symbol', '').upper()
    qs = Transaction.objects.all()
    if symbol:
        qs = qs.filter(symbol=symbol)
    data = [{
        'symbol': t.symbol,
        'type': t.transaction_type,
        'type_display': 'Alış' if t.transaction_type == 'buy' else 'Satış',
        'quantity': float(t.quantity),
        'price': float(t.price),
        'total': round(float(t.quantity * t.price), 2),
        'notes': t.notes,
        'date': t.date,
    } for t in qs[:100]]
    return Response({'count': len(data), 'transactions': data})


# ─────────────────────────────────────────────────────────────────────────────
# WATCHLIST
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def watchlist(request):
    """Takip listesi - GET /api/portfolio/watchlist/"""
    items = Watchlist.objects.all()
    result = []
    for item in items:
        data = get_stock_data(item.symbol)
        result.append({
            'symbol': item.symbol,
            'note': item.note,
            'price': data['price'] if data else None,
            'change_percent': data['change_percent'] if data else None,
            'added_at': item.added_at,
        })
    return Response({'count': len(result), 'watchlist': result})


@api_view(['POST'])
def watchlist_add(request):
    """
    Takip listesine ekle - POST /api/portfolio/watchlist/add/
    Body: { symbol, note (opsiyonel) }
    """
    symbol = request.data.get('symbol', '').upper().strip()
    note = request.data.get('note', '').strip()

    if not symbol:
        return Response({'error': 'symbol zorunlu'}, status=400)

    # Zaten portfoyimde mi?
    if Portfolio.objects.filter(symbol=symbol).exists():
        return Response({'error': f'{symbol} zaten portfoyunuzde var'}, status=400)

    obj, created = Watchlist.objects.get_or_create(
        symbol=symbol,
        defaults={'note': note}
    )
    return Response({
        'status': 'eklendi' if created else 'zaten listede',
        'symbol': symbol,
    })


@api_view(['DELETE'])
def watchlist_remove(request, symbol):
    """Takip listesinden cikar - DELETE /api/portfolio/watchlist/MOGAN/"""
    symbol = symbol.upper()
    deleted, _ = Watchlist.objects.filter(symbol=symbol).delete()
    if deleted:
        return Response({'status': f'{symbol} takip listesinden cikarildi'})
    return Response({'error': 'Sembol bulunamadi'}, status=404)
