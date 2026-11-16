"""Modelin elle yazdığı çevirileri veriyle birleştiren geçici yardımcı."""
import copy
import json
import pathlib

def uygula(dil, metin):
    p = pathlib.Path('data/icerik.json')
    veri = json.loads(p.read_text(encoding='utf-8'))
    satirlar = metin.strip().splitlines()
    assert len(satirlar) == len(veri), (dil, len(satirlar))
    for x, satir in zip(veri, satirlar):
        baslik, ozet, metin = satir.split('¦')
        t = dict(baslik=baslik, ozet=ozet, metin=metin.replace('\\n', '\n'))
        if 'etiketler' in x['diller']['en']:
            t['etiketler'] = copy.deepcopy(x['diller']['en']['etiketler'])
        x['diller'][dil] = t
    p.write_text(json.dumps(veri, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
