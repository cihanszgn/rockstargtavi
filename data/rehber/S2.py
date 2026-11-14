import json,re
pat=re.compile(r"(doğrulan|doğrulay|bu rehberde|okuduğum|resmî olarak (?:doğ|açık)|emin değil|bulamad|ulaşamad|verified|could not|not confirm|confirm|vérifi|n'ai|pude|encontr|resmî sayfa|resmî olarak)",re.I)
for g in ["minecraft","roblox","diablo-4","path-of-exile-2","genshin-impact"]:
    d=json.load(open(g+".json",encoding="utf-8"))
    def walk(o,path):
        if isinstance(o,str):
            for s in re.split(r"(?<=[.;])\s+",o):
                if pat.search(s) and re.search(r"\.tr",path): print(g,path,"::",s)
        elif isinstance(o,list):
            for i,x in enumerate(o): walk(x,path+f"[{i}]")
        elif isinstance(o,dict):
            for k,x in o.items(): walk(x,path+"."+k)
    walk(d["diller"],"")
