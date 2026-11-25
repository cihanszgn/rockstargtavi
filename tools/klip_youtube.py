"""Anahtarsız YouTube kaynağı; yalnız yerel bilgisayarda, yayın yapmaz.

Üretim için tüm görüntü indirilmez: yt-dlp zaman aralığı indirmesi kullanılır.
Altyazı aday üretir; kesin kesim sınırı ve ses referansı yerel Whisper'dandır.
"""
from __future__ import annotations

import contextlib
import difflib
import html
import json
import math
import pathlib
import re
import subprocess
import time
import urllib.parse
from datetime import datetime, timezone

import klip_konusma as k

AYAR = {'youtube_min_sure_sn': 300, 'youtube_liste_siniri': 50,
        'youtube_heatmap_agirlik': .2, 'youtube_heatmap_min': .6,
        'youtube_aday_whisper': True}


def video_id(arg):
    if arg.startswith('youtube:'):
        value = arg[8:]
    else:
        p = urllib.parse.urlparse(arg)
        host = (p.hostname or '').lower()
        if host == 'youtu.be':
            value = p.path.strip('/').split('/')[0]
        elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
            value = urllib.parse.parse_qs(p.query).get('v', [''])[0]
            if not value and p.path.startswith(('/shorts/', '/live/', '/embed/')):
                value = p.path.split('/')[2]
        else:
            return None
    return value if re.fullmatch(r'[A-Za-z0-9_-]{11}', value) else None


def bot_engeli(exc):
    text = str(exc).lower()
    return any(x in text for x in ("not a bot", 'confirm you', 'http error 403', 'status code: 403'))


def istemciyle(operasyon):
    """Normal istemci önce; yalnız bot/403 engelinde bir kez çerezsiz yedek."""
    try:
        return operasyon({}), 'normal'
    except Exception as e:
        if not bot_engeli(e):
            raise
    return operasyon({'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'tv']}}}), 'android,ios,tv'


def dene(islem, deneme=2, bekle=5.0):
    """Geçici indirme/ffmpeg çökmesi için tek yeniden deneme; bot engeli ve üyelik hatası yeniden denenmez.
    Hata hep RuntimeError olarak çıkar (yt-dlp DownloadError analizi çökertmesin)."""
    son = None
    for i in range(deneme):
        try:
            return islem()
        except Exception as e:
            son = e
            if bot_engeli(e) or any(x in str(e).lower() for x in ('members-only', 'private video', 'unavailable')):
                break
            if i + 1 < deneme:
                time.sleep(bekle)
    raise RuntimeError(f'YouTube indirme: {str(son)[-300:]}') from son


class SessizLog:
    def debug(self, *a): pass
    def warning(self, *a): pass
    def error(self, *a): pass


def bilgi(arg, flat=False, limit=50):
    import yt_dlp
    def run(extra):
        opts = {'quiet': True, 'no_warnings': True, 'logger': SessizLog(),
                'skip_download': True, 'socket_timeout': 30, 'retries': 1,
                'extract_flat': 'in_playlist' if flat else False,
                **({'playlistend': limit, 'extractor_args': {'youtubetab': {'approximate_date': ['1']}}}
                   if flat else {'noplaylist': True}), **extra}
        with yt_dlp.YoutubeDL(opts) as dl:
            return dl.extract_info(arg, download=False)
    value, client = istemciyle(run)
    value['_klip_istemci'] = client
    return value


def yayin_kaydi(y):
    """Eski Kick kaydı aynen kalır; youtube_kanallari ek kaynak listesidir."""
    return [c for c in y.get('youtube_kanallari', []) if c.get('etkin', True)]


def yayinci(ayar, channel_id):
    for y in ayar['yayincilar']:
        for c in y.get('youtube_kanallari', []):
            if c['kanal_id'] == channel_id:
                return y, c
    return None, None


def normalle(info, ayar):
    y, channel = yayinci(ayar, info.get('channel_id'))
    handle = (info.get('uploader_id') or (channel or {}).get('tanitici') or info.get('channel_id') or '').lstrip('@')
    date = info.get('upload_date') or info.get('release_date')
    if not date:
        raise RuntimeError('YouTube video tarihi yok; yeni video olduğu varsayılmaz')
    epoch = int(datetime.strptime(date, '%Y%m%d').replace(tzinfo=timezone.utc).timestamp())
    vid = info['id']
    return {'platform': 'youtube', 'vod_id': vid, 'anahtar': f'youtube:{vid}',
            'yayinci': y['ad'] if y else info.get('channel', handle), 'kanal': handle,
            'kanal_id': info.get('channel_id'), 'kanal_url': f'https://www.youtube.com/@{handle}',
            'baslik': info.get('title', ''), 'oyun': '', 'kategoriler': info.get('categories') or [],
            'baslangic_epoch': epoch, 't0_epoch': 0, 'sure_sn': info.get('duration') or 0,
            'canli': bool(info.get('is_live')), 'kaynak': f'https://www.youtube.com/watch?v={vid}',
            'vod_url': f'https://www.youtube.com/watch?v={vid}',
            'tarih': datetime.fromtimestamp(epoch, timezone.utc).strftime('%Y-%m-%d'),
            'youtube_istemci': info.get('_klip_istemci', 'normal')}


def atlama_nedeni(info, cfg, simdi=None, tarih_suz=True):
    url = info.get('webpage_url') or info.get('url') or ''
    if '/shorts/' in url or info.get('_type') == 'short':
        return 'shorts'
    if info.get('availability') in ('subscriber_only', 'premium_only', 'needs_auth', 'private'):
        return 'uyelere_ozel_veya_ozel'
    if info.get('is_live') or info.get('live_status') in ('is_live', 'is_upcoming', 'post_live'):
        return 'canli_veya_islenmemis'
    if info.get('duration') is None:
        return 'sure_bilinmiyor'
    if info['duration'] < cfg.get('youtube_min_sure_sn', 300):
        return 'cok_kisa'
    date = info.get('upload_date') or info.get('release_date')
    if tarih_suz:
        if not date:
            return 'tarih_bilinmiyor'
        epoch = datetime.strptime(date, '%Y%m%d').replace(tzinfo=timezone.utc).timestamp()
        if epoch < (simdi or time.time()) - cfg.get('son_gun', 7)*86400:
            return 'eski'
    return None


def tara(ayar, dizin, yayinci_filtresi=None, hepsi=False, simdi=None, getir=bilgi):
    import yayin_klip as yk
    cfg = {**AYAR, **ayar['ayar']}
    durum = yk.durum_oku(pathlib.Path(dizin))
    result = {'yeni': [], 'atlanan_islenmis': [], 'youtube_atlanan': [], 'youtube_kanallar': [], 'hata': []}
    seen = set()
    for y in ayar['yayincilar']:
        if not y['etkin'] or (yayinci_filtresi and yayinci_filtresi.lower() not in (y['ad'].lower(), y['kanal'].lower())):
            continue
        for c in yayin_kaydi(y):
            count = {'yayinci': y['ad'], 'kanal_id': c['kanal_id'], 'bulunan': 0, 'atlanan': 0, 'nedenler': {}}
            ccfg = {**cfg, **y['ayar'], **c.get('ayar', {})}
            for tab in ('videos', 'streams'):
                try:
                    entries = getir(f"https://www.youtube.com/channel/{c['kanal_id']}/{tab}",
                                     flat=True, limit=ccfg['youtube_liste_siniri']).get('entries') or []
                except Exception as e:
                    if 'does not have a' in str(e) and 'tab' in str(e):
                        continue
                    result['hata'].append({'yayinci': y['ad'], 'sekme': tab, 'hata': str(e)[-500:]})
                    continue
                for entry in entries:
                    vid = entry.get('id')
                    if not vid or vid in seen:
                        continue
                    seen.add(vid)
                    reason = atlama_nedeni(entry, ccfg, simdi, tarih_suz=False)
                    # Yaklaşık tarih yalnız kesin biçimde eski girdiler için optimizasyon.
                    # Son 14 günlük belirsizlik bandında tekil kesin tarih zorunlu.
                    approx = entry.get('timestamp')
                    if not reason and approx and approx < (simdi or time.time())-(ccfg['son_gun']+14)*86400:
                        reason = 'eski_yaklasik_tarih'
                    # Flat listede tarih bulunmayabilir; tekil metadata ile kesin süz.
                    info = entry
                    if not reason:
                        if yk.islendi_mi(durum, f'youtube:{vid}') and not hepsi:
                            reason = 'islenmis'
                            result['atlanan_islenmis'].append(f'youtube:{vid}')
                        else:
                            try:
                                info = getir(f'https://www.youtube.com/watch?v={vid}')
                                reason = atlama_nedeni(info, ccfg, simdi)
                            except Exception as e:
                                reason = 'uyelere_ozel' if any(s in str(e).lower() for s in ('members-only', 'join this channel', 'members only')) else 'bilgi_hatasi'
                                result['hata'].append({'anahtar': f'youtube:{vid}', 'hata': str(e)[-500:]})
                    if reason:
                        count['atlanan'] += 1
                        count['nedenler'][reason] = count['nedenler'].get(reason, 0)+1
                        result['youtube_atlanan'].append({'anahtar': f'youtube:{vid}', 'yayinci': y['ad'], 'neden': reason})
                        continue
                    vod = normalle(info, ayar)
                    uygun, _ = yk.oyun_suzgeci(vod, ccfg)
                    if not uygun:
                        result['youtube_atlanan'].append({'anahtar': vod['anahtar'], 'yayinci': y['ad'], 'neden': 'oyun_suzgeci'})
                        count['atlanan'] += 1
                        count['nedenler']['oyun_suzgeci'] = count['nedenler'].get('oyun_suzgeci', 0)+1
                        continue
                    result['yeni'].append(vod)
                    count['bulunan'] += 1
            result['youtube_kanallar'].append(count)
    return result


def altyazi_json3(value):
    """JSON3 kelime ofsetlerini korur; kayan/tekrarlanan satırları tekler.
    Noktalamasız otomatik satırları cümle diye sunmaz; tarama birimleridir.
    """
    events = [e for e in value.get('events', []) if e.get('segs')]
    words, seen = [], set()
    for i, e in enumerate(events):
        start = float(e.get('tStartMs', 0))/1000
        end = start + float(e.get('dDurationMs', 0))/1000
        if i+1 < len(events):
            end = min(end, float(events[i+1].get('tStartMs', end*1000))/1000)
        segs = e['segs']
        for j, s in enumerate(segs):
            text = html.unescape(s.get('utf8', '')).replace('\n', ' ').strip()
            if not text:
                continue
            a = start+float(s.get('tOffsetMs', 0))/1000
            b = start+float(segs[j+1].get('tOffsetMs', (end-start)*1000))/1000 if j+1 < len(segs) else end
            key = (round(a, 3), text)
            if key not in seen and b > a:
                words.append({'bas': round(a, 3), 'bit': round(b, 3), 'metin': ' '+text})
                seen.add(key)
    # Altyazıda noktalama çoğu kez yoktur: model taraması için yaklaşık 8 sn satır.
    result, current = [], []
    for w in sorted(words, key=lambda w: w['bas']):
        if current and (w['bit']-current[0]['bas'] > 8 or w['bas']-current[-1]['bit'] > 2):
            result.append({'bas': current[0]['bas'], 'bit': current[-1]['bit'],
                           'metin': ''.join(x['metin'] for x in current).strip(), 'altyazi': True})
            current = []
        current.append(w)
    if current:
        result.append({'bas': current[0]['bas'], 'bit': current[-1]['bit'],
                       'metin': ''.join(x['metin'] for x in current).strip(), 'altyazi': True})
    return result


def altyazi_al(info, http):
    for lang in ('tr-orig', 'tr'):
        for item in info.get('automatic_captions', {}).get(lang, []):
            if item.get('ext') == 'json3':
                try:
                    rows = altyazi_json3(json.loads(http(item['url'])))
                    if rows:
                        return rows, lang
                except (OSError, RuntimeError, ValueError):
                    pass
    return [], None


def heatmap_tepeleri(points, minimum=.6, mesafe=60):
    peaks = []
    for i, p in enumerate(points or []):
        value = p.get('value', 0)
        if value < minimum or (i and points[i-1]['value'] > value) or (i+1 < len(points) and points[i+1]['value'] >= value):
            continue
        peaks.append({'sn': (p['start_time']+p['end_time'])/2, 'deger': value})
    selected = []
    for p in sorted(peaks, key=lambda p: -p['deger']):
        if not any(abs(p['sn']-s['sn']) < mesafe for s in selected):
            selected.append(p)
    return sorted(selected, key=lambda p: p['sn'])


def bolum_indir(vod, a, b, hedef, ff, ses=False):
    import yt_dlp
    from yt_dlp.utils import download_range_func
    from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor
    hedef = pathlib.Path(hedef)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    def run(extra):
        opts = {'quiet': True, 'no_warnings': True, 'logger': SessizLog(), 'noplaylist': True,
            'format': 'bestaudio/best' if ses else 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            'outtmpl': str(hedef), 'ffmpeg_location': ff, 'socket_timeout': 30,
            'retries': 1, 'fragment_retries': 1, 'overwrites': True,
            'download_ranges': download_range_func(None, [(a, b)]),
            'force_keyframes_at_cuts': True, 'merge_output_format': 'mkv', **extra}
        # yt-dlp CLI de bunu ayarlar: FFmpegFD.available() downloader opts'u okumuyor.
        token = FFmpegPostProcessor._ffmpeg_location.set(ff)
        try:
            with yt_dlp.YoutubeDL(opts) as dl:
                info = dl.extract_info(vod['vod_url'], download=True)
        finally:
            FFmpegPostProcessor._ffmpeg_location.reset(token)
        return info
    started = time.monotonic()
    info, client = dene(lambda: istemciyle(run))
    # yt-dlp birleşen biçimde uzantıyı değiştirebilir.
    actual = hedef if hedef.exists() else hedef.with_suffix('.mkv')
    if not actual.exists():
        raise RuntimeError('YouTube aralık indirmesi dosya üretmedi')
    formats = info.get('requested_formats') or [info]
    return actual, {'istemci': client, 'yukseklik': max((f.get('height') or 0 for f in formats), default=0),
                    'aralik': [a, b], 'sure_sn': round(time.monotonic()-started, 3)}


def whisper_dokum(vod, araliklar, dizin, cfg, ff, http=None):
    """300 sn atomik ızgara; ses yalnız istenen aralıklardan indirilir."""
    folder = pathlib.Path(dizin)/'dokum'/vod['anahtar'].replace(':', '-')
    step = int(cfg.get('konusma_parca_sn', 300))
    chunks = sorted({i for a, b in araliklar for i in range(max(0, int(a//step)), math.ceil(min(b, vod['sure_sn'])/step))})
    words, measurements = [], []
    for i in chunks:
        a, b = max(0, i*step-15), min(vod['sure_sn'], (i+1)*step+15)
        signature = k.imza(['yt-asr-v1', cfg['konusma_model'], cfg['konusma_cihaz'], step, i])
        path = folder/'whisper'/f'{signature}.json'
        audio = folder/'ses'/f'{signature}.wav'
        if path.exists() and audio.exists():
            value = json.loads(path.read_text(encoding='utf-8'))
            cached = True
        else:
            media, dl = bolum_indir(vod, a, b, folder/'ses'/f'{signature}.mkv', ff, True)
            r = subprocess.run([ff, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(media),
                '-t', str(b-a), '-vn', '-ac', '1', '-ar', '16000', str(audio)], capture_output=True, timeout=600)
            if r.returncode:
                raise RuntimeError('YouTube ASR sesi açılamadı')
            raw = k.dok_calistir(audio, cfg['konusma_model'], cfg['konusma_cihaz'], path.with_suffix('.worker.json'), kucuk=cfg['konusma_kucuk_model'])
            ww = [{**w, 'bas': round(a+w['bas'], 3), 'bit': round(a+w['bit'], 3)}
                  for s in raw['segmentler'] for w in s['kelimeler']
                  if i*step <= a+(w['bas']+w['bit'])/2 < (i+1)*step]
            value = {'kelimeler': ww, 'olcum': raw['olcum'], 'indirme': dl, 'ses_bas_sn': a, 'ses': str(audio)}
            k.json_yaz(path, value)
            cached = False
        words.extend(value['kelimeler'])
        measurements.append({**value['olcum'], 'onbellek': cached, 'youtube_ses': value['ses'],
                             'ses_bas_sn': a, 'aralik': [i*step, min(vod['sure_sn'], (i+1)*step)]})
    return k.cumleler(words), measurements


def ses_referanslari(item, measurements):
    a, b = item['klip_baslangic_sn'], item['klip_bitis_sn']
    for key, t in [('konusma_ses_referansi', a+.35), ('konusma_son_ses_referansi', b-.35)]:
        m = next((m for m in measurements if m['aralik'][0] <= t < m['aralik'][1]), None)
        if m is None:
            raise RuntimeError('YouTube klibinin gerçek ses referansı eksik')
        item[key] = {'dosya': m['youtube_ses'], 'bas_sn': m['ses_bas_sn'],
                     'hedef_bas_sn': a, 'hedef_bitis_sn': b}
    item['konusma_plan_araligi'] = [a, b]


def ayni_yayin(a, b):
    """Kimlik kesin değilse tarih/başlıkla an zamanlarını eşitleme.
    Kesin URL kimliği: aralık eşle. Muhtemel aynı tam yayın: tamamını incelemeye ayır.
    """
    import yayin_klip as yk
    if a.get('yayinci') != b.get('yayinci') or a.get('platform') == b.get('platform'):
        return 'farkli'
    sa, sb = a.get('sure_sn', 0), b.get('sure_sn', 0)
    ta, tb = ' '.join(yk.oyun_belirtecleri(a.get('baslik') or '')), ' '.join(yk.oyun_belirtecleri(b.get('baslik') or ''))
    date_delta = abs(yk.iso_epoch(a['tarih'])-yk.iso_epoch(b['tarih'])) if a.get('tarih') and b.get('tarih') else math.inf
    if min(sa, sb) >= 5400 and abs(sa-sb) <= max(120, .03*max(sa, sb)) and date_delta <= 2*86400 and ta and tb and difflib.SequenceMatcher(None, ta, tb).ratio() >= .75:
        return 'muhtemel_ayni_yayin_inceleme'
    return 'belirsiz'


def cift_kaynak_engeli(vod, dizin):
    """Paketlerdeki gerçek döküm eşleşmesi, kurgulu yüklemelerde zaman kaymasına dayanır."""
    matches = []
    for path in (pathlib.Path(dizin)/'cikti').glob('*/*.json'):
        try:
            p = json.loads(path.read_text(encoding='utf-8'))
            if p.get('platform') != 'kick' or p.get('yayinci') != vod['yayinci']:
                continue
            other = {'platform': 'kick', 'yayinci': p['yayinci'], 'tarih': p.get('yayin_tarihi'),
                     'baslik': p.get('yayin_basligi'), 'sure_sn': p.get('kaynak_sure_sn', 0)}
            if ayni_yayin(vod, other) == 'muhtemel_ayni_yayin_inceleme':
                matches.append(str(path))
        except (OSError, ValueError, KeyError):
            continue
    return matches


def metin_tekrar(item, vod, dizin):
    import yayin_klip as yk
    text = ' '.join(yk.oyun_belirtecleri(item.get('dokum_metni') or ''))
    if len(text.split()) < 15:
        return None
    for path in (pathlib.Path(dizin)/'cikti').glob('*/*.json'):
        try:
            p = json.loads(path.read_text(encoding='utf-8'))
            if p.get('platform') == vod['platform'] or p.get('yayinci') != vod['yayinci']:
                continue
            old = ' '.join(yk.oyun_belirtecleri(p.get('dokum_metni') or ''))
            if len(old.split()) >= 15 and difflib.SequenceMatcher(None, text, old, autojunk=False).ratio() >= .8:
                return str(path)
        except (OSError, ValueError):
            continue
    return None


def analiz(vod, info, dizin, cfg, ff, http):
    cfg = {**k.AYAR, **AYAR, **cfg}
    yargi_cfg = {**cfg, 'kisa_ad': cfg.get('kisa_ad') or vod.get('kisa_ad') or vod.get('yayinci')}  # ayar kaydına girmez
    if not cfg['konusma']:
        raise RuntimeError('YouTube sohbet içermez; konuşmasız analiz desteklenmiyor')
    uncertain = cift_kaynak_engeli(vod, dizin)
    if uncertain:
        return {'vod': vod, 'ayar': cfg, 'klipler': [], 'inceleme': uncertain,
                'konusma': {'durum': 'çift kaynak incelemesi bekliyor'}}
    rows, lang = altyazi_al(info, http)
    captions = rows
    measurements = []
    if not rows:
        rows, measurements = whisper_dokum(vod, [(0, vod['sure_sn'])], dizin, cfg, ff)
    model = k.ButceliModel(k.ModelYolu(cfg), cfg['konusma_cagri_butcesi']*max(1, math.ceil(vod['sure_sn']/7200)))
    folder = pathlib.Path(dizin)/'dokum'/vod['anahtar'].replace(':', '-')
    peaks = heatmap_tepeleri(info.get('heatmap'), cfg['youtube_heatmap_min'])
    answers = []
    size, overlap = int(cfg['konusma_pencere_sn']), int(cfg['konusma_ortusme_sn'])
    if not 0 <= overlap < size:
        raise ValueError('YouTube tarama örtüşmesi geçersiz')
    for a in range(0, math.ceil(vod['sure_sn']), size-overlap):
        window = [s for s in rows if a <= s['bas'] and s['bit'] <= a+size]
        if window:
            found = k.toplu_yargi([window], model, folder, yargi_cfg, True)[0]
            if found:
                answers.extend(found)
    # Heatmap yerel tepeleri de bağımsız adaydır; içerik yargısı zorunlu.
    heat_windows = [[s for s in rows if p['sn']-45 <= s['bas'] and s['bit'] <= p['sn']+45] for p in peaks[:cfg['konusma_aday_sayisi']]]
    if heat_windows:
        for found in k.toplu_yargi(heat_windows, model, folder, yargi_cfg):
            if found:
                answers.extend(found)
    provisional = []
    for answer in answers:
        if answer['anlasilir'] and answer['puan'] >= cfg['konusma_min_puan']:
            provisional.append({'klip_baslangic_sn': answer['bas_sn'], 'klip_bitis_sn': answer['bit_sn'],
                'konusma_puani': answer['puan'], 'answer': answer})
    provisional = k.aday_birlestir(provisional)[:cfg['konusma_aday_sayisi']]
    # Altyazı aday aramasında kullanılır; yalnız bulunan adayların çevresi Whisper.
    if captions and provisional:
        ranges = [(max(0, a['klip_baslangic_sn']-25), min(vod['sure_sn'], a['klip_bitis_sn']+25)) for a in provisional]
        precise, measurements = whisper_dokum(vod, ranges, dizin, cfg, ff)
        windows = [[s for s in precise if a-25 <= s['bas'] and s['bit'] <= b+25]
                   for a, b in [(p['klip_baslangic_sn'], p['klip_bitis_sn']) for p in provisional]]
        revised = k.toplu_yargi(windows, model, folder, yargi_cfg)
        answers = [found[0] for found in revised if found]
        rows = precise
    else:
        answers = [p['answer'] for p in provisional]
    clips, rejected = [], []
    weight = float(cfg['youtube_heatmap_agirlik'])
    if not 0 <= weight <= 1:
        raise ValueError('youtube_heatmap_agirlik 0–1 olmalı')
    klip_min_sn = max(k.KLIP_MIN_SN, cfg['klip_min_sn'])
    for answer in answers:
        if not answer['anlasilir'] or answer['puan'] < cfg['konusma_min_puan']:
            continue
        bounds = k.sinira_oturt(rows, answer['bas_sn'], answer['bit_sn'], klip_min_sn, cfg['konusma_azami_sn'])
        if not bounds:
            continue
        a, b = bounds
        peak = (a+b)/2
        heat = max((p['value'] for p in info.get('heatmap') or [] if p['start_time'] < b and a < p['end_time']), default=0)
        score = (1-weight)*answer['puan']*10+weight*heat*100 if info.get('heatmap') else answer['puan']*10
        item = {'zirve_sn': peak, 'zirve_dilimleri': [peak], 'zirve_zaman': f'{int(peak)//60}:{int(peak)%60:02d}',
                'klip_baslangic_sn': a, 'klip_bitis_sn': b, 'sure_sn': round(b-a, 3),
                'puan': round(score, 3), 'konusma_puani': answer['puan'], 'konusma_gerekce': answer['gerekce'],
                'konusma_baslik': answer['baslik'], 'konusma_kisa_aciklama': answer.get('kisa_aciklama'),
                'heatmap_puani': heat,
                'baskin': 'konusma', 'kaynaklar': ['altyazi_tarama' if captions else 'whisper_tarama']+(['heatmap'] if heat else []),
                'dokum_metni': ' '.join(s['metin'] for s in rows if a <= s['bas'] and s['bit'] <= b)}
        duplicate = metin_tekrar(item, vod, dizin)
        if duplicate:
            rejected.append({'aralik': [a, b], 'neden': 'cift_kaynak_dokum_eslesmesi', 'paket': duplicate})
            continue
        ses_referanslari(item, measurements)
        clips.append(item)
    return {'vod': vod, 'ayar': cfg, 'klipler': k.son_secim(k.aday_birlestir(clips), cfg),
            'elenen': rejected, 'konusma_surumu': k.SURUM,
            'konusma': {'durum': 'açık', 'dokum': rows, 'altyazi': lang, 'heatmap_tepeleri': peaks,
                'dokum_olcumleri': measurements, 'model_cagrilari': model.olcum, 'cagrilar': model.sayac}}
