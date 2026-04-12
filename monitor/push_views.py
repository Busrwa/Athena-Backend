"""
Push Notification Endpoint'leri
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .push_service import register_token, send_push, get_tokens


@api_view(['POST'])
def push_register(request):
    """
    POST /api/monitor/push/register/
    Body: { "token": "ExponentPushToken[...]" }
    Telefon push token'ını kaydeder.
    """
    token = request.data.get('token', '')
    if not token:
        return Response({'error': 'token gerekli'}, status=400)

    success = register_token(token)
    if success:
        return Response({'status': 'Token kaydedildi', 'token': token[:30] + '...'})
    else:
        return Response({'error': 'Geçersiz token formatı'}, status=400)


@api_view(['POST'])
def push_test(request):
    """
    POST /api/monitor/push/test/
    Test bildirimi gönder.
    """
    tokens = get_tokens()
    if not tokens:
        return Response({'error': 'Kayıtlı token yok. Önce uygulamayı aç.'}, status=400)

    send_push(
        title='🦉 Athena Test Bildirimi',
        body='Push notification çalışıyor! Stop/hedef uyarıları aktif.',
        data={'type': 'test'},
    )
    return Response({'status': 'Test bildirimi gönderildi', 'token_sayisi': len(tokens)})