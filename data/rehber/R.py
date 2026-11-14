import json,re
files=["minecraft","roblox","diablo-4","path-of-exile-2","genshin-impact"]
# (old,new) plain substring replacements, applied everywhere in order
pairs=[
(" ve burada rakam vermiyorum (kendi bilgim)",""),
(" and I give no figures here (own knowledge)",""),
(" et je ne donne aucun chiffre ici (ma propre connaissance)",""),
(" y aquí no doy cifras (conocimiento propio)",""),
("(kendi bilgim; ","("),("(own knowledge; ","("),("(ma propre connaissance ; ","("),("(conocimiento propio; ","("),
(", kendi bilgim)",")"),(", own knowledge)",")"),(", ma propre connaissance)",")"),(", conocimiento propio)",")"),
(" (kendi bilgim)",""),(" (own knowledge)",""),(" (ma propre connaissance)",""),(" (conocimiento propio)",""),
("satın almadan önce orada bakın, ben lira fiyatını doğrulayamadım.","satın almadan önce orada bakın."),
("check there; I could not verify local prices.","check there."),
("vérifiez-le là ; je n'ai pas pu confirmer les prix locaux.","vérifiez-le là."),
("compruébalo allí; no pude verificar los precios locales.","compruébalo allí."),
("Engeli aşmak için VPN önermiyorum.","Engeli aşmak için VPN kullanılması önerilmez."),
("I do not recommend a VPN to get around the block.","Using a VPN to get around the block is not recommended."),
("Je ne recommande pas un VPN pour contourner le blocage.","Il n'est pas recommandé d'utiliser un VPN pour contourner le blocage."),
("No recomiendo una VPN para saltarse el bloqueo.","No se recomienda usar una VPN para saltarse el bloqueo."),
("kesin tutarı burada yazmıyorum.","kesin tutar için o ekrana bakın."),
("I do not state an exact amount here.","check that screen for the exact amount."),
("je n'indique pas de montant exact ici.","consultez cet écran pour le montant exact."),
("aquí no indico una cifra exacta.","consulta esa pantalla para la cifra exacta."),
("bu konuyu Roblox Yaratıcı Merkezi'nden okuyun, burada rakam vermiyorum","güncel koşullar için Roblox Yaratıcı Merkezi'ne bakın"),
("read about it in the Roblox Creator Hub, I give no figures here","see the Roblox Creator Hub for the current terms"),
("lisez le Creator Hub de Roblox, je ne donne aucun chiffre ici","consultez le Creator Hub de Roblox pour les conditions actuelles"),
("léelo en el Creator Hub de Roblox, aquí no doy cifras","consulta el Creator Hub de Roblox para las condiciones actuales"),
("Türkiye lira fiyatı resmî olarak doğrulanamadı, kesin tutarı","Türkiye lira fiyatı resmî olarak açıklanmadı; kesin tutarı"),
("the Turkish lira price could not be verified officially, so see","the Turkish lira price has not been officially announced, so see"),
("le prix en livres turques n'a pas pu être vérifié officiellement, consultez","le prix en livres turques n'a pas été annoncé officiellement, consultez"),
("el precio en liras turcas no se pudo verificar oficialmente, mira","el precio en liras turcas no se ha anunciado oficialmente, mira"),
("bu yüzden tabloya eklemedim.","bu yüzden tabloda yer almıyor."),
("so I did not add them to the table","so they are not in the table"),
("je ne les ai donc pas mises dans le tableau","elles ne figurent donc pas dans le tableau"),
("así que no las puse en la tabla","así que no figuran en la tabla"),
("yalnızca Macera Rütbesi 10 ve üst sınırlar resmî kaynaklarla doğrulandı, diğer eşikler yaklaşık kendi bilgimdir ve sürümle değişebilir.","Macera Rütbesi 10 ve üst sınırlar resmî kaynaklarda yer alır; diğer eşikler yaklaşıktır ve sürüme göre değişebilir."),
("only Adventure Rank 10 and the upper limits were verified with official sources, and the other thresholds are approximate own knowledge that may change with versions.","Adventure Rank 10 and the upper limits appear in official sources; the other thresholds are approximate and may change with versions."),
("seuls le Rang d'Aventure 10 et les limites supérieures ont été vérifiés avec des sources officielles, les autres seuils sont ma propre connaissance approximative et peuvent changer avec les versions.","le Rang d'Aventure 10 et les limites supérieures figurent dans les sources officielles ; les autres seuils sont approximatifs et peuvent changer avec les versions."),
("solo el Rango de Aventura 10 y los límites superiores se verificaron con fuentes oficiales, y los demás umbrales son conocimiento propio aproximado que puede cambiar con las versiones.","el Rango de Aventura 10 y los límites superiores figuran en fuentes oficiales; los demás umbrales son aproximados y pueden cambiar con las versiones."),
("Türkçe metin desteğini doğrulayamadım. Oyun içi dil menüsünden kontrol edin.","Evet, Türkçe metin desteği vardır (Epic mağaza sayfasına göre 16 metin dili); seslendirme Çince, İngilizce, Japonca ve Korece."),
("I could not verify Turkish text support. Check the in-game language menu.","Yes, Turkish text is supported (16 text languages according to the Epic store page); the voice-over is Chinese, English, Japanese and Korean."),
("Je n'ai pas pu vérifier la prise en charge du texte en turc. Consultez le menu des langues dans le jeu.","Oui, le texte en turc est pris en charge (16 langues de texte d'après la page Epic) ; le doublage est en chinois, anglais, japonais et coréen."),
("No pude verificar el soporte de texto en turco. Revisa el menú de idiomas dentro del juego.","Sí, se admite el texto en turco (16 idiomas de texto según la página de Epic); las voces son en chino, inglés, japonés y coreano."),
]
cells={"Kendi bilgim":"Sürüme göre değişebilir","Own knowledge":"May change with versions","Ma propre connaissance":"Peut changer selon les versions","Conocimiento propio":"Puede cambiar según las versiones",
"Resmî olarak doğrulanmadı":"Resmî olarak açıklanmadı","Not officially verified":"Not officially announced","Non vérifié officiellement":"Non annoncé officiellement","No verificado oficialmente":"No anunciado oficialmente",
"Desene göre Pit 100 civarı; kaynak yok":"Desene göre Pit 100 civarı; resmî değil","Around Pit 100 by the pattern; no source":"Around Pit 100 by the pattern; not official","Autour de la Fosse 100 d'après le motif ; sans source":"Autour de la Fosse 100 d'après le motif ; non officiel","Alrededor del Foso 100 por el patrón; sin fuente":"Alrededor del Foso 100 por el patrón; no oficial"}
def fix(o):
    if isinstance(o,str):
        if o in cells: return cells[o]
        for a,b in pairs: o=o.replace(a,b)
        return o
    if isinstance(o,list): return [fix(x) for x in o]
    if isinstance(o,dict): return {k:fix(v) for k,v in o.items()}
    return o
for f in files:
    p=f+".json"; d=json.load(open(p,encoding="utf-8"))
    d["diller"]=fix(d["diller"])
    s=json.dumps(d,ensure_ascii=False,indent=2)
    open(p,"w",encoding="utf-8",newline="\n").write(s+"\n")
