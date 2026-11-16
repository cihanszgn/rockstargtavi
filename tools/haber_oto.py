#!/usr/bin/env python3
"""Saatlik haber akışı: 10 kaynaktan aday toplar, yayın paketini doğrular, tekrarları eler.

Metni araştırıp yazan zamanlanmış ajandır; RSS metni otomatik haber diye kopyalanmaz.
Kullanım ve yayın sözleşmesi: otomasyon/SAATLIK-HABER.md.
"""
from __future__ import annotations

import argparse
import concurrent.futures
from contextlib import closing
import html
import json
import pathlib
import re
import sqlite3
import subprocess
import sys
import unicodedata
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'otomasyon/kaynaklar.json').read_text(encoding='utf-8'))
DILLER = ('tr', 'en', 'fr', 'es')
TRT = timezone(timedelta(hours=3))
UA = 'Mozilla/5.0 (compatible; CTRLAGAME-News/1.0; +https://ctrl-agame.com/hakkinda.html)'
SENARYO = ROOT / 'video/senaryo'
AYARLAR = ROOT / 'sosyal/ayarlar.json'


def simdi():
    return datetime.now(timezone.utc)


def norm(value):
    value = str(value).lower().replace('ı', 'i')
    return re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFD', value).encode('ascii', 'ignore').decode()).strip()


def kanonik(url):
    p = urllib.parse.urlsplit(url)
    query = urllib.parse.urlencode(sorted((k, v) for k, v in urllib.parse.parse_qsl(p.query)
                                         if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid', 'ref')))
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/'), query, ''))


def https(url):
    try:
        p = urllib.parse.urlsplit(url)
        return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password and p.port in (None, 443)
    except (TypeError, ValueError):
        return False


def resmi(url):
    if not https(url):
        return False
    p = urllib.parse.urlsplit(url)
    if p.path.rstrip('/') in ('', '/news', '/en-US/news', '/feed', '/en-us', '/us/whatsnew'):
        return False
    # Steam'in haricî basın akışı, kullanıcı incelemeleri ve forum yazıları resmî duyuru sayılmaz.
    if '/externalpost/' in p.path or '/discussions/' in p.path or '/appreviews/' in p.path:
        return False
    if p.hostname == 'steamcommunity.com' and not re.match(r'^/(?:games|ogg)/[^/]+/announcements/detail/', p.path):
        return False
    return any(p.hostname == host or p.hostname.endswith('.' + host) for host in CONFIG['resmi_alanlar'])


def tarih(value):
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except ValueError:
            return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def aday_tarihi(item):
    published = tarih(item.get('tarih'))
    if published:
        return published
    match = re.match(r'^(\d{2})/(\d{2})/(\d{2})\b', item.get('baslik', ''))
    if match:
        try:
            month, day, year = map(int, match.groups())
            return datetime(2000 + year, month, day, tzinfo=timezone.utc)
        except ValueError:
            pass
    match = re.search(r'/(20\d{2})/(\d{2})/(\d{2})/', item.get('url', ''))
    if match:
        try:
            return datetime(*map(int, match.groups()), tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def tarih_suz(items, now):
    kept = []
    for item in items:
        dt = aday_tarihi(item)
        if dt and not now - timedelta(hours=CONFIG['sinirlar']['son_saat']) <= dt <= now + timedelta(minutes=5):
            continue
        kept.append(dict(item, tarih=dt.isoformat() if dt else None))
    return kept


def getir(url):
    if not https(url):
        raise ValueError('yalnız HTTPS kaynak okunur')
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/xml,text/html,application/json'})
    with urllib.request.urlopen(req, timeout=25) as response:
        if not https(response.geturl()):
            raise ValueError('HTTPS dışı yönlendirme')
        raw = response.read(2_500_001)
        if len(raw) > 2_500_000:
            raise ValueError('kaynak 2.5 MB sınırını aşıyor')
        return raw


def steam_adresi(gid):
    # ISteamNews gid duyuru kimliği değildir; resmî yönlendirici gerçek adresi verir.
    url = f'https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/{gid}'
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=15) as response:
        final = response.geturl()
        if not resmi(final) or urllib.parse.urlsplit(final).hostname != 'steamcommunity.com':
            raise ValueError('Steam yönlendirmesi resmî duyuru detayına ulaşmadı')
        return final


def rss_oku(raw, source, now):
    if b'<!ENTITY' in raw or b'<!DOCTYPE' in raw:
        raise ValueError('DTD/entity içeren akış kabul edilmez')
    root = ET.fromstring(raw)
    if root.tag.split('}')[-1] not in ('rss', 'feed', 'RDF'):
        raise ValueError('RSS/Atom/RDF yerine başka içerik döndü')
    out = []
    for item in root.iter():
        if item.tag.split('}')[-1] not in ('item', 'entry'):
            continue
        fields = {x.tag.split('}')[-1]: x for x in item}
        def val(key):
            return fields[key].text or '' if key in fields else ''
        title = html.unescape(val('title')).strip()
        links = [x for x in item if x.tag.split('}')[-1] == 'link']
        url = next((x.get('href') or x.text or '' for x in links if x.get('rel', 'alternate') == 'alternate'), '').strip()
        published = tarih(val('pubDate') or val('published') or val('date') or val('updated'))
        if not title or not https(url):
            continue
        out.append({'kaynak': source['id'], 'ad': source['ad'], 'baslik': title,
                    'url': url, 'tarih': published.isoformat() if published else None,
                    'resmi_aday': resmi(url)})
    return out


class LinkOku(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.current, self.text = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.current, self.text = dict(attrs).get('href'), []

    def handle_data(self, data):
        if self.current:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.current:
            self.links.append((self.current, ' '.join(self.text)))
            self.current = None


def _kaynak_tara(source, now):
    try:
        if source.get('rss'):
            items = rss_oku(getir(source['rss']), source, now)
            return {'id': source['id'], 'durum': 'ok', 'adet': len(items), 'web_gerekli': not bool(items)}, items
        if source.get('api'):
            data = json.loads(getir(source['api']))
            items = []
            if source.get('bicim') == 'steam':
                for item in data['appnews']['newsitems']:
                    if item.get('feedname') != 'steam_community_announcements':
                        continue
                    gid = str(item['gid'])
                    if not gid.isdigit():
                        continue
                    items.append({'kaynak': source['id'], 'ad': source['ad'], 'baslik': item['title'],
                                  'url': f'https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/{gid}', 'steam_gid': gid,
                                  'tarih': datetime.fromtimestamp(item['date'], timezone.utc).isoformat(), 'resmi_aday': True})
                return {'id': source['id'], 'durum': 'ok', 'web_gerekli': False}, items
            for item in data['data']['Catalog']['searchStore']['elements']:
                promotions = item.get('promotions') or {}
                if not (promotions.get('promotionalOffers') or promotions.get('upcomingPromotionalOffers')):
                    continue
                slug = next((x.get('pageSlug') for x in item.get('catalogNs', {}).get('mappings', []) if x.get('pageSlug')), None) or item.get('productSlug') or item.get('urlSlug')
                offers = [o for group in ('promotionalOffers', 'upcomingPromotionalOffers')
                          for bundle in promotions.get(group, []) for o in bundle.get('promotionalOffers', [])]
                for offer in offers:
                    start, end = tarih(offer.get('startDate')), tarih(offer.get('endDate'))
                    if not start or not end or end <= now or offer.get('discountSetting', {}).get('discountPercentage') != 0:
                        continue
                    if not slug:
                        continue
                    store = 'https://store.epicgames.com/en-US/p/' + slug.removesuffix('/home')
                    items.append({'kaynak': source['id'], 'ad': source['ad'], 'baslik': item['title'],
                                  'url': store, 'tarih': start.isoformat() if start <= now else None, 'resmi_aday': True,
                                  'resmi_veri': {'api_url': source['api'], 'alinma_zamani': now.isoformat(),
                                                'oyun': item['title'], 'baslangic': start.isoformat(),
                                                'bitis': end.isoformat(), 'magaza_url': store, 'ulke': 'TR'}})
            return {'id': source['id'], 'durum': 'ok', 'web_gerekli': False,
                    'not': 'Epic API kampanya olguları resmî teyittir; mağaza 403 olsa da geçerlidir.'}, items
        parser = LinkOku()
        parser.feed(getir(source['url']).decode('utf-8', errors='replace'))
        out, seen = [], set()
        for link, title in parser.links:
            url = urllib.parse.urljoin(source['url'], link)
            if source['yol'] not in urllib.parse.urlsplit(url).path or len(title.strip()) < 20:
                continue
            if kanonik(url) in seen or kanonik(url) == kanonik(source['url']):
                continue
            seen.add(kanonik(url))
            out.append({'kaynak': source['id'], 'ad': source['ad'], 'baslik': title.strip()[:220],
                        'url': url, 'tarih': None, 'resmi_aday': resmi(url)})
        return {'id': source['id'], 'durum': 'ok' if out else 'kismi', 'adet': min(len(out), 10),
                'web_gerekli': True, 'not': 'Gerçek haber metni kaynak sayfasında okunmalı.'}, out
    except (OSError, ValueError, ET.ParseError, KeyError) as error:
        return {'id': source['id'], 'durum': 'hata', 'adet': 0, 'web_gerekli': True,
                'hata': str(error)[:250]}, []


def kaynak_tara(source, now):
    status, items = _kaynak_tara(source, now)
    fresh = tarih_suz(items, now)
    fresh.sort(key=lambda x: (bool(x['tarih']), x['tarih'] or ''), reverse=True)
    kept = fresh[:source.get('aday_siniri', CONFIG['sinirlar'].get('kaynak_basina', 6))]
    limited = len(kept)
    if source.get('bicim') == 'steam':
        resolved, errors = [], []
        for item in kept:
            try:
                item['url'] = steam_adresi(item['steam_gid'])
                resolved.append(item)
            except (OSError, ValueError) as exc:
                errors.append(str(exc)[:200])
        kept = resolved
        if errors:
            status.update(durum='kismi', web_gerekli=True, teyit_hatalari=errors)
    status.update(adet=len(kept), bulunan=len(items), tarih_elendi=len(items) - len(fresh),
                  sinir_elendi=len(fresh) - limited, tarihsiz=sum(not x['tarih'] for x in kept))
    return status, kept


def tara(now=None):
    now = now or simdi()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda s: kaynak_tara(s, now), CONFIG['kaynaklar']))
    return {'zaman': now.isoformat(), 'kaynaklar': [s for s, _ in results],
            'adaylar': [item for _, items in results for item in items]}


def _db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=3, isolation_level=None)
    db.execute('CREATE TABLE IF NOT EXISTS lease (id INTEGER PRIMARY KEY CHECK(id=1), token TEXT, expiry REAL)')
    return db


def kilit_al(path, now=None):
    now = now or simdi()
    db = _db(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT token, expiry FROM lease WHERE id=1').fetchone()
        if row and row[1] > now.timestamp():
            db.rollback()
            return None
        token = uuid.uuid4().hex
        db.execute('INSERT OR REPLACE INTO lease VALUES (1, ?, ?)', (token, (now + timedelta(minutes=45)).timestamp()))
        db.commit()
        return token
    finally:
        db.close()


def kilit_kontrol(path, token, now=None):
    now = now or simdi()
    with closing(_db(path)) as db:
        row = db.execute('SELECT token, expiry FROM lease WHERE id=1').fetchone()
        if not row or row[0] != token or row[1] <= now.timestamp():
            raise ValueError('yayın kilidi yok, süresi dolmuş ya da başka oturuma ait')


def kilit_birak(path, token):
    with closing(_db(path)) as db:
        return db.execute('DELETE FROM lease WHERE id=1 AND token=?', (token,)).rowcount == 1


def senaryo_denetle(haber, klasor=None):
    """Haberle birlikte yazılmış video senaryosu varsa, yayından önce haber metniyle tutarlı mı diye sınar.

    Senaryo yalnız varsa denetlenir; hype eşiğe ulaşan haberde hazirla onun varlığını ayrıca zorunlu kılar. Sayı ve tarihler yalnız haber metninden gelebilir.
    """
    errors = []
    for lang in DILLER:
        path = (klasor or SENARYO) / f"{haber['id']}-{lang}.json"
        if path.exists():
            # Video araçları yalnız senaryo varken yüklenir: haber akışı onlara bağımlı kalmaz.
            import video_uret
            errors += [f'{path.name}: {e}' for e in video_uret.senaryo_dosyasi_denetle(path, haber, lang)]
    return errors


def hype_esigi():
    """Video eşiği sosyal/ayarlar.json → video.hype_esigi (yoksa 7). Video araçlarını içe aktarmaz."""
    if not AYARLAR.exists():
        return 7
    return int((json.loads(AYARLAR.read_text(encoding='utf-8')).get('video') or {}).get('hype_esigi', 7))


def kesif_kaynagi(url):
    if not https(url):
        return None
    host = urllib.parse.urlsplit(url).hostname
    for source in CONFIG['kaynaklar']:
        domain = urllib.parse.urlsplit(source['url']).hostname.removeprefix('www.')
        if source['rol'] == 'kesif' and (host == domain or host.endswith('.' + domain)):
            return source
    return None


def ortak_api(url):
    return kanonik(url) in {kanonik(s['api']) for s in CONFIG['kaynaklar'] if s.get('api')}


def epic_kanit_denetle(auto, incoming, now):
    url = auto.get('resmi_url', '')
    epic = next(s for s in CONFIG['kaynaklar'] if s['id'] == 'epic')
    if kanonik(url) != kanonik(epic['api']):
        return
    data = auto.get('resmi_veri')
    if not isinstance(data, dict):
        raise ValueError('Epic API teyidi için taranan kampanya olguları gerekli')
    fetched, start, end = (tarih(data.get(k)) for k in ('alinma_zamani', 'baslangic', 'bitis'))
    store = data.get('magaza_url', '')
    if (data.get('api_url') != epic['api'] or not isinstance(data.get('oyun'), str) or not data['oyun'].strip()
            or data.get('ulke') != 'TR' or not fetched or not timedelta(0) <= now - fetched <= timedelta(hours=2)
            or not start or not end or start >= end or end <= now or not https(store)
            or urllib.parse.urlsplit(store).hostname != 'store.epicgames.com'
            or not urllib.parse.urlsplit(store).path.startswith('/en-US/p/') or kanonik(store) not in incoming):
        raise ValueError('Epic kampanya kanıtı tarih/mağaza/bölge ile tutarlı ve güncel olmalı')


def teyit_denetle(auto, incoming, texts):
    kind = auto.get('teyit_turu', 'resmi')
    official = auto.get('resmi_url', '')
    if kind == 'resmi':
        if not resmi(official) or kanonik(official) not in incoming:
            raise ValueError('kaynaklar içinde izinli resmî kaynak gerekli')
        return
    if kind != 'birincil':
        raise ValueError('otomasyon.teyit_turu: resmi veya birincil olmalı')
    primary = auto.get('birincil_kaynak')
    reports = auto.get('capraz_kaynaklar')
    if (not isinstance(primary, dict) or primary.get('tur') not in ('aciklama', 'roportaj', 'resmi_sosyal', 'resmi_youtube')
            or any(not isinstance(primary.get(k), str) or len(primary[k].strip()) < 3 for k in ('kisi', 'gorev', 'kurum', 'olgu'))):
        raise ValueError('adı ve görevi verilen yetkiliye ait birincil açıklama gerekli; sızıntı/söylenti kabul edilmez')
    claim = primary['olgu'] + ' ' + ' '.join(x.get('baslik', '') for x in texts.values())
    if re.search(r'\b(leak(?:ed|s)?|rumou?rs?|reportedly|anonymous|unnamed|sizinti|soylenti|isimsiz)\b', norm(claim)):
        raise ValueError('sızıntı, söylenti veya isimsiz kaynak birincil teyit sayılmaz')
    if not isinstance(reports, list) or len(reports) < 2:
        raise ValueError('birincil teyit için en az iki bağımsız keşif yayını gerekli')
    groups, names = set(), []
    for url in reports:
        source = kesif_kaynagi(url)
        if not source or kanonik(url) not in incoming:
            raise ValueError('çapraz kaynaklar izinli keşif yayınları ve kaynaklar içinde olmalı')
        groups.add(source.get('yayin_grubu', source['id']))
        names.append(source['ad'])
    if len(groups) < 2:
        raise ValueError('aynı yayın grubundaki iki sayfa bağımsız teyit sayılmaz')
    if any(not any(norm(name) in norm(text.get('metin', '')) for name in names) for text in texts.values()):
        raise ValueError('birincil teyitte her dilin metninde kaynak yayının adı açıkça anılmalı')


def hazirla(existing, batch, now=None, senaryo_klasoru=None):
    now = now or simdi()
    if not isinstance(batch, list) or len(batch) > CONFIG['sinirlar']['tur_basina']:
        raise ValueError('paket liste olmalı ve en fazla 3 haber içermeli')
    today = now.astimezone(TRT).date()
    used = sum(1 for x in existing if x.get('otomasyon') and
               str(x['otomasyon'].get('eklenme') or x.get('tarih', ''))[:10] == today.isoformat())
    urls = {kanonik(s['url']) for x in existing for s in x.get('kaynaklar', []) if not ortak_api(s['url'])}
    ids = {x['id'] for x in existing}
    titles = {norm(x.get('diller', {}).get('tr', {}).get('baslik', '')) for x in existing}
    topics = {x.get('otomasyon', {}).get('konu') for x in existing}
    added = []
    for x in batch:
        if not isinstance(x, dict):
            raise ValueError('her haber bir nesne olmalı')
        auto = x.get('otomasyon') or {}
        tr = x.get('diller', {}).get('tr', {})
        sources = x.get('kaynaklar') or []
        incoming = {kanonik(s.get('url', '')) for s in sources}
        if (x.get('id') in ids or norm(tr.get('baslik', '')) in titles or
                (auto.get('konu') and auto['konu'] in topics) or {u for u in incoming if not ortak_api(u)} & urls):
            continue
        if used + len(added) >= CONFIG['sinirlar']['gunluk']:
            break
        for field in ('id', 'oyun', 'tarih', 'tur'):
            if not isinstance(x.get(field), str) or not x[field].strip():
                raise ValueError(f'{field}: zorunlu metin')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', x['id']):
            raise ValueError('geçersiz haber id')
        if x['tur'] not in ('haber', 'guncelleme', 'cikis', 'ucretsiz', 'indirim'):
            raise ValueError('geçersiz haber türü; söylenti haber akışına giremez')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', x['tarih']):
            raise ValueError('haber tarihi YYYY-AA-GG olmalı')
        dt = datetime.fromisoformat(x['tarih']).date()
        if not 0 <= (today - dt).days <= 2:
            raise ValueError('haber tarihi gelecek ya da 48 saatlik pencerenin dışında')
        if not sources or any(not https(s.get('url')) or not s.get('ad') for s in sources):
            raise ValueError('adlandırılmış HTTPS kaynaklar gerekli')
        if 'platform' in x and not (isinstance(x['platform'], list) and all(isinstance(p, str) and p.strip() for p in x['platform'])):
            raise ValueError('platform metin listesi olmalı')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', str(auto.get('konu', ''))):
            raise ValueError('otomasyon.konu: olayın tekrarını önleyecek değişmez kimlik gerekli')
        checked = tarih(auto.get('teyit_zamani'))
        if (not checked or not timedelta(0) <= now - checked <= timedelta(hours=2) or len(str(auto.get('oyuncuya_fayda', ''))) < 30):
            raise ValueError('son 2 saatte okunmuş kaynak ve oyuncuya somut fayda açıklaması gerekli')
        teyit_denetle(auto, incoming, x.get('diller', {}))
        epic_kanit_denetle(auto, incoming, now)
        hype = auto.get('hype')
        if type(hype) is not int or not 1 <= hype <= 10:
            raise ValueError('otomasyon.hype: 1–10 arası tam sayı gerekli')
        if hype >= hype_esigi() and not ((senaryo_klasoru or SENARYO) / f"{x['id']}-tr.json").exists():
            raise ValueError('otomasyon.hype eşiğe ulaştı: video senaryosu (video/senaryo/<id>-tr.json) gerekli')
        for lang in DILLER:
            content = x.get('diller', {}).get(lang) or {}
            if not all(isinstance(content.get(k), str) and content[k].strip() for k in ('baslik', 'ozet', 'metin')):
                raise ValueError(f'{lang}: başlık, özet veya metin eksik')
            if len(content['baslik']) > 100 or not 50 <= len(content['metin'].split()) <= 300:
                raise ValueError(f'{lang}: başlık en fazla 100 karakter, haber 50–300 kelime olmalı')
            if any(not isinstance(tag, str) or not re.fullmatch(r'#[A-Za-z0-9]+', tag) for tag in content.get('etiketler', [])):
                raise ValueError(f'{lang}: geçersiz etiket')
        errors = senaryo_denetle(x, senaryo_klasoru)
        if errors:
            raise ValueError('video senaryosu: ' + '; '.join(errors[:10]))
        new = json.loads(json.dumps(x, ensure_ascii=False))
        new['otomasyon']['eklenme'] = now.astimezone(TRT).isoformat()
        added.append(new)
        ids.add(x['id']); titles.add(norm(tr['baslik'])); topics.add(auto['konu']); urls.update(u for u in incoming if not ortak_api(u))
    return added + existing, added


class Sayfa(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.ids, self.links = set(), []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id'): self.ids.add(a['id'])
        if tag in ('a', 'img', 'script', 'link'):
            url = a.get('href') or a.get('src')
            if url: self.links.append(url)


def baglantilari_kontrol(root=ROOT):
    pages = {p.resolve(): Sayfa(p.read_text(encoding='utf-8')) for p in root.rglob('*.html') if '.git' not in p.parts}
    errors, n = [], 0
    for path, page in pages.items():
        for link in page.links:
            url = urllib.parse.urlsplit(link)
            if (url.netloc and url.hostname not in ('ctrl-agame.com', 'www.ctrl-agame.com')) or url.scheme not in ('', 'http', 'https'):
                continue
            raw = urllib.parse.unquote(url.path)
            target = root / raw.lstrip('/') if raw.startswith('/') else path.parent / raw
            if not raw: target = path
            target = target.resolve()
            if target.is_dir(): target /= 'index.html'
            n += 1
            if not target.exists() or (url.fragment and target in pages and urllib.parse.unquote(url.fragment) not in pages[target].ids):
                errors.append(f'{path.relative_to(root)} -> {link}')
    if errors:
        raise ValueError('kırık iç bağlantı: ' + '; '.join(errors[:15]))
    return {'sayfa': len(pages), 'baglanti': n, 'bozuk': 0}


def state_dir():
    gitdir = subprocess.run(['git', 'rev-parse', '--git-dir'], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    result = (ROOT / gitdir).resolve() / 'haber-oto'
    result.mkdir(parents=True, exist_ok=True)
    return result


def json_yaz(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('eylem', choices=['tara', 'kilit-al', 'kilit-kontrol', 'kilit-birak', 'hazirla', 'kontrol'])
    parser.add_argument('--batch', type=pathlib.Path)
    parser.add_argument('--token')
    parser.add_argument('--uygula', action='store_true')
    args = parser.parse_args()
    state = state_dir()
    lock = state / 'kilit.sqlite'
    if args.eylem == 'kilit-al':
        token = kilit_al(lock)
        result = {'durum': 'alindi' if token else 'mesgul', 'token': token}
    elif args.eylem == 'kilit-birak':
        result = {'birakildi': kilit_birak(lock, args.token or '')}
    elif args.eylem == 'kilit-kontrol':
        kilit_kontrol(lock, args.token or '')
        result = {'gecerli': True}
    elif args.eylem == 'tara':
        result = tara()
        path = state / 'adaylar.json'
        json_yaz(path, result)
        result = {'dosya': str(path), 'kaynaklar': result['kaynaklar'], 'aday': len(result['adaylar'])}
    elif args.eylem == 'kontrol':
        result = baglantilari_kontrol()
    else:
        if not args.batch:
            parser.error('--batch gerekli')
        original = (ROOT / 'data/icerik.json').read_bytes()
        existing = json.loads(original)
        merged, added = hazirla(existing, json.loads(args.batch.read_text(encoding='utf-8')))
        json_yaz(state / 'onizleme.json', merged)
        if args.uygula and added:
            kilit_kontrol(lock, args.token or '')
            branch = subprocess.run(['git', 'branch', '--show-current'], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
            dirty = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
            if branch != 'main' or dirty:
                raise ValueError('uygulama yalnız temiz main dalında yapılır; açık değişiklikleri koru')
            if (ROOT / 'data/icerik.json').read_bytes() != original:
                raise ValueError('içerik eşzamanlı değişti; yeniden hazırla')
            # Geri alma dosyası yalnız bu çalıştırmanın kendi haber değişikliğini kapsar.
            (state / 'icerik-once.json').write_bytes(original)
            json_yaz(ROOT / 'data/icerik.json', merged)
        result = {'eklenen': [x['id'] for x in added], 'adet': len(added), 'uygulandi': bool(args.uygula and added),
                  'onizleme': str(state / 'onizleme.json')}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, sqlite3.Error) as error:
        print(json.dumps({'hata': str(error)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
