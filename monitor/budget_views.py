"""
Athena Bütçe Yönetimi
======================
Kullanıcı bütçesini girer → Athena tüm piyasayı tarar → En iyi hisseleri seçer
→ Kullanıcı "aldım" der → Athena fiyat takibi yapar → SAT sinyali verir
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from django.conf import settings
from groq import Groq

from stocks.services import (
    get_stock_data, get_technical_indicators, get_fundamental_data,
    ALL_BIST_STOCKS,
)
from monitor.scanner import compute_score, _get_signal_label
from monitor.models import BudgetPlan, BudgetPosition

GROQ_MODEL = "llama-3.3-70b-versatile"

RISK_PARAMS = {
    'dusuk': {'stop': 4, 'hedef': 8},
    'orta': {'stop': 7, 'hedef': 15},
    'yuksek': {'stop': 10, 'hedef': 25},
}


def _groq_client():
    return Groq(api_key=settings.GROQ_API_KEY)


# ─── 1. Bütçe Oluştur ────────────────────────────────────────────────────────

@api_view(['POST'])
def butce_olustur(request):
    """
    POST /api/monitor/butce/olustur/
    Body: { "toplam_butce": 1000, "risk_profili": "orta", "max_hisse_sayisi": 3 }

    Athena tüm BIST'i tarar → En iyi N hisseyi seçer → Groq ile analiz yapar
    → BudgetPlan + BudgetPosition(bekliyor) kaydeder → Kullanıcıya rapor verir
    """
    toplam_butce = float(request.data.get('toplam_butce', 0))
    risk_profili = request.data.get('risk_profili', 'orta')
    max_hisse_sayisi = int(request.data.get('max_hisse_sayisi', 3))

    if toplam_butce <= 0:
        return Response({'error': 'toplam_butce sıfırdan büyük olmalı'}, status=400)
    if risk_profili not in RISK_PARAMS:
        return Response({'error': 'risk_profili: dusuk | orta | yuksek'}, status=400)

    # Var olan aktif planı devre dışı bırak
    BudgetPlan.objects.filter(is_active=True).update(is_active=False)

    rp = RISK_PARAMS[risk_profili]
    butce_per_hisse = toplam_butce / max_hisse_sayisi

    # ── Piyasa Taraması ───────────────────────────────────────────────────────
    adaylar = []
    hatalar = []

    taranacak = ALL_BIST_STOCKS[:80]  # En likit 80 hisse (hız için)

    for sembol in taranacak:
        try:
            stock = get_stock_data(sembol)
            if not stock or stock.get('price', 0) <= 0:
                continue

            fiyat = stock['price']
            if fiyat <= 0:
                continue

            # Bütçe yeterliliği: en az 1 lot alabilmeli
            if butce_per_hisse < fiyat:
                continue

            tech = get_technical_indicators(sembol)
            if not tech.get('rsi'):
                continue

            fund = None
            try:
                fund = get_fundamental_data(sembol)
            except Exception:
                pass

            puan, gerekceler = compute_score(tech, stock, fund)

            if puan >= 4:  # Sadece gerçekten güçlü sinyaller
                adet = int(butce_per_hisse / fiyat)
                if adet < 1:
                    continue

                adaylar.append({
                    'sembol': sembol,
                    'puan': puan,
                    'fiyat': fiyat,
                    'adet': adet,
                    'maliyet': round(adet * fiyat, 2),
                    'stop_f': round(fiyat * (1 - rp['stop'] / 100), 4),
                    'hedef_f': round(fiyat * (1 + rp['hedef'] / 100), 4),
                    'stop_pct': rp['stop'],
                    'hedef_pct': rp['hedef'],
                    'rsi': tech.get('rsi'),
                    'trend': tech.get('trend'),
                    'macd_hist': tech.get('macd_histogram'),
                    'bb_pos': tech.get('bb_position', ''),
                    'gerekceler': gerekceler,
                    'sinyal': _get_signal_label(puan),
                    'degisim': stock.get('change_percent', 0),
                })
        except Exception as e:
            hatalar.append(f"{sembol}: {str(e)[:60]}")
            continue

    if not adaylar:
        return Response({
            'error': (
                'Yeterli sinyal bulunamadı. Piyasa şu an nötr veya düşüş eğiliminde. '
                'Daha düşük puan eşiğiyle tekrar tarama yapılabilir.'
            ),
            'taranan': len(taranacak),
        }, status=200)

    # En iyi N hisseyi seç
    adaylar.sort(key=lambda x: x['puan'], reverse=True)
    secilen = adaylar[:max_hisse_sayisi]

    # ── Groq ile Detaylı Analiz ───────────────────────────────────────────────
    hisse_ozeti = "\n".join([
        f"• {a['sembol']} — Fiyat: {a['fiyat']} TL | Adet: {a['adet']} | "
        f"Maliyet: {a['maliyet']} TL | Skor: +{a['puan']} | RSI: {a['rsi']} | "
        f"Trend: {a['trend']} | Stop: {a['stop_f']} TL | Hedef: {a['hedef_f']} TL\n"
        f"  Gerekçe: {' | '.join(a['gerekceler'][:3])}"
        for a in secilen
    ])

    prompt = f"""Kullanıcının {toplam_butce} TL bütçesi var. Risk profili: {risk_profili}.
Her hisseye yaklaşık {butce_per_hisse:.0f} TL ayrılacak.

Athena'nın teknik tarama sonucu seçilen hisseler:
{hisse_ozeti}

Lütfen şunları yap:
1. Her hisse için neden seçildiğini 2-3 cümleyle açıkla (RSI, MACD, trend verilerini kullan).
2. Kullanıcıya "ne zaman almalı" konusunda somut öneri ver (şimdi mi, düzeltme beklenmeli mi?).
3. Her hisse için risk uyarısı ver.
4. Genel portföy değerlendirmesi yap (çeşitlendirme, toplam risk).
5. Stop-loss ve hedef fiyatlara dikkat çek.

Türkçe yaz. Net, sade, anlaşılır ol. Jargon kullanma, borsa bilgisi olmayan birine anlatır gibi anlat."""

    athena_analiz = ""
    try:
        client = _groq_client()
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": (
                    "Sen Athena'sın — BIST uzmanı kişisel yapay zeka yatırım asistanısın. "
                    "Türkçe, net ve anlaşılır konuşursun. Borsa bilgisi olmayan kullanıcılara "
                    "rehberlik edersin. Her analizin sonunda 'Bu analiz kişisel kullanım içindir, "
                    "resmi yatırım tavsiyesi değildir.' notunu eklersin."
                )},
                {"role": "user", "content": prompt}
            ],
            temperature=0.25,
            max_tokens=2000,
        )
        athena_analiz = resp.choices[0].message.content
    except Exception as e:
        athena_analiz = f"Groq analizi alınamadı: {str(e)}"

    # ── Veritabanına Kaydet ───────────────────────────────────────────────────
    plan = BudgetPlan.objects.create(
        toplam_butce=toplam_butce,
        risk_profili=risk_profili,
        max_hisse_sayisi=max_hisse_sayisi,
        athena_analiz=athena_analiz,
        son_tarama=timezone.now(),
        is_active=True,
    )

    pozisyonlar_data = []
    for a in secilen:
        pos = BudgetPosition.objects.create(
            plan=plan,
            sembol=a['sembol'],
            adet=a['adet'],
            giris_fiyat=a['fiyat'],
            stop_fiyat=a['stop_f'],
            hedef_fiyat=a['hedef_f'],
            giris_skoru=a['puan'],
            durum='bekliyor',
            athena_not=' | '.join(a['gerekceler'][:3]),
        )
        pozisyonlar_data.append({
            'id': pos.id,
            'sembol': a['sembol'],
            'adet': a['adet'],
            'giris_fiyat': a['fiyat'],
            'maliyet_tl': a['maliyet'],
            'stop_fiyat': a['stop_f'],
            'hedef_fiyat': a['hedef_f'],
            'stop_pct': a['stop_pct'],
            'hedef_pct': a['hedef_pct'],
            'skor': a['puan'],
            'sinyal': a['sinyal'],
            'rsi': a['rsi'],
            'trend': a['trend'],
            'gerekceler': a['gerekceler'][:5],
            'durum': 'bekliyor',
        })

    toplam_maliyet = sum(p['maliyet_tl'] for p in pozisyonlar_data)

    return Response({
        'plan_id': plan.id,
        'toplam_butce': toplam_butce,
        'kullanilan_butce': round(toplam_maliyet, 2),
        'kalan_nakit': round(toplam_butce - toplam_maliyet, 2),
        'risk_profili': risk_profili,
        'taranan_hisse': len(taranacak),
        'bulunan_aday': len(adaylar),
        'secilen_hisse': len(secilen),
        'pozisyonlar': pozisyonlar_data,
        'athena_analiz': athena_analiz,
        'mesaj': (
            f"Athena {len(taranacak)} hisse taradı, {len(adaylar)} aday buldu, "
            f"en iyi {len(secilen)} tanesini seçti. "
            f"'Aldım' onayı için /api/monitor/butce/pozisyon/<id>/alindi/ endpoint'ini kullan."
        ),
    })


# ─── 2. "Aldım" Onayı ────────────────────────────────────────────────────────

@api_view(['POST'])
def pozisyon_alindi(request, pozisyon_id):
    """
    POST /api/monitor/butce/pozisyon/<id>/alindi/
    Body: { "gercek_fiyat": 45.20 }  (opsiyonel — gerçek alış fiyatı)

    Kullanıcı hisseyi aldığında bu endpoint çağrılır.
    Pozisyon durumu 'bekliyor' → 'acik' olur.
    """
    try:
        pos = BudgetPosition.objects.get(id=pozisyon_id)
    except BudgetPosition.DoesNotExist:
        return Response({'error': 'Pozisyon bulunamadı'}, status=404)

    if pos.durum != 'bekliyor':
        return Response({'error': f'Pozisyon zaten {pos.durum} durumunda'}, status=400)

    gercek_fiyat = request.data.get('gercek_fiyat')
    if gercek_fiyat:
        gercek_fiyat = float(gercek_fiyat)
        pos.giris_fiyat = gercek_fiyat
        # Stop ve hedefi güncelle
        rp = RISK_PARAMS.get(pos.plan.risk_profili, RISK_PARAMS['orta'])
        pos.stop_fiyat = round(gercek_fiyat * (1 - rp['stop'] / 100), 4)
        pos.hedef_fiyat = round(gercek_fiyat * (1 + rp['hedef'] / 100), 4)

    pos.durum = 'acik'
    pos.save()

    return Response({
        'status': 'Pozisyon açık olarak işaretlendi',
        'sembol': pos.sembol,
        'adet': float(pos.adet),
        'giris_fiyat': float(pos.giris_fiyat),
        'stop_fiyat': float(pos.stop_fiyat),
        'hedef_fiyat': float(pos.hedef_fiyat),
        'maliyet_tl': pos.maliyet_tl,
        'mesaj': (
            f"{pos.sembol} portföyüne eklendi. "
            f"Stop: {float(pos.stop_fiyat)} TL | Hedef: {float(pos.hedef_fiyat)} TL. "
            f"Athena düzenli takip edecek ve uyarı gönderecek."
        ),
    })


# ─── 3. Aktif Bütçe Takibi ───────────────────────────────────────────────────

@api_view(['GET'])
def butce_durum(request):
    """
    GET /api/monitor/butce/durum/
    Aktif bütçe planı + tüm pozisyonların anlık durumu + Athena SAT/TUT sinyali
    """
    plan = BudgetPlan.objects.filter(is_active=True).first()
    if not plan:
        return Response({
            'error': 'Aktif bütçe planı yok. /api/monitor/butce/olustur/ ile başla.',
        }, status=404)

    pozisyonlar = plan.pozisyonlar.filter(durum__in=['bekliyor', 'acik'])
    sonuclar = []
    uyarilar = []
    toplam_maliyet = 0
    toplam_guncel = 0

    for pos in pozisyonlar:
        stock = get_stock_data(pos.sembol)
        if not stock:
            continue

        guncel_fiyat = stock['price']
        degisim_bugun = stock.get('change_percent', 0)

        maliyet = float(pos.adet) * float(pos.giris_fiyat)
        guncel_deger = float(pos.adet) * guncel_fiyat
        kaz_kayip_tl = guncel_deger - maliyet
        kaz_kayip_pct = (kaz_kayip_tl / maliyet * 100) if maliyet > 0 else 0

        if pos.durum == 'acik':
            toplam_maliyet += maliyet
            toplam_guncel += guncel_deger

        # Sinyal hesapla
        tech = get_technical_indicators(pos.sembol)
        puan, gerekceler = compute_score(tech, stock)
        sinyal_label = _get_signal_label(puan)

        # Otomatik stop/hedef kontrolü
        acil_uyari = None
        tavsiye = 'TUT'
        rp = RISK_PARAMS.get(pos.plan.risk_profili, RISK_PARAMS['orta'])

        if pos.durum == 'acik':
            if guncel_fiyat <= float(pos.stop_fiyat):
                acil_uyari = f"🔴 STOP-LOSS! Fiyat ({guncel_fiyat}) stop seviyesinin ({float(pos.stop_fiyat)}) altına indi. HEMEN SAT!"
                tavsiye = 'SAT'
                uyarilar.append(acil_uyari)
            elif guncel_fiyat >= float(pos.hedef_fiyat):
                acil_uyari = f"🎯 HEDEF TUTTU! Fiyat ({guncel_fiyat}) hedefe ({float(pos.hedef_fiyat)}) ulaştı. Sat veya kısmi sat düşün!"
                tavsiye = 'SAT'
                uyarilar.append(acil_uyari)
            elif puan <= -4:
                acil_uyari = f"⚠️ GÜÇLÜ SAT sinyali (skor {puan}). Stop gelmeden satmayı düşün."
                tavsiye = 'SAT'
                uyarilar.append(acil_uyari)
            elif puan >= 3:
                tavsiye = 'TUT_AL'  # güçlü, tutmaya devam
            elif kaz_kayip_pct <= -(rp['stop'] * 0.8):
                tavsiye = 'DİKKAT'

        sonuclar.append({
            'id': pos.id,
            'sembol': pos.sembol,
            'durum': pos.durum,
            'adet': float(pos.adet),
            'giris_fiyat': float(pos.giris_fiyat),
            'guncel_fiyat': guncel_fiyat,
            'stop_fiyat': float(pos.stop_fiyat),
            'hedef_fiyat': float(pos.hedef_fiyat),
            'maliyet_tl': round(maliyet, 2),
            'guncel_deger': round(guncel_deger, 2),
            'kaz_kayip_tl': round(kaz_kayip_tl, 2),
            'kaz_kayip_pct': round(kaz_kayip_pct, 2),
            'degisim_bugun': degisim_bugun,
            'rsi': tech.get('rsi'),
            'trend': tech.get('trend'),
            'tavsiye': tavsiye,
            'athena_sinyal': sinyal_label,
            'sinyal_skoru': puan,
            'gerekceler': gerekceler[:3],
            'acil_uyari': acil_uyari,
        })

    toplam_kaz_kayip = toplam_guncel - toplam_maliyet
    toplam_kaz_kayip_pct = (toplam_kaz_kayip / toplam_maliyet * 100) if toplam_maliyet > 0 else 0

    return Response({
        'plan_id': plan.id,
        'toplam_butce': float(plan.toplam_butce),
        'risk_profili': plan.risk_profili,
        'toplam_maliyet': round(toplam_maliyet, 2),
        'toplam_guncel': round(toplam_guncel, 2),
        'toplam_kaz_kayip': round(toplam_kaz_kayip, 2),
        'toplam_kaz_kayip_pct': round(toplam_kaz_kayip_pct, 2),
        'acik_pozisyon_sayisi': len([p for p in sonuclar if p['durum'] == 'acik']),
        'bekleyen_sayisi': len([p for p in sonuclar if p['durum'] == 'bekliyor']),
        'acil_uyarilar': uyarilar,
        'pozisyonlar': sonuclar,
        'son_tarama': plan.son_tarama,
        'athena_analiz': plan.athena_analiz,
    })


# ─── 4. Pozisyon Kapat ───────────────────────────────────────────────────────

@api_view(['POST'])
def pozisyon_kapat(request, pozisyon_id):
    """
    POST /api/monitor/butce/pozisyon/<id>/kapat/
    Body: { "cikis_fiyat": 50.50, "neden": "hedef" | "stop" | "manuel" }

    Pozisyonu kapatır, kar/zarar kaydeder.
    """
    try:
        pos = BudgetPosition.objects.get(id=pozisyon_id)
    except BudgetPosition.DoesNotExist:
        return Response({'error': 'Pozisyon bulunamadı'}, status=404)

    cikis_fiyat = float(request.data.get('cikis_fiyat', 0))
    neden = request.data.get('neden', 'manuel')

    if cikis_fiyat <= 0:
        # Anlık fiyatı al
        stock = get_stock_data(pos.sembol)
        cikis_fiyat = stock['price'] if stock else float(pos.giris_fiyat)

    maliyet = float(pos.adet) * float(pos.giris_fiyat)
    gelir = float(pos.adet) * cikis_fiyat
    kaz_kayip_tl = gelir - maliyet
    kaz_kayip_pct = (kaz_kayip_tl / maliyet * 100) if maliyet > 0 else 0

    durum_map = {'hedef': 'hedef', 'stop': 'stop', 'manuel': 'kapali'}
    pos.durum = durum_map.get(neden, 'kapali')
    pos.cikis_fiyat = cikis_fiyat
    pos.kapanis_tarihi = timezone.now()
    pos.kaz_kayip_tl = round(kaz_kayip_tl, 2)
    pos.kaz_kayip_pct = round(kaz_kayip_pct, 2)
    pos.save()

    emoji = '✅' if kaz_kayip_tl >= 0 else '❌'

    return Response({
        'status': 'Pozisyon kapatıldı',
        'sembol': pos.sembol,
        'giris_fiyat': float(pos.giris_fiyat),
        'cikis_fiyat': cikis_fiyat,
        'adet': float(pos.adet),
        'maliyet_tl': round(maliyet, 2),
        'gelir_tl': round(gelir, 2),
        'kaz_kayip_tl': round(kaz_kayip_tl, 2),
        'kaz_kayip_pct': round(kaz_kayip_pct, 2),
        'durum': pos.durum,
        'mesaj': f"{emoji} {pos.sembol} kapatıldı: {kaz_kayip_tl:+.2f} TL ({kaz_kayip_pct:+.2f}%)",
    })


# ─── 5. Yeni Fırsat Tara ─────────────────────────────────────────────────────

@api_view(['POST'])
def yeni_firsat_tara(request):
    """
    POST /api/monitor/butce/yeni-firsat/
    Body: { "kalan_butce": 300, "risk_profili": "orta" }

    Mevcut portföyde olmayan hisseleri tara, yeni fırsat bul.
    """
    kalan_butce = float(request.data.get('kalan_butce', 0))
    risk_profili = request.data.get('risk_profili', 'orta')

    if kalan_butce <= 0:
        return Response({'error': 'kalan_butce sıfırdan büyük olmalı'}, status=400)

    # Zaten portföyde olanları hariç tut
    mevcut_semboller = set(
        BudgetPosition.objects.filter(
            plan__is_active=True,
            durum__in=['bekliyor', 'acik']
        ).values_list('sembol', flat=True)
    )

    rp = RISK_PARAMS.get(risk_profili, RISK_PARAMS['orta'])
    adaylar = []

    for sembol in ALL_BIST_STOCKS[:80]:
        if sembol in mevcut_semboller:
            continue
        try:
            stock = get_stock_data(sembol)
            if not stock or stock.get('price', 0) <= 0:
                continue
            fiyat = stock['price']
            if fiyat > kalan_butce:
                continue

            tech = get_technical_indicators(sembol)
            if not tech.get('rsi'):
                continue

            puan, gerekceler = compute_score(tech, stock)

            if puan >= 4:
                adet = int(kalan_butce / fiyat)
                if adet < 1:
                    continue
                adaylar.append({
                    'sembol': sembol,
                    'puan': puan,
                    'fiyat': fiyat,
                    'adet': adet,
                    'maliyet': round(adet * fiyat, 2),
                    'stop_f': round(fiyat * (1 - rp['stop'] / 100), 4),
                    'hedef_f': round(fiyat * (1 + rp['hedef'] / 100), 4),
                    'rsi': tech.get('rsi'),
                    'trend': tech.get('trend'),
                    'gerekceler': gerekceler[:3],
                })
        except Exception:
            continue

    adaylar.sort(key=lambda x: x['puan'], reverse=True)
    en_iyi = adaylar[:3]

    return Response({
        'kalan_butce': kalan_butce,
        'bulunan': len(adaylar),
        'oneriler': en_iyi,
        'mesaj': (
            f"{len(adaylar)} yeni fırsat bulundu, en iyi 3 tanesi listelendi."
            if en_iyi else
            "Şu an için yeni güçlü sinyal bulunamadı. Nakit tutmak da bir stratejidir."
        ),
    })


# ─── 6. Tüm Geçmiş ───────────────────────────────────────────────────────────

@api_view(['GET'])
def butce_gecmis(request):
    """GET /api/monitor/butce/gecmis/ — Kapalı pozisyonların performansı"""
    kapali = BudgetPosition.objects.filter(
        durum__in=['hedef', 'stop', 'kapali']
    ).select_related('plan')[:50]

    data = []
    toplam_kaz = 0
    for pos in kapali:
        kaz = float(pos.kaz_kayip_tl or 0)
        toplam_kaz += kaz
        data.append({
            'sembol': pos.sembol,
            'giris_fiyat': float(pos.giris_fiyat),
            'cikis_fiyat': float(pos.cikis_fiyat or 0),
            'adet': float(pos.adet),
            'kaz_kayip_tl': kaz,
            'kaz_kayip_pct': float(pos.kaz_kayip_pct or 0),
            'durum': pos.durum,
            'acilis': pos.acilis_tarihi,
            'kapanis': pos.kapanis_tarihi,
        })

    kazanan = [d for d in data if d['kaz_kayip_tl'] > 0]
    kaybeden = [d for d in data if d['kaz_kayip_tl'] <= 0]

    return Response({
        'toplam_islem': len(data),
        'kazanan': len(kazanan),
        'kaybeden': len(kaybeden),
        'basari_orani': round(len(kazanan) / len(data) * 100, 1) if data else 0,
        'toplam_kaz_kayip_tl': round(toplam_kaz, 2),
        'pozisyonlar': data,
    })
