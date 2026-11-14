import json,re,sys
pat=re.compile(r"(kendi bilgim|kendi bilgimdir|Kendi bilgim|rakam vermiyorum|yazmıyorum|vermiyorum|önermiyorum|okuduğum|\w+(?:dım|dim|dum|düm|tım|tim|tum|tüm)\b|bu rehberde doğ|own knowledge|Own knowledge|\bI (?:could|did|do|give|state|recommend|have|am)\b|sources I|je n'ai|je ne |\bje\b|j'ai|[Mm]a propre|[Cc]onocimiento propio|\bno pude|\bno he |\bno doy|\bno recomiendo|aquí no)")
ign=re.compile(r"^(Do I|Puis-je|Dois-je|Can I|What if|How do I|Quelle|Comment)")
for g in ["minecraft","roblox","diablo-4","path-of-exile-2","genshin-impact"]:
    d=json.load(open(g+".json",encoding="utf-8"))
    def walk(o,path):
        if isinstance(o,str):
            if pat.search(o):
                for s in re.split(r"(?<=[.;:!?])\s+",o):
                    if pat.search(s) and not ign.match(s): print(g,path,"::",s)
        elif isinstance(o,list):
            for i,x in enumerate(o): walk(x,path+f"[{i}]")
        elif isinstance(o,dict):
            for k,x in o.items(): walk(x,path+"."+k)
    walk(d["diller"],"")
