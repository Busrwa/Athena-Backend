"""
Athena Push Notification Servisi
==================================
Expo Push API kullanarak telefona bildirim gönderir.
Stop-loss, hedef, momentum bozulması durumlarında çalışır.
"""
import requests
from django.conf import settings

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'

# Bellekte token sakla (basit çözüm, DB'ye de eklenebilir)
_push_tokens = set()


def register_token(token: str):
    """Push token'ı kaydet"""
    if token and token.startswith('ExponentPushToken['):
        _push_tokens.add(token)
        print(f"[PUSH] Token kaydedildi: {token[:30]}...")
        return True
    return False


def get_tokens():
    return list(_push_tokens)


def send_push(title: str, body: str, data: dict = None, tokens: list = None):
    """
    Expo Push API ile bildirim gönder.
    tokens belirtilmezse tüm kayıtlı token'lara gönderir.
    """
    hedef_tokenlar = tokens or get_tokens()
    if not hedef_tokenlar:
        print("[PUSH] Kayıtlı token yok, bildirim gönderilemedi")
        return False

    mesajlar = []
    for token in hedef_tokenlar:
        mesajlar.append({
            'to': token,
            'title': title,
            'body': body,
            'data': data or {},
            'sound': 'default',
            'priority': 'high',
            'channelId': 'athena-alerts',
        })

    try:
        resp = requests.post(
            EXPO_PUSH_URL,
            json=mesajlar,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            timeout=10,
        )
        result = resp.json()
        print(f"[PUSH] Gönderildi: {len(mesajlar)} bildirim → {result}")
        return True
    except Exception as e:
        print(f"[PUSH] Hata: {e}")
        return False


# ─── Hazır Bildirim Şablonları ───────────────────────────────────────────────

def push_stop_loss(sembol: str, fiyat: float, zarar_pct: float):
    send_push(
        title=f"🔴 STOP-LOSS — {sembol}",
        body=f"Fiyat {fiyat:.2f} TL'ye düştü. Zarar: %{zarar_pct:.1f}. HEMEN SAT!",
        data={'type': 'stop_loss', 'sembol': sembol},
    )


def push_hedef(sembol: str, fiyat: float, kar_pct: float):
    send_push(
        title=f"🎯 HEDEF TUTTU — {sembol}",
        body=f"Fiyat {fiyat:.2f} TL'ye ulaştı. Kâr: %{kar_pct:.1f}. Sat veya tut?",
        data={'type': 'hedef', 'sembol': sembol},
    )


def push_momentum(sembol: str, mesaj: str):
    send_push(
        title=f"⚡ MOMENTUM BOZULUYOR — {sembol}",
        body=mesaj,
        data={'type': 'momentum', 'sembol': sembol},
    )


def push_guclu_sat(sembol: str, skor: int):
    send_push(
        title=f"⚠️ GÜÇLÜ SAT SİNYALİ — {sembol}",
        body=f"Teknik analiz skoru: {skor}. Stop gelmeden satmayı düşün.",
        data={'type': 'guclu_sat', 'sembol': sembol},
    )