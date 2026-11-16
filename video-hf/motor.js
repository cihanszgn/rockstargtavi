/* Hyperframes üretim motoru: window.VIDEO verisinden 8 sahne türünü kurar.
   Metin, sayı, süre, görsel ve tema yalnız veriden gelir (tools/video_hf.py üretir); burada haber metni yok.
   Yalnız deterministik kod: Date.now, Math.random, fetch yok. */
(function(){
"use strict";
var V = window.VIDEO, K = V.kelimeler || [], S = V.sahneler, TOT = V.sure;
var P = V.tema.paket, OGE = V.tema.oge || [], H = V.haber || {};
var $ = function(s,r){return (r||document).querySelector(s)};
var NS = "http://www.w3.org/2000/svg";
var tl = gsap.timeline({paused:true});
var cam = $("#cam");
function el(tag,cls,txt,parent){var e=document.createElement(tag);if(cls)e.className=cls;if(txt!==undefined&&txt!==null)e.textContent=txt;if(parent)parent.appendChild(e);return e}
function svgEl(tag,attrs,parent){var e=document.createElementNS(NS,tag);for(var k in attrs)e.setAttribute(k,attrs[k]);if(parent)parent.appendChild(e);return e}
function html(parent,s){parent.innerHTML=s;return parent}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}

/* ---------- paket başına hareket dili ---------- */
function shake(t,a){
  if(P!=="esports"&&P!=="kolaj") return;
  a=a||12;var s=[[a,-a*.6],[-a*.8,a*.5],[a*.5,-a*.35],[0,0]];
  s.forEach(function(p,i){tl.fromTo(cam,{x:i?s[i-1][0]:0,y:i?s[i-1][1]:0},{x:p[0],y:p[1],duration:.035,ease:"none",immediateRender:false},t+i*.035)});
}
/* giris: öğeyi t anında paketin diliyle getirir. o.r eğim, o.sk yatık, o.s büyüklük, o.dx yandan */
function giris(e,t,o){
  o=o||{};var r=o.r||0,sk=P==="esports"?(o.sk===undefined?-6:o.sk):0;
  if(P==="esports"){
    tl.fromTo(e,{scale:o.s||1.45,rotation:r-5,skewX:sk,opacity:0},{scale:1,rotation:r,skewX:sk,opacity:1,duration:.17,ease:"power4.out"},t);
    if(o.sh!==false)shake(t,o.a||12);
  }else if(P==="gazete"){
    tl.fromTo(e,{y:46,scaleY:1.12,rotation:r*.3,opacity:0},{y:0,scaleY:1,rotation:r*.3,opacity:1,duration:.34,ease:"power2.out"},t);
  }else if(P==="neon"){
    tl.fromTo(e,{scale:1.1,opacity:0,x:o.dx?o.dx*.12:0},{scale:1,opacity:1,x:0,duration:.1,ease:"steps(2)"},t);
    tl.fromTo(e,{opacity:.25},{opacity:1,duration:.04,ease:"none",immediateRender:false},t+.1);
    tl.fromTo(e,{opacity:.55},{opacity:1,duration:.04,ease:"none",immediateRender:false},t+.18);
  }else{ /* kolaj: zıplayan çıkartma */
    tl.fromTo(e,{scale:.2,rotation:r-14,opacity:0},{scale:1,rotation:r,opacity:1,duration:.36,ease:"back.out(2.4)"},t);
    if(o.sh!==false&&(o.a||0)>14)shake(t,6);
  }
}
/* yan: yandan kayarak gelen şerit */
function yan(e,t,o){
  o=o||{};var x=o.x===undefined?-1100:o.x,d=o.d||.28;
  if(P==="gazete"){tl.fromTo(e,{opacity:0,x:x>0?60:-60},{opacity:1,x:0,duration:.4,ease:"power2.out"},t);return}
  if(P==="neon"){tl.fromTo(e,{opacity:0,x:x>0?220:-220},{opacity:1,x:0,duration:.22,ease:"power3.out"},t);return}
  if(P==="kolaj"){tl.fromTo(e,{opacity:1,x:x,rotation:(o.r||0)+(x>0?6:-6)},{x:0,rotation:o.r||0,duration:d+.1,ease:"back.out(1.5)"},t);return}
  tl.fromTo(e,{x:x,opacity:1},{x:0,duration:d,ease:"power4.out"},t);
}
function sayac(e,from,to,t,dur){
  /* tl.call/onUpdate seek'te çalışmaz: metin sayısını snap'li textContent animasyonuyla sür */
  e.textContent=String(from);
  tl.fromTo(e,{textContent:from},{textContent:to,duration:dur,ease:"power2.out",snap:{textContent:1}},t);
}
function drift(e,t,dur,a,b){tl.fromTo(e,a,Object.assign({duration:dur,ease:"none"},b),t)}
function vur(e,t){tl.fromTo(e,{scale:1},{scale:1.1,duration:.12,yoyo:true,repeat:1,immediateRender:false,ease:"power2.out"},t)}
function ac(e,t,dur){tl.fromTo(e,{scaleX:0,transformOrigin:"0 50%"},{scaleX:1,duration:dur||.25,ease:"power3.out"},t)}
function sayi(s){var n=parseFloat(String(s).replace(",","."));return isNaN(n)?null:n}

/* ---------- paket başına sahne arka planı: koyu/açık renk değişimi ---------- */
var ARKA = {
  esports:["transparent","color-mix(in srgb,var(--ana-koyu) 78%,transparent)","color-mix(in srgb,var(--bg2) 70%,transparent)","transparent"],
  gazete:["transparent","transparent","transparent","transparent"],
  neon:["transparent","transparent","transparent","transparent"],
  kolaj:["transparent","color-mix(in srgb,var(--bg2) 70%,transparent)","transparent","color-mix(in srgb,var(--bg2) 45%,transparent)"]
}[P];

/* ---------- süs (dekor): yalnız güvenli alanın dışı; veri-dekor işaretli, güvenlik denetimine girmez ---------- */
function dekorKur(sc,i,t0,t1){
  var d=el("div","dk-kat",null,sc);d.style.cssText="position:absolute;left:0;top:0;width:1080px;height:1920px;pointer-events:none;overflow:hidden";
  d.setAttribute("data-dekor","1");
  var dur=t1-t0,v=i%3;
  var a=function(css,cls){var e=el("div",cls||"",null,d);e.style.cssText="position:absolute;"+css;return e};
  if(P==="esports"){
    var bl=a("left:-120px;width:1400px;height:"+(v===0?150:v===1?110:190)+"px;top:"+(v===1?1530:1600)+"px;background:var(--ana);transform:skewY(-4deg);opacity:.9");
    a("left:-120px;width:1400px;height:26px;top:"+(v===1?1500:1572)+"px;background:var(--vurgu);transform:skewY(-4deg)");
    a("right:-60px;top:-40px;width:520px;height:230px;background:var(--vurgu);transform:skewX(-20deg);opacity:.9");
    a("right:150px;top:-40px;width:90px;height:230px;background:var(--ana);transform:skewX(-20deg)");
    drift(bl,t0,dur,{x:-30},{x:30});
  }else if(P==="gazete"){
    a("left:54px;right:54px;top:150px;height:6px;border-top:3px solid var(--murekkep);border-bottom:1px solid var(--murekkep)");
    var ft=a("left:54px;right:54px;top:1530px;height:6px;border-top:3px solid var(--murekkep);border-bottom:1px solid var(--murekkep)");
    var kol=a("left:54px;top:1560px;width:972px;height:330px;display:flex;gap:26px");
    for(var c=0;c<3;c++){var cc=el("div","",null,kol);cc.style.cssText="flex:1;background:repeating-linear-gradient(0deg,var(--murekkep) 0 7px,transparent 7px 19px);opacity:.22;height:"+(c===1?250:300)+"px"}
    a("left:0;top:0;width:1080px;height:150px;background:var(--murekkep)");
  }else if(P==="neon"){
    a("left:0;top:0;width:1080px;height:150px;background:linear-gradient(180deg,rgba(0,0,0,.65),transparent)");
    var gr=a("left:-300px;top:1540px;width:1680px;height:700px;background:linear-gradient(var(--ana-acik) 2px,transparent 2px) 0 0/100% 56px,linear-gradient(90deg,var(--ana-acik) 2px,transparent 2px) 0 0/90px 100%;opacity:.35;transform:perspective(520px) rotateX(62deg);transform-origin:50% 0");
    a("left:0;top:1540px;width:1080px;height:3px;background:var(--ana-acik);box-shadow:0 0 22px var(--ana-acik)");
    drift(gr,t0,dur,{backgroundPosition:"0 0,0 0"},{backgroundPosition:"0 112px,180px 0"});
  }else{
    a("left:-60px;top:-60px;width:380px;height:300px;background:var(--vurgu);border-radius:50%;border:7px solid #111;box-shadow:8px 8px 0 #111");
    a("right:-80px;top:20px;width:260px;height:140px;background:var(--ana);border-radius:70px;border:7px solid #111;transform:rotate(-12deg)");
    var st=a("left:70px;top:"+(v===1?1580:1640)+"px;width:360px;height:96px;background:repeating-linear-gradient(135deg,var(--vurgu) 0 28px,#111 28px 56px);border:7px solid #111;border-radius:20px;box-shadow:9px 9px 0 #111;transform:rotate(-4deg)");
    a("right:70px;top:1700px;width:230px;height:230px;background:var(--vurgu);border:7px solid #111;border-radius:50%;box-shadow:9px 9px 0 #111");
    drift(st,t0,dur,{rotation:-5},{rotation:-2});
  }
  /* akan yazı: oyun adı + tür etiketi (veriden) */
  var yz=(String(H.oyun||"")+" • "+String(H.tur_etiket||"")+" • ").toUpperCase();
  if(V.dil==="zh")yz=String(H.oyun||"")+" • "+String(H.tur_etiket||"")+" • ";
  var rows=P==="gazete"?[]:[[76,96,1],[1745,150,-1]];
  rows.forEach(function(r){
    var e=el("div","dekor-yazi",null,d);e.style.cssText+=";top:"+r[0]+"px;left:0;font-size:"+r[1]+"px;-webkit-text-stroke:3px "+(P==="kolaj"?"#111":"var(--yazi)")+";color:transparent;opacity:.55";
    e.textContent=yz.repeat(8);
    tl.fromTo(e,{x:r[2]>0?0:-900},{x:r[2]>0?-900:0,duration:dur,ease:"none"},t0);
  });
  oyunSusu(d,i,t0,dur);
  return d;
}
/* oyuna özgü süs: oyun tablosundan gelen tek öğe (telifli logo/karakter yok, yalnız biçim) */
function oyunSusu(d,i,t0,dur){
  OGE.forEach(function(o){
    var a=function(css){var e=el("div","",null,d);e.style.cssText="position:absolute;"+css;return e};
    if(o==="piksel"){
      for(var r=0;r<6;r++)for(var c=0;c<=r;c++){a("left:"+(780+c*50-r*0)+"px;top:"+(1560+r*50)+"px;width:50px;height:50px;background:"+((r+c)%2?"var(--vurgu)":"var(--ana)")+";border:3px solid rgba(0,0,0,.45)")}
      var bl=a("left:70px;top:1580px;width:100px;height:100px;background:var(--ana);border:4px solid rgba(0,0,0,.5);box-shadow:inset -14px -14px 0 rgba(0,0,0,.25),inset 14px 14px 0 rgba(255,255,255,.2)");
      drift(bl,t0,dur,{y:0},{y:24});
    }else if(o==="gunbatimi"){
      var s=a("left:290px;top:1500px;width:500px;height:250px;border-radius:250px 250px 0 0;background:linear-gradient(180deg,var(--vurgu),var(--ana));opacity:.95;overflow:hidden");
      for(var k=0;k<5;k++)el("div","",null,s).style.cssText="position:absolute;left:0;right:0;top:"+(120+k*26)+"px;height:"+(5+k*3)+"px;background:var(--bg)";
      drift(s,t0,dur,{y:30},{y:-6});
    }else if(o==="keskin"){
      var t=a("left:0;top:1500px;width:0;height:0;border-left:260px solid var(--ana);border-top:420px solid transparent;opacity:.9");
      a("right:0;top:1520px;width:0;height:0;border-right:200px solid var(--vurgu);border-top:380px solid transparent;opacity:.9");
      var xh=a("left:470px;top:1560px;width:140px;height:140px;border:6px solid var(--vurgu);border-radius:50%;opacity:.8");
      a("left:535px;top:1540px;width:10px;height:180px;background:var(--vurgu);opacity:.8");a("left:450px;top:1625px;width:180px;height:10px;background:var(--vurgu);opacity:.8");
      drift(xh,t0,dur,{rotation:0},{rotation:90});
    }else if(o==="altigen"){
      var hx=a("left:600px;top:1540px;width:250px;height:290px;background:var(--ana-acik);clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%);opacity:.55");
      a("left:690px;top:1610px;width:160px;height:190px;background:var(--vurgu);clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%);opacity:.8");
      drift(hx,t0,dur,{rotation:-10},{rotation:10});
    }
  });
}

/* ---------- geçişler (sahne sınırlarında) ---------- */
function gecisKur(){
  var host=$("#gecis");
  for(var i=1;i<S.length;i++){
    var B=S[i].bas;
    if(P==="esports"){
      var h=i%2===1,dir=i%4<2?1:-1,len=h?1900:2800,cl=[["var(--vurgu)","var(--ana)"],["var(--yazi)","var(--bg)"]][i%2];
      ["b","a"].forEach(function(k,j){
        var e=el("div","",null,host);e.style.background=k==="b"?cl[1]:cl[0];
        e.style.clipPath=h?"polygon(225px 0,100% 0,calc(100% - 225px) 100%,0 100%)":"polygon(0 150px,100% 0,100% calc(100% - 150px),0 100%)";
        var prop=h?"x":"y",A={},M={},O={};A[prop]=-dir*len;M[prop]=0;O[prop]=dir*len;
        tl.fromTo(e,A,Object.assign({duration:.12,ease:"power3.in"},M),B-.17+j*.04);
        tl.fromTo(e,M,Object.assign({duration:.12,ease:"power3.out",immediateRender:false},O),B+.01+j*.04);
      });
    }else if(P==="gazete"){
      var sy=el("div","",null,host);sy.style.background="var(--kagit)";sy.style.borderLeft="14px solid var(--murekkep)";
      tl.fromTo(sy,{x:1100},{x:0,duration:.16,ease:"power2.in"},B-.18);
      tl.fromTo(sy,{x:0},{x:-1100,duration:.2,ease:"power2.out",immediateRender:false},B+.02);
    }else if(P==="neon"){
      var fl=el("div","",null,host);fl.style.background="var(--ana-acik)";fl.style.mixBlendMode="screen";fl.style.opacity=0;
      var ln=el("div","",null,host);ln.style.cssText+=";height:8px;top:0;background:#fff;box-shadow:0 0 40px 14px var(--ana-acik)";
      tl.fromTo(ln,{y:-30},{y:1930,duration:.3,ease:"power2.inOut"},B-.15);
      tl.fromTo(fl,{opacity:0},{opacity:.7,duration:.08,yoyo:true,repeat:1,ease:"none",immediateRender:false},B-.06);
    }else{
      ["var(--vurgu)","#fff","var(--ana)"].forEach(function(c,j){
        var b=el("div","",null,host);b.style.background=c;b.style.borderTop="7px solid #111";b.style.borderBottom="7px solid #111";
        b.style.height="660px";b.style.top=(j*630)+"px";
        tl.fromTo(b,{x:(j%2?1:-1)*1200},{x:0,duration:.14,ease:"power3.in"},B-.2+j*.03);
        tl.fromTo(b,{x:0},{x:(j%2?-1:1)*1200,duration:.14,ease:"power3.out",immediateRender:false},B+.0+j*.03);
      });
    }
  }
}

/* ---------- HUD: ilerleme parçaları, logo ---------- */
function hudKur(){
  var p=$("#prog"),W=972-6*(S.length-1);
  S.forEach(function(s,i){
    var seg=el("i","",null,p);seg.style.width=(W*(s.bit-s.bas)/TOT)+"px";
    var f=el("b","",null,seg);
    tl.fromTo(f,{scaleX:0},{scaleX:1,duration:s.bit-s.bas,ease:"none"},s.bas);
  });
  var lg=$("#logo");lg.innerHTML="";
  ["C","T","R","L"].forEach(function(c){el("kbd","",c,lg)});el("span","","+",lg);el("kbd","","A",lg);el("span","","GAME",lg);
}

/* ---------- altyazı: kelime kelime vurgulu ---------- */
function altyaziKur(){
  var sub=$("#sub");
  (V.parcalar||[]).forEach(function(p){
    var part=el("div","part",null,sub);
    p.satirlar.forEach(function(line){
      var ln=el("div","pl",null,part);
      line.forEach(function(i){var w=el("span","w",K[i].k+(V.dil==="zh"?"":" "),ln);w.setAttribute("data-i",i)});
    });
    tl.set(part,{visibility:"visible"},p.b);
    tl.fromTo(part,{y:16,scale:.94,opacity:0},{y:0,scale:1,opacity:1,duration:.1,ease:"power3.out"},p.b);
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
var KART=["k1","k2","k3"];
/* yuva: henüz görünmemiş öğenin yeri silik çerçeveyle belli olur; kare hiçbir anda boş durmaz */
function yuva(ata){return el("div","yuva",null,ata)}
function ustEtiket(ic,tx,cls){var r=el("div","etiket-satir",null,ic);var c=el("div","chip "+(cls||"c-tur")+" fit",tx,r);return r}
function sahneBaslik(ic,tx,cls){var e=el("div","baslik-pencere k1 d fit",tx,ic);e.setAttribute("data-max","50");return e}

/* ---------- sahne kurucular ---------- */
var B = {};

B.baslik = function(sc,ic,s,id){
  var v=s.veri,t0=s.bas,t1=s.bit;
  ustEtiket(ic,v.ust_etiket||H.tur_etiket||"",(H.tur==="ucretsiz"||H.tur==="indirim"||H.tur==="cikis")?"c-tur":"c-tur");
  var fr=el("div","bk-foto k2"+(V.foto?"":" yok"),null,ic);
  if(V.foto){var im=el("img","",null,fr);im.src=V.foto;im.alt="";drift(im,t0,t1-t0,{scale:1},{scale:1.18})}
  else{var og=el("div","bk-oyun d fit",H.oyun||"",fr);og.setAttribute("data-max","150")}
  if(H.tarih_metin){var td=el("div","bk-tarih b",H.tarih_metin,fr);giris(td,t0+.9,{r:-3,s:1.5,a:6})}
  var bs=el("div","bk-baslik d fit",null,ic);bs.setAttribute("data-max","124");
  var tx=String(v.baslik||""),parts=[],pos=0,vg=(v.vurgu||[]).slice();
  vg.forEach(function(g){var k=tx.indexOf(g.metin,pos);if(k<0)return;if(k>pos)parts.push([tx.slice(pos,k),null]);parts.push([g.metin,g]);pos=k+g.metin.length});
  if(pos<tx.length)parts.push([tx.slice(pos),null]);
  var marks=[];
  parts.forEach(function(q){if(q[1]){var m=el("mark","",q[0].length<=18?q[0].replace(/ /g," "):q[0],bs);marks.push([m,q[1]])}else bs.appendChild(document.createTextNode(q[0]))});
  giris(bs,t0+.05,{r:-1,s:1.3,a:10});
  marks.forEach(function(m){tl.fromTo(m[0],{scale:1},{scale:1.12,duration:.14,yoyo:true,repeat:1,immediateRender:false,ease:"power2.out"},m[1].goster||t0+1.5)});
  if((v.tuslar||[]).length){var tr=el("div","bk-tuslar",null,ic);v.tuslar.forEach(function(k,n){var kb=el("kbd","",k,tr);giris(kb,t0+1.1+n*.12,{s:1.6,a:6,sh:false})})}
  giris(fr,t0,{r:-1,s:1.2,sh:false});
};

B.kaynak = function(sc,ic,s){
  var v=s.veri,t0=s.bas,t1=s.bit;
  var et=el("div","kn-etiket chip c-tur fit",v.etiket||"",ic);
  var bar=el("div","kn-bar k1",null,ic);
  el("b","",v.alan||"",bar);var sl=el("s","",v.yol||"",bar);
  var ad=el("div","kn-ad d k2 fit",v.ad||"",ic);ad.setAttribute("data-max","58");ad.style.padding="14px 26px";
  var al=el("div","kn-alinti k3 fit",v.alinti?("“"+v.alinti+"”"):"",ic);al.setAttribute("data-max","68");
  if(!v.alinti){al.remove();}
  if(v.tarih){var tr=el("div","kn-tarih b",v.tarih,ic)}
  giris(et,t0+.1,{r:-2,s:1.4,a:10});yan(bar,t0+.3,{x:-1000});
  giris(ad,v.goster||t0+.5,{r:-1,s:1.3});
  if(v.alinti)giris(al,(v.goster||t0+.5)+.5,{r:1,s:1.25,a:10});
  if(tr)giris(tr,t0+1.4,{sh:false});
};

B.maddeler = function(sc,ic,s){
  var v=s.veri,t0=s.bas;
  sahneBaslik(ic,v.baslik||"");giris(ic.lastChild,t0+.1,{r:-1,s:1.35,a:10});
  var ls=el("div","mp-liste",null,ic);
  (v.maddeler||[]).forEach(function(m,i){
    var o=el("div","mp-oge "+KART[i%3],null,yuva(ls));
    var n=el("div","mp-no d",String(i+1),o);n.style.background=i%3===1?"var(--bg)":"rgba(0,0,0,.28)";n.style.color="inherit";
    var tx=el("div","mp-metin b fit",m.metin||"",o);tx.setAttribute("data-max","58");
    giris(o,m.goster-.03,{r:(i%2?1:-1)*1.2,s:1.35,a:12});
  });
};

B.yama_fark = function(sc,ic,s){
  var v=s.veri,t0=s.bas;
  sahneBaslik(ic,v.baslik||"");giris(ic.lastChild,t0+.1,{r:-1,s:1.35,a:10});
  var ls=el("div","yf-liste",null,ic);
  (v.satirlar||[]).forEach(function(r,i){
    var o=el("div","yf-satir "+KART[i%3],null,yuva(ls));
    var ad=el("div","yf-ad b fit",r.ad||"",o);ad.setAttribute("data-max","40");
    var dg=el("div","yf-degerler",null,o);
    var es=el("div","yf-eski d",String(r.eski),dg);
    var ok=document.createElementNS(NS,"svg");ok.setAttribute("class","yf-ok");ok.setAttribute("viewBox","0 0 96 64");
    svgEl("path",{d:"M4 24h54V6l34 26-34 26V40H4z",fill:"currentColor"},ok);dg.appendChild(ok);
    var ye=el("div","yf-yeni d",String(r.yeni),dg);
    if(r.birim){el("div","yf-birim b",r.birim,dg)}
    var bar=el("div","yf-bar",null,o);var i1=el("i","e",null,bar),i2=el("i","",null,bar);
    var eo=Math.max(4,Math.min(100,r.eski_oran||0)),yo=Math.max(4,Math.min(100,r.yeni_oran||0));
    i1.style.width=eo+"%";i2.style.width=eo+"%";
    var t=r.goster;
    yan(o,t-.05,{x:-1100});
    var en=sayi(r.eski),yn=sayi(r.yeni);
    giris(es,t+.2,{r:-2,s:1.4,a:8});
    tl.fromTo(ok,{opacity:0,x:-40},{opacity:1,x:0,duration:.16},t+.55);
    giris(ye,t+.8,{r:2,s:1.7,a:16});
    tl.fromTo(i2,{width:eo+"%"},{width:yo+"%",duration:.4,ease:"power4.in"},t+.8);
    tl.fromTo(es,{opacity:.7},{opacity:.45,duration:.2},t+.8);
    if(r.yon==="ayni")ok.style.visibility="hidden";
  });
};

B.platform = function(sc,ic,s){
  var v=s.veri,t0=s.bas;
  sahneBaslik(ic,v.baslik||"");giris(ic.lastChild,t0+.1,{r:-1,s:1.35,a:10});
  var rz=el("div","pf-rozetler",null,ic);
  (v.platformlar||[]).forEach(function(p,i){var r=el("div","pf-rozet d fit "+(p.renk||"diger"),p.ad,rz);r.setAttribute("data-max","56");giris(r,p.goster-.05,{r:(i%2?1:-1)*2,s:1.5,a:10})});
  var sy=el("div","pf-sayilar",null,ic);
  (v.sayilar||[]).forEach(function(q,i){
    var k=el("div","pf-kutu "+KART[(i+1)%3],null,yuva(sy));
    var dg=el("div","pf-deger d fit",String(q.deger),k);dg.setAttribute("data-max","150");
    var et=el("div","pf-etk b fit",q.etiket||"",k);et.setAttribute("data-max","38");
    giris(k,q.goster-.05,{r:(i%2?1:-1)*1.5,s:1.4,a:12});
    if(/^\d{1,5}$/.test(String(q.deger))){sayac(dg,0,parseInt(q.deger,10),q.goster,.6)}
  });
  if(v.not){var nt=el("div","pf-not k1 b fit",v.not,ic);nt.setAttribute("data-max","50");yan(nt,(v.sayilar&&v.sayilar.length?v.sayilar[v.sayilar.length-1].goster:t0+2)+.5,{x:1100})}
};

B.tarih = function(sc,ic,s){
  var v=s.veri,t0=s.bas,t1=s.bit;
  var et=ustEtiket(ic,v.etiket||"",null);giris(et,t0+.1,{r:-2,s:1.4,a:10});
  var ust=el("div","tr-ust",null,ic);
  var bg=el("div","tr-buyuk d",v.gun_bit&&v.gun_bit!==v.gun_bas?(v.gun_bas+"–"+v.gun_bit):String(v.gun_bas),ust);
  var ay=el("div","tr-ay d",v.ay_adi||"",ust);var yl=el("div","tr-yil b",v.yil_metin||"",ust);
  giris(bg,t0+.35,{r:-2,s:1.5,a:16});giris(ay,t0+.6,{r:2,s:1.3,a:8});
  var tk=el("div","tr-takvim k2",null,ic);
  (v.hafta||[]).forEach(function(h){el("span","hf",h,tk)});
  var bos=(v.ilk_haftagunu||0);
  for(var b=0;b<bos;b++)el("span","",null,tk);
  var lo=v.gun_bas,hi=v.gun_bit||v.gun_bas;
  for(var g=1;g<=(v.gun_sayisi||30);g++){var sp=el("span",(g>=lo&&g<=hi)?"on":"",String(g),tk)}
  yan(tk,t0+.8,{x:-1000});
  tk.querySelectorAll("span.on").forEach(function(e,n){tl.fromTo(e,{scale:1},{scale:1.3,duration:.18,yoyo:true,repeat:1,immediateRender:false},t0+1.3+n*.12)});
  if(v.not){var nt=el("div","tr-not k1 b fit",v.not,ic);nt.setAttribute("data-max","46");giris(nt,t0+1.6,{r:1,s:1.3})}
  tl.fromTo(bg,{y:0},{y:-8,duration:2,ease:"sine.inOut",yoyo:true,repeat:1,immediateRender:false},t0+2);
};

B.fiyat = function(sc,ic,s){
  var v=s.veri,t0=s.bas,t1=s.bit,uc=v.durum==="ucretsiz";
  var eti=el("div","fy-etiket d k3 fit",uc?(v.etiket||""):(v.etiket||""),ic);eti.setAttribute("data-max","230");eti.style.padding="6px 24px";
  giris(eti,t0+.15,{r:-2,s:1.6,a:18});
  if(v.eski_fiyat){var es=el("div","fy-eski d",String(v.eski_fiyat),ic);giris(es,(v.goster||t0+.7),{r:-1,s:1.4})}
  if(v.yeni_fiyat){var ye=el("div","fy-yeni d fit",String(v.yeni_fiyat),ic);ye.setAttribute("data-max","230");giris(ye,(v.goster||t0+.7)+.35,{r:1,s:1.6,a:18})}
  if(v.indirim){var ro=el("div","fy-rozet d k1",String(v.indirim),ic);ro.style.top="-10px";giris(ro,(v.goster||t0+.7)+.5,{r:10,s:2.2,a:16})}
  if(v.bitis){var bt=el("div","fy-bitis chip c-alt fit",v.bitis,ic);giris(bt,t0+1.8,{r:-1,s:1.3})}
  var mg=el("div","fy-magaza",null,ic);
  (v.magazalar||[]).forEach(function(m,i){var q=el("span","b "+KART[i%3],m.ad,mg);giris(q,m.goster-.05,{r:(i%2?1:-1)*2,s:1.4,a:6})});
};

B.kapanis = function(sc,ic,s){
  var v=s.veri,t0=s.bas,t1=s.bit;
  var c=el("div","kp-cagri d fit",v.cagri||"",ic);c.setAttribute("data-max","150");
  var a=el("div","kp-alt b fit",v.alt||"",ic);a.setAttribute("data-max","56");
  var ad=el("div","kp-adres d k3",v.adres||"",ic);
  giris(c,t0+.1,{r:-2,s:1.5,a:18});giris(a,t0+.7,{r:1,s:1.3});yan(ad,t0+1.2,{x:1000});
  maskot(sc,t0,t1);
};

/* ---------- maskot: piksel mavi blok; başı alt şeride değmesin diye 40 px içeride, alt orta dolu kalsın ---------- */
function maskot(sc,t0,t1){
  var GOVDE=['..oooooooooooo..','.otttttttttttto.','otffffffffffffto','offffffffffffffo','offffffffffffffo','offffffffffffffo','offffffwwffffffo','offfffwffwfffffo','offfffwwwwfffffo','offfffwffwfffffo','offfffwffwfffffo','offffffffffffffo','osssssssssssssso','.osssssssssssso.','..oooooooooooo..'];
  var BAC={dur:['...offo..offo...','...offo..offo...','...offo..offo...','.owwwwo..owwwwo.','.oggggo..oggggo.'],hav:['...offo..offo...','...offo..offo...','..owwwo..owwwo..','..oggo....oggo..','................']};
  var R={o:'#0A1430',t:'#8fb0ff',f:'var(--ana)',s:'var(--ana-koyu)',w:'#FFFFFF',g:'#9AA8C3'};
  var Hh=12,g=GOVDE.map(function(r){return r.split('')});
  [[4,5],[10,11]].forEach(function(p){[3,4].forEach(function(r){g[r][p[0]]='w';g[r][p[1]]='w'});g[4][p[1]]='o'});
  var svg=document.createElementNS(NS,"svg");svg.setAttribute("id","mas");svg.setAttribute("viewBox","0 0 192 240");svg.setAttribute("data-dekor","1");
  svg.style.cssText="position:absolute;left:718px;top:1000px;width:192px;height:240px";
  sc.appendChild(svg);
  var gb=svgEl("g",{},svg),g1=svgEl("g",{},svg),g2=svgEl("g",{},svg);
  function rects(rows,off,parent){rows.forEach(function(s,r){var c=0;while(c<s.length){var h=s[c],e=c+1;while(e<s.length&&s[e]===h)e++;if(R[h]){svgEl("rect",{x:c*Hh,y:(r+off)*Hh,width:(e-c)*Hh,height:Hh,fill:R[h]},parent)}c=e}})}
  rects(g.map(function(r){return r.join('')}),0,gb);rects(BAC.dur,15,g1);rects(BAC.hav,15,g2);
  svg.style.transformOrigin="50% 100%";
  tl.set(g2,{opacity:0},t0);
  tl.fromTo(svg,{x:500,opacity:1},{x:0,duration:.3,ease:"power3.out"},t0+.4);
  var t=t0+1.2;
  while(t<t1-1.0){
    tl.set(g1,{opacity:0},t);tl.set(g2,{opacity:1},t);
    tl.fromTo(svg,{y:0,scaleY:.86,scaleX:1.1},{y:-70,scaleY:1.06,scaleX:.96,duration:.3,ease:"power2.out",immediateRender:false},t);
    tl.to(svg,{y:0,scaleY:1,scaleX:1,duration:.28,ease:"power2.in"},t+.3);
    tl.set(g1,{opacity:1},t+.58);tl.set(g2,{opacity:0},t+.58);
    t+=1.25;
  }
}

/* ---------- kurulum ---------- */
var host=$("#cam");
S.forEach(function(s,i){
  var sc=document.getElementById("s"+i);
  sc.style.background=ARKA[i%ARKA.length];
  dekorKur(sc,i,s.bas,s.bit);
  var ic=el("div","ic",null,sc);
  (B[s.sablon]||B.kapanis)(sc,ic,s,i);
  /* her sahnenin ilk karesi boş olmasın: içerik 0. saniyede görünür kalır (giriş animasyonları fromTo) */
});
hudKur();altyaziKur();gecisKur();

/* ---------- sığdırma: uzun metin küçülür, taşma olmaz ---------- */
function sigdir(){
  document.querySelectorAll(".fit").forEach(function(e){
    var mx=parseFloat(e.getAttribute("data-max"))||parseFloat(getComputedStyle(e).fontSize);
    var fs=mx;e.style.fontSize=fs+"px";
    var sc=e.closest(".sc");
    /* gizli sahnede ölçü sıfır olur: ölçüm için sahneyi geçici görünür yap */
    var rest=null;
    if(sc&&getComputedStyle(sc).visibility==="hidden"||(sc&&sc.offsetParent===null&&getComputedStyle(sc).display==="none")){rest=sc.style.cssText;sc.style.visibility="visible";sc.style.display="block"}
    var n=0;
    /* dar satır aralığında harf kutusu satırdan taşar (scrollHeight ≈ clientHeight+%8): gerçek taşma en az yarım satırdır */
    while(n++<80&&fs>20&&(e.scrollHeight>e.clientHeight+Math.max(3,fs*.3)||e.scrollWidth>e.clientWidth+1)){fs-=Math.max(1,Math.round(fs*.04));e.style.fontSize=fs+"px"}
    if(rest!==null)sc.style.cssText=rest;
  });
  /* altyazı: her parçanın en uzun satırı 800 px'e sığsın (güvenli alan x 70–930); kelime vurgusu %10 büyür */
  document.querySelectorAll("#sub .part").forEach(function(pt){
    var ls=pt.querySelectorAll(".pl"),mx=0;
    ls.forEach(function(l){l.style.fontSize="";mx=Math.max(mx,l.offsetWidth)});
    if(mx>800){var f=Math.floor(74*800/mx);ls.forEach(function(l){l.style.fontSize=f+"px"})}
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
