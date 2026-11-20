/* Hyperframes modern editoryal video motoru (v6): window.VIDEO verisinden 8 sahne türünü kurar.
   Yalnız deterministik kod: Date.now, Math.random, fetch yok.
   Görsel öncelikli, temiz, üst üste binmeyen tipografi; kayan süs yazısı, kesikli boş kafes ve yapay efekt yok. */
(function(){
"use strict";
var V = window.VIDEO, K = V.kelimeler || [], S = V.sahneler, TOT = V.sure;
var P = V.tema.paket, H = V.haber || {};
var $ = function(s,r){return (r||document).querySelector(s)};
var NS = "http://www.w3.org/2000/svg";
var tl = gsap.timeline({paused:true});
function el(tag,cls,txt,parent){var e=document.createElement(tag);if(cls)e.className=cls;if(txt!==undefined&&txt!==null)e.textContent=txt;if(parent)parent.appendChild(e);return e}
function svgEl(tag,attrs,parent){var e=document.createElementNS(NS,tag);for(var k in attrs)e.setAttribute(k,attrs[k]);if(parent)parent.appendChild(e);return e}
function ON(e){e.setAttribute("data-on","1");return e}
function F(e,mx,mn){e.className+=" fit";e.setAttribute("data-max",String(mx));if(mn)e.setAttribute("data-min",String(mn));return e}

/* ---------- sade, akıcı editoryal hareket dili ---------- */
function giris(e,t,o){
  o=o||{};var dy=o.y===undefined?26:o.y,d=o.d||.34;
  tl.fromTo(e,{y:dy,opacity:0},{y:0,opacity:1,duration:d,ease:"power3.out"},Math.max(0,t));
}
function kancaGiris(e,t,o){
  /* İlk karede (t=0) tam görünür (opacity:1), hafif akıcı oturuş */
  o=o||{};var dy=o.y===undefined?10:o.y,d=o.d||.24;
  tl.fromTo(e,{y:dy,opacity:1},{y:0,opacity:1,duration:d,ease:"power3.out"},t);
}
function sayac(e,from,to,t,dur){
  e.textContent=String(from);
  tl.fromTo(e,{textContent:from},{textContent:to,duration:dur,ease:"power2.out",snap:{textContent:1}},Math.max(0,t));
}

/* ---------- tüm video boyunca sinematik oyun arka planı ---------- */
function zeminKur(){
  var z=$("#zemin");
  if(V.foto){
    var im=el("img","zm-foto",null,z);im.src=V.foto;im.alt="";
    tl.fromTo(im,{scale:1.06,x:0},{scale:1.15,x:-18,duration:TOT,ease:"none"},0);
  }
  el("div","zm-perde",null,z);
}

/* ---------- yumuşak sinematik geçişler (sahne sınırlarında) ---------- */
function gecisKur(){
  var host=$("#gecis");
  for(var i=1;i<S.length;i++){
    var B=S[i].bas;
    var fl=el("div","",null,host);
    fl.style.cssText="background:#05060b;opacity:0";
    tl.fromTo(fl,{opacity:0},{opacity:.55,duration:.11,ease:"power2.in"},Math.max(0,B-.11));
    tl.to(fl,{opacity:0,duration:.16,ease:"power2.out"},B);
  }
}

/* ---------- HUD: ince ilerleme çubuğu ve sade marka imzası ---------- */
function hudKur(){
  var p=$("#prog"),W=972-8*(S.length-1);
  S.forEach(function(s){
    var seg=el("i","",null,p);seg.style.width=(W*(s.bit-s.bas)/TOT)+"px";
    var f=el("b","",null,seg);
    tl.fromTo(f,{scaleX:0},{scaleX:1,duration:s.bit-s.bas,ease:"none"},s.bas);
  });
  var lg=$("#logo");lg.innerHTML="";
  el("i","",null,lg);
  el("span","","CTRL+A GAME",lg);
}

/* ---------- altyazı: tek temiz koyu hap içinde, kelime kelime vurgulu ---------- */
function altyaziKur(){
  var sub=$("#sub");
  (V.parcalar||[]).forEach(function(p){
    var part=el("div","part",null,sub);
    var kutu=el("div","part-kutu",null,part);
    p.satirlar.forEach(function(line){
      var ln=el("div","pl",null,kutu);
      line.forEach(function(i){var w=el("span","w",K[i].k+(V.dil==="zh"?"":" "),ln);w.setAttribute("data-i",i)});
    });
    tl.set(part,{visibility:"visible"},p.b);
    tl.fromTo(part,{y:10,opacity:0},{y:0,opacity:1,duration:.12,ease:"power2.out"},p.b);
    tl.set(part,{visibility:"hidden"},p.bitis);
    var idx=[];p.satirlar.forEach(function(l){l.forEach(function(i){idx.push(i)})});
    idx.forEach(function(i,n){
      var w=part.querySelector('[data-i="'+i+'"]');
      var nxt=n+1<idx.length?K[idx[n+1]].b:p.bitis;
      tl.set(w,{className:"w on"},K[i].b);
      tl.set(w,{className:"w"},Math.max(K[i].b+.01,Math.min(nxt,p.bitis)-.001));
    });
  });
}

/* ---------- ortak parçalar ---------- */
function yuva(ata){return el("div","yuva",null,ata)}
function sahneVitrin(ic,baslik,etiket,t0,t1,kisa){
  var v=ON(el("div","sahne-vitrin"+(kisa?" kisa":""),null,ic));
  if(V.foto){
    var im=el("img","",null,v);im.src=V.foto;im.alt="";
    tl.fromTo(im,{scale:1.04},{scale:1.11,duration:Math.max(.5,t1-t0),ease:"none"},t0);
  }
  var ust=el("div","sv-ust",null,v);
  if(etiket)el("div","chip c-tur",etiket,ust);
  if(H.oyun&&String(baslik||"").toLowerCase()!==String(H.oyun).toLowerCase())el("div","sv-oyun",H.oyun,ust);
  if(baslik)F(el("div","sh d",baslik,v),56,28);
  giris(v,t0,{y:18,d:.3});
  return v;
}

/* kelime kelime başlık + sade alt çizgi vurgusu */
function kelimeKur(host,tx,vg){
  var parts=[],pos=0,words=[],groups=[],zh=V.dil==="zh";
  (vg||[]).slice().forEach(function(g){var k=tx.indexOf(g.metin,pos);if(k<0)return;if(k>pos)parts.push([tx.slice(pos,k),null]);parts.push([g.metin,g]);pos=k+g.metin.length});
  if(pos<tx.length)parts.push([tx.slice(pos),null]);
  function bol(str){if(zh){var a=[];for(var i=0;i<str.length;i+=2)a.push(str.slice(i,i+2));return a}return str.split(/\s+/).filter(Boolean)}
  parts.forEach(function(q){
    var ws=bol(q[0]),par=host,hl=null;
    if(!ws.length)return;
    if(q[1]){par=el("span","bg",null,host);hl=el("i","hl",null,par);groups.push({wrap:par,hl:hl,g:q[1]})}
    ws.forEach(function(w,i){
      var sp=el("span","bw",w,par);words.push(sp);
      if(!zh&&i<ws.length-1)par.appendChild(document.createTextNode(" "));
    });
    if(!zh)host.appendChild(document.createTextNode(" "));
  });
  return {words:words,groups:groups};
}
function kelimeGiris(kw,t0,gap){
  kw.words.forEach(function(w,i){
    tl.fromTo(w,{y:10,opacity:1},{y:0,opacity:1,duration:.2,ease:"power3.out"},t0+i*gap);
  });
  kw.groups.forEach(function(g,gi){
    var erken=t0+.22+gi*.14;
    var tg=g.g.goster?Math.min(g.g.goster,erken+.18):erken;
    tl.set(g.wrap,{className:"bg on"},tg);
    tl.fromTo(g.hl,{scaleX:0},{scaleX:1,duration:.22,ease:"power3.out"},tg);
  });
}

/* ---------- 8 sahne kurucu ---------- */
var B = {};

B.baslik = function(sc,ic,s){
  var v=s.veri,t0=s.bas,t1=s.bit,dur=Math.max(.5,t1-t0);
  ic.classList.add("t-baslik");
  var bg=el("div","bk-bg"+(V.foto_oran&&V.foto_oran>=2.15?" genis":""));sc.insertBefore(bg,sc.firstChild);
  if(V.foto){
    var im=el("img","bk-img",null,bg);im.src=V.foto;im.alt="";
    if(!V.foto_oran){
      im.addEventListener("load",function(){if(im.naturalHeight&&im.naturalWidth/im.naturalHeight>=2.15)bg.classList.add("genis")});
    }
    tl.fromTo(im,{scale:1.02},{scale:1.10,duration:dur,ease:"none"},t0);
    el("div","bk-ov ov-perde",null,bg);
  }else{
    el("div","bk-ov ov-doku",null,bg);
  }
  /* Üst tek sade meta şeridi: kategori rozeti + tarih + oyun adı (görselin ortasını hiç kapatmaz) */
  var ust=ON(el("div","bk-ust",null,ic));
  var sol=el("div","bk-sol",null,ust);
  var et=el("div","chip c-tur",H.tur_etiket||v.ust_etiket||"",sol);
  if(H.tarih_metin)el("div","bk-tarih",H.tarih_metin,sol);
  var dm=el("div","bk-damga",H.oyun||v.ust_etiket||"",ust);
  kancaGiris(et,t0,{y:6,d:.18});
  kancaGiris(dm,t0,{y:6,d:.18});
  /* Alt vurucu başlık bloğu */
  var alt=ON(el("div","bk-alt-blok",null,ic));
  var cz=el("div","bk-cizgi",null,alt);
  tl.fromTo(cz,{scaleX:0,transformOrigin:"0 50%"},{scaleX:1,duration:.28,ease:"power3.out"},t0+.04);
  var bs=ON(F(el("div","bk-bas d",null,alt),122,96));
  var kw=kelimeKur(bs,String(v.baslik||""),v.vurgu);
  kelimeGiris(kw,t0,Math.min(.04,.20/Math.max(1,kw.words.length)));
};

B.kaynak = function(sc,ic,s){
  var v=s.veri,t0=s.bas,t1=s.bit;
  sahneVitrin(ic,v.etiket||"",H.tur_etiket||"",t0,t1,true);
  var kart=ON(el("div","kn-kart",null,ic));
  var ust=el("div","kn-ust-satir",null,kart);
  F(el("div","kn-ad d",v.ad||"",ust),50,28);
  if(v.alan||v.yol){
    var bar=el("div","kn-bar",null,ust);
    el("b","",v.alan||"",bar);
    if(v.yol)el("s","",v.yol,bar);
  }
  if(v.alinti){
    F(el("div","kn-alinti","“"+v.alinti+"”",kart),50,30);
  }
  if(v.tarih){
    el("div","kn-tarih",v.tarih,kart);
  }
  giris(kart,t0+.14,{y:24,d:.36});
};

B.maddeler = function(sc,ic,s){
  var v=s.veri,t0=s.bas,t1=s.bit,L=v.maddeler||[],n=Math.max(1,L.length);
  sahneVitrin(ic,v.baslik||"",H.tur_etiket||"",t0,t1,true);
  var ls=el("div","mp-liste n"+n,null,ic);
  var mx=[0,66,54,48,42,38,34][Math.min(n,6)];
  L.forEach(function(m,i){
    var o=ON(el("div","mp-oge",null,yuva(ls)));
    el("div","mp-no",(i+1<10?"0":"")+(i+1),o);
    F(el("div","mp-metin b",m.metin||"",o),mx,26);
    var t=i===0?Math.min(m.goster||t0+.15,t0+.25):Math.max(t0+.18,(m.goster||t0+.3*i)-.04);
    giris(o,t,{y:22,d:.32});
  });
};

B.yama_fark = function(sc,ic,s){
  var v=s.veri,t0=s.bas,t1=s.bit,L=v.satirlar||[],n=Math.max(1,L.length);
  sahneVitrin(ic,v.baslik||"",H.tur_etiket||"",t0,t1,true);
  var ls=el("div","yf-liste n"+n,null,ic);
  L.forEach(function(r,i){
    var o=ON(el("div","yf-satir",null,yuva(ls)));
    F(el("div","yf-ad",r.ad||"",o),30,20);
    var dg=el("div","yf-degerler",null,o);
    var es=el("div","yf-eski d",String(r.eski),dg);
    var ok=document.createElementNS(NS,"svg");ok.setAttribute("class","yf-ok");ok.setAttribute("viewBox","0 0 96 64");
    svgEl("path",{d:"M6 27h56V10l28 22-28 22V37H6z",fill:"currentColor"},ok);dg.appendChild(ok);
    var ye=F(el("div","yf-yeni d",String(r.yeni),dg),n>=3?96:132,56);
    if(r.birim)el("div","yf-birim b",r.birim,dg);
    var bar=el("div","yf-bar",null,o);var i1=el("i","e",null,bar),i2=el("i","",null,bar);
    var eo=Math.max(4,Math.min(100,(r.eski_oran||0)*(r.eski_oran<=1?100:1)));
    var yo=Math.max(4,Math.min(100,(r.yeni_oran||0)*(r.yeni_oran<=1?100:1)));
    i1.style.width=eo+"%";i2.style.width=eo+"%";
    var t=i===0?Math.min(r.goster||t0+.15,t0+.25):Math.max(t0+.18,(r.goster||t0+.3*i)-.04);
    giris(o,t,{y:22,d:.3});
    tl.fromTo(i2,{width:eo+"%"},{width:yo+"%",duration:.38,ease:"power3.out"},t+.24);
    if(r.yon==="ayni")ok.style.visibility="hidden";
  });
};

B.platform = function(sc,ic,s){
  var v=s.veri,t0=s.bas,t1=s.bit,PL=v.platformlar||[],SY=v.sayilar||[],solo=!SY.length;
  sahneVitrin(ic,v.baslik||"",H.tur_etiket||"",t0,t1,true);
  if(PL.length){
    var rz=ON(el("div","pf-rozetler"+(solo?" solo n"+PL.length:""),null,ic));
    PL.forEach(function(p,i){
      var r=F(el("div","pf-rozet "+(p.renk||"diger"),p.ad,rz),solo?66:32,22);
      giris(r,Math.max(t0+.12,(p.goster||t0+.16+i*.12)-.04),{y:18,d:.28});
    });
  }
  if(SY.length){
    var sy=el("div","pf-sayilar n"+SY.length,null,ic);
    SY.forEach(function(q,i){
      var k=ON(el("div","pf-kutu",null,yuva(sy)));
      var dg=F(el("div","pf-deger d",String(q.deger),k),SY.length===1?190:136,64);
      F(el("div","pf-etk b",q.etiket||"",k),SY.length===1?50:42,22);
      var t=i===0?Math.min(q.goster||t0+.18,t0+.28):Math.max(t0+.18,(q.goster||t0+.3*i)-.04);
      giris(k,t,{y:22,d:.3});
      if(/^\d{1,5}$/.test(String(q.deger)))sayac(dg,0,parseInt(q.deger,10),t+.05,.45);
    });
  }
  if(v.not){
    var nt=ON(F(el("div","pf-not b",v.not,ic),34,22));
    giris(nt,(SY.length?SY[SY.length-1].goster:(PL.length?PL[PL.length-1].goster:t0+.7))+.16,{y:18,d:.3});
  }
};

B.tarih = function(sc,ic,s){
  var v=s.veri,t0=s.bas,t1=s.bit;
  sahneVitrin(ic,v.etiket||"",H.tur_etiket||"",t0,t1,true);
  var kart=ON(el("div","tr-kart",null,ic));
  var ust=el("div","tr-ust",null,kart);
  var dt=v.gun_bit&&v.gun_bit!==v.gun_bas?(v.gun_bas+"–"+v.gun_bit):String(v.gun_bas);
  F(el("div","tr-buyuk d",dt,ust),146,80);
  var yn=el("div","tr-yan",null,ust);
  F(el("div","tr-ay d",v.ay_adi||"",yn),66,32);
  el("div","tr-yil",v.yil_metin||"",yn);
  var tk=el("div","tr-takvim",null,kart);
  (v.hafta||[]).forEach(function(h){el("span","hf",h,tk)});
  var bos=(v.ilk_haftagunu||0);
  for(var b=0;b<bos;b++)el("span","",null,tk);
  var lo=v.gun_bas,hi=v.gun_bit||v.gun_bas;
  for(var g=1;g<=(v.gun_sayisi||30);g++){el("span",(g>=lo&&g<=hi)?"on":"",String(g),tk)}
  if(v.not){
    F(el("div","tr-not b",v.not,kart),34,22);
  }
  giris(kart,t0+.14,{y:24,d:.36});
  tk.querySelectorAll("span.on").forEach(function(e,n){
    tl.fromTo(e,{scale:.88},{scale:1.08,duration:.22,yoyo:true,repeat:1,ease:"power2.out",immediateRender:false},t0+.55+n*.08);
  });
};

B.fiyat = function(sc,ic,s){
  var v=s.veri,t0=s.bas,t1=s.bit;
  sahneVitrin(ic,H.oyun||v.etiket||"",H.tur_etiket||"",t0,t1,true);
  var kart=ON(el("div","fy-kart",null,ic));
  if(v.indirim)el("div","fy-rozet d",String(v.indirim),kart);
  if(v.etiket)F(el("div","fy-etiket d",v.etiket,kart),118,56);
  if(v.eski_fiyat)el("div","fy-eski d",String(v.eski_fiyat),kart);
  if(v.yeni_fiyat)F(el("div","fy-yeni d",String(v.yeni_fiyat),kart),158,72);
  if(v.bitis)F(el("div","fy-bitis chip c-alt",v.bitis,kart),28,20);
  if((v.magazalar||[]).length){
    var mg=el("div","fy-magaza",null,kart);
    v.magazalar.forEach(function(m){el("span","",m.ad,mg)});
  }
  giris(kart,t0+.14,{y:24,d:.36});
};

B.kapanis = function(sc,ic,s){
  var v=s.veri,t0=s.bas,t1=s.bit;
  var vt=sahneVitrin(ic,H.oyun||"",H.tur_etiket||"",t0,t1,false);
  vt.classList.add("kp-vitrin");
  var kart=ON(el("div","kp-kart",null,ic));
  var ust=el("div","kp-ust",null,kart);
  F(el("div","kp-cagri d",v.cagri||"",ust),86,44);
  if(v.alt)F(el("div","kp-alt b",v.alt,ust),38,24);
  var sat=el("div","kp-sat",null,kart);
  var sol=el("div","kp-sol",null,sat);
  el("div","kp-site b","CTRL+A GAME",sol);
  if(v.adres)F(el("div","kp-adres d",v.adres,sol),38,24);
  giris(kart,t0+.14,{y:24,d:.36});
};

/* ---------- kurulum ---------- */
zeminKur();
S.forEach(function(s,i){
  var sc=document.getElementById("s"+i);
  var ic=el("div","ic t-"+s.sablon,null,sc);
  (B[s.sablon]||B.kapanis)(sc,ic,s,i);
});
hudKur();altyaziKur();gecisKur();

/* ---------- sığdırma: taşma olmaz ---------- */
function sigdir(){
  document.querySelectorAll(".fit").forEach(function(e){
    var mx=parseFloat(e.getAttribute("data-max"))||parseFloat(getComputedStyle(e).fontSize);
    var mn=parseFloat(e.getAttribute("data-min"))||20;
    var fs=mx;e.style.fontSize=fs+"px";
    var sc=e.closest(".sc");
    var rest=null;
    if(sc&&(getComputedStyle(sc).visibility==="hidden"||(sc.offsetParent===null&&getComputedStyle(sc).display==="none"))){rest=sc.style.cssText;sc.style.visibility="visible";sc.style.display="block"}
    var n=0;
    var bw=e.querySelectorAll(".bw");
    var tasma=function(){
      if(bw.length){var h=0,w=0;bw.forEach(function(b){var t=0,l=0,n=b;while(n&&n!==e){t+=n.offsetTop;l+=n.offsetLeft;n=n.offsetParent}h=Math.max(h,t+b.offsetHeight);w=Math.max(w,l+b.offsetWidth)});return h>e.clientHeight+Math.max(3,fs*.14)||w>e.clientWidth+1}
      return e.scrollHeight>e.clientHeight+Math.max(3,fs*.14)||e.scrollWidth>e.clientWidth+1};
    while(n++<120&&fs>mn&&tasma()){fs=Math.max(mn,fs-Math.max(1,Math.round(fs*.03)));e.style.fontSize=fs+"px"}
    if(rest!==null)sc.style.cssText=rest;
  });
  document.querySelectorAll("#sub .part").forEach(function(pt){
    var ls=pt.querySelectorAll(".pl"),mx=0;
    ls.forEach(function(l){l.style.fontSize="";mx=Math.max(mx,l.offsetWidth)});
    if(mx>800){var f=Math.floor(50*800/mx);ls.forEach(function(l){l.style.fontSize=f+"px"})}
  });
  window.__sigdi=true;
}
window.__sigdir=sigdir;
if(document.fonts&&document.fonts.ready){document.fonts.ready.then(sigdir)}else{sigdir()}
sigdir();

window.__timelines=window.__timelines||{};
window.__timelines["main"]=tl;
tl.seek(0);
})();
