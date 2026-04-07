"""
Athena Otomatik Zamanlayıcı
- Piyasa saatlerinde (Pzt-Cuma 10:00-18:30) her 30 dakikada tarama yapar
- Her sabah 10:05'te günlük Top 3 öneri maili gönderir
- Taramada stop-loss/hedef kontrol eder, gerekirse SAT maili atar

Çalıştırmak için: python athena_scheduler.py
"""

import subprocess
import sys
import time
from datetime import datetime
import os

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MANAGE_PY  = os.path.join(BASE_DIR, "manage.py")
PYTHON     = sys.executable

TARAMA_ARALIGI_DAKIKA = 30  # Her 30 dakikada tarama

# ─── Günlük rapor ayarları — buradan değiştir ─────────────────────────────
BUTCE = 1000   # TL — her gün ne kadar yatırım yapabilirsin?
RISK  = "orta" # dusuk / orta / yuksek
# ──────────────────────────────────────────────────────────────────────────


def piyasa_acik_mi() -> bool:
    """BIST piyasa saatleri: Pzt-Cuma, 10:00-18:30 TSİ"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    saat = now.hour * 60 + now.minute
    return 10 * 60 <= saat <= 18 * 60 + 30


def tarama_yap():
    """Piyasa taraması + aktif plan stop/hedef kontrolü"""
    print(f"\n{'='*60}")
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ⚡ Athena tarama başlıyor...")
    print(f"{'='*60}")
    try:
        result = subprocess.run(
            [PYTHON, MANAGE_PY, "run_monitor"],
            capture_output=True, text=True, timeout=300, cwd=BASE_DIR
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr and "WARNING" not in result.stderr:
            print(f"[UYARI] {result.stderr[:300]}")
        print(f"[{datetime.now():%H:%M:%S}] Tarama tamamlandı.")
    except subprocess.TimeoutExpired:
        print("[HATA] Tarama 5 dakikada bitmedi.")
    except Exception as e:
        print(f"[HATA] {e}")


def gunluk_rapor_gonder():
    """Her sabah 10:05'te Top 3 öneri maili at"""
    print(f"\n{'='*60}")
    print(f"[{datetime.now():%H:%M:%S}] 📧 Günlük Top 3 rapor gönderiliyor...")
    print(f"  Bütçe: {BUTCE:,.0f} TL | Risk: {RISK}")
    print(f"{'='*60}")
    try:
        result = subprocess.run(
            [PYTHON, MANAGE_PY, "gunluk_rapor",
             "--butce", str(BUTCE), "--risk", RISK],
            capture_output=True, text=True, timeout=300, cwd=BASE_DIR
        )
        if result.stdout:
            print(result.stdout)
        print(f"[{datetime.now():%H:%M:%S}] Günlük rapor tamamlandı.")
    except Exception as e:
        print(f"[HATA] Günlük rapor: {e}")


def main():
    print("=" * 60)
    print("  ⚡ ATHENA OTOMATİK ZAMANLAYICI BAŞLADI")
    print(f"  Tarama aralığı : Her {TARAMA_ARALIGI_DAKIKA} dakika")
    print(f"  Piyasa saatleri: Pzt-Cuma 10:00 - 18:30")
    print(f"  Günlük rapor   : Her sabah 10:05")
    print(f"  Bütçe          : {BUTCE:,.0f} TL | Risk: {RISK}")
    print(f"  Başlangıç      : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 60)

    son_tarama = None
    gunluk_rapor_gonderildi = None  # Bugün rapor gönderildi mi?

    while True:
        simdi = datetime.now()
        bugun = simdi.date()

        # Günlük rapor: Her sabah 10:05-10:10 arası, sadece bir kez
        if (piyasa_acik_mi()
                and simdi.hour == 10 and 5 <= simdi.minute <= 10
                and simdi.weekday() < 5
                and gunluk_rapor_gonderildi != bugun):
            gunluk_rapor_gonder()
            gunluk_rapor_gonderildi = bugun

        # 30 dakikalık tarama
        if piyasa_acik_mi():
            if (son_tarama is None
                    or (simdi - son_tarama).total_seconds() >= TARAMA_ARALIGI_DAKIKA * 60):
                tarama_yap()
                son_tarama = datetime.now()
            else:
                kalan = TARAMA_ARALIGI_DAKIKA * 60 - (simdi - son_tarama).total_seconds()
                print(f"[{simdi:%H:%M:%S}] Piyasa açık — sonraki tarama "
                      f"{int(kalan//60)} dk {int(kalan%60)} sn sonra", end="\r")
        else:
            gun = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"][simdi.weekday()]
            print(f"[{simdi:%H:%M:%S}] Piyasa kapalı ({gun}) — bekleniyor...", end="\r")

        time.sleep(30)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[DURDURULDU] Athena zamanlayıcı kapatıldı.")
