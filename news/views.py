import feedparser
import requests
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import NewsItem

# KAP RSS - guncel URL'ler (2024 itibariyle aktif olanlar)
KAP_FEEDS = [
    {
        'url': 'https://www.kap.org.tr/tr/rss/bildirim',
        'source': 'KAP'
    },
    {
        'url': 'https://www.kap.org.tr/tr/rss/onemli-aciklama',
        'source': 'KAP-ONEMLI'
    },
]

# Yedek finans haberleri
YEDEK_FEEDS = [
    {
        'url': 'https://feeds.bbci.co.uk/turkish/rss.xml',
        'source': 'BBC-TR'
    },
    {
        'url': 'https://www.bloomberght.com/rss',
        'source': 'BLOOMBERG-TR'
    },
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; AthenaBot/1.0)',
    'Accept': 'application/rss+xml, application/xml, text/xml',
}


def _parse_date(entry) -> datetime | None:
    for field in ('published', 'updated', 'created'):
        val = entry.get(field, '')
        if val:
            try:
                return parsedate_to_datetime(val)
            except Exception:
                try:
                    return datetime.fromisoformat(val.replace('Z', '+00:00'))
                except Exception:
                    continue
    return None


def _extract_symbol(text: str) -> str:
    """Baslik veya ozetten BIST hisse kodunu bul"""
    # Parantez icindeki kodlar (MOGAN), (THYAO) gibi
    match = re.search(r'\(([A-Z]{2,6})\)', text)
    if match:
        return match.group(1)
    # Baslangicta buyuk harf kelime
    match = re.search(r'^([A-Z]{3,6})\b', text)
    if match:
        return match.group(1)
    # Herhangibir yerde
    match = re.search(r'\b([A-Z]{3,6})\b', text)
    return match.group(1) if match else ''


def fetch_kap_news(symbol: str = None, limit: int = 20) -> list:
    """
    KAP RSS'den haberleri ceker.
    Once KAP feed'lerini dener, basarisiz olursa DB'deki eski kayitlari doner.
    """
    items = []
    feed_errors = []

    all_feeds = KAP_FEEDS + YEDEK_FEEDS

    for feed_info in all_feeds:
        feed_url = feed_info['url']
        source = feed_info['source']
        try:
            # feedparser dogrudan istekte basarisiz olabilir, requests ile dene
            resp = requests.get(feed_url, headers=HEADERS, timeout=8)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)

            if not feed.entries:
                feed = feedparser.parse(feed_url)

            for entry in feed.entries[:40]:
                title = entry.get('title', '').strip()
                link = entry.get('link', '').strip()
                summary = entry.get('summary', entry.get('description', '')).strip()

                if not title or not link:
                    continue

                pub_date = _parse_date(entry)
                sym = _extract_symbol(title) or _extract_symbol(summary)

                # Sembol filtresi
                if symbol:
                    title_up = title.upper()
                    sym_up = symbol.upper()
                    if sym_up not in title_up and sym_up not in summary.upper():
                        continue

                # DB'ye kaydet
                obj, _ = NewsItem.objects.get_or_create(
                    link=link,
                    defaults={
                        'title': title,
                        'summary': summary[:500] if summary else '',
                        'source': source,
                        'symbol': sym,
                        'published_at': pub_date,
                    }
                )

                items.append({
                    'title': obj.title,
                    'summary': obj.summary,
                    'link': obj.link,
                    'symbol': obj.symbol,
                    'published_at': str(obj.published_at) if obj.published_at else None,
                    'source': obj.source,
                })

        except Exception as e:
            feed_errors.append(f"{feed_url}: {str(e)[:80]}")
            continue

    # Eger hic haber gelemediyse DB'den goster
    if not items:
        qs = NewsItem.objects.all()
        if symbol:
            qs = qs.filter(symbol__iexact=symbol)
        for obj in qs[:limit]:
            items.append({
                'title': obj.title,
                'summary': obj.summary,
                'link': obj.link,
                'symbol': obj.symbol,
                'published_at': str(obj.published_at) if obj.published_at else None,
                'source': obj.source + ' (cache)',
            })

    # Tarihe gore sirala, tekrar eden linkleri kaldir
    seen = set()
    unique_items = []
    for item in items:
        if item['link'] not in seen:
            seen.add(item['link'])
            unique_items.append(item)

    unique_items.sort(
        key=lambda x: x['published_at'] or '1970-01-01',
        reverse=True
    )

    return unique_items[:limit]


@api_view(['GET'])
def latest_news(request):
    """
    Son haberler - GET /api/news/
    ?symbol=MOGAN  (opsiyonel filtre)
    """
    symbol = request.query_params.get('symbol', '').upper().strip()
    news = fetch_kap_news(symbol=symbol or None, limit=20)
    return Response({
        'count': len(news),
        'news': news,
        'note': 'KAP resmi bildirimleri ve finans haberleri'
    })


@api_view(['GET'])
def news_for_symbol(request, symbol):
    """Belirli hisse haberleri - GET /api/news/MOGAN/"""
    symbol = symbol.upper()
    news = fetch_kap_news(symbol=symbol, limit=15)
    return Response({
        'symbol': symbol,
        'count': len(news),
        'news': news
    })


@api_view(['GET'])
def cached_news(request):
    """Sadece DB cache - GET /api/news/cached/"""
    symbol = request.query_params.get('symbol', '').upper()
    qs = NewsItem.objects.all()
    if symbol:
        qs = qs.filter(symbol__iexact=symbol)
    items = list(qs[:50].values(
        'title', 'summary', 'link', 'symbol', 'published_at', 'source', 'fetched_at'
    ))
    return Response({'count': len(items), 'news': items})
