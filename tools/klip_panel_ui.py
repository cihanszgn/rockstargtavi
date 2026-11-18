"""Onay panelinin (klip_yayin.py sayfa) sabit CSS ve tarayıcı betiği. Yalnız düz metin; girilen değerler buraya GİRMEZ.
Sunucudan gelen her metin sayfaya `textContent`/`value` ile yazılır ya da sunucuda kaçışlanmış HTML parçası olarak gelir."""

CSS = """
:root{--bg:#f6f6f4;--fg:#1c1c1a;--kart:#fff;--cizgi:#d9d9d4;--vurgu:#0a6cff;--kirmizi:#b3261e;--yesil:#1b7a3a;--sari:#8a6100;--gri:#6b6b66}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--fg:#ecebe6;--kart:#1f1f1d;--cizgi:#3a3a36;--vurgu:#6aa4ff;--kirmizi:#ff8b82;--yesil:#6fd08a;--sari:#e0b64a;--gri:#a3a39c}}
[hidden]{display:none!important}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto}
h1{font-size:1.4rem} h2{margin-top:2rem;border-bottom:1px solid var(--cizgi);padding-bottom:.3rem;font-size:1.15rem}
.kart{background:var(--kart);border:1px solid var(--cizgi);border-radius:10px;padding:14px;margin:14px 0}
.kart.kufur{border-color:var(--kirmizi);border-width:2px}
.kart h3{margin:0 0 6px;font-size:1.05rem;overflow-wrap:anywhere}
.no{display:inline-block;min-width:1.8em;text-align:center;background:var(--vurgu);color:#fff;border-radius:6px;padding:0 6px;margin-right:6px}
.govde{display:flex;gap:16px;flex-wrap:wrap} .govde video{background:#000;max-width:100%;border-radius:6px}
.yan{flex:1;min-width:260px;overflow-wrap:anywhere} table{border-collapse:collapse} th{text-align:left;padding:1px 10px 1px 0;color:var(--sari);font-weight:600}
pre{white-space:pre-wrap;word-break:break-word;background:var(--bg);padding:8px;border-radius:6px;margin:4px 0}
.uyari{color:var(--kirmizi);padding-left:1.2em;margin:.4em 0} .durum{margin:2px 0 8px;font-weight:600}
.durum.yayinda,.durum.paylasildi{color:var(--yesil)} .durum.dustu,.durum.bekle{color:var(--kirmizi)}
.kr{display:flex;gap:10px;flex-wrap:wrap} .kr img{width:280px;max-width:100%;border-radius:4px} figure{margin:0}
a{color:var(--vurgu)} .ipucu{color:var(--sari);font-size:.92rem} code{background:var(--bg);padding:1px 5px;border-radius:4px}
.kufurrozet,.ellerozet,.platrozet{display:inline-block;font-size:.75rem;font-weight:700;border-radius:4px;padding:1px 6px;margin-left:6px;vertical-align:middle}
.kufurrozet{background:var(--kirmizi);color:var(--bg)} .ellerozet{background:var(--sari);color:var(--bg)} .platrozet{background:var(--gri);color:var(--bg)}
.ozet{position:sticky;top:0;z-index:5;background:var(--kart);border:1px solid var(--cizgi);border-radius:8px;padding:8px 12px;font-size:1.05rem}
.not{color:var(--sari)}
.suzgec{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0}
.suzgec button[aria-pressed=true]{background:var(--vurgu);color:#fff;border-color:var(--vurgu)}
.suzgec select{font:inherit;min-height:44px;padding:6px 10px;border-radius:8px;border:1px solid var(--cizgi);background:var(--kart);color:var(--fg);max-width:100%}
.islem{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}
button{font:inherit;font-weight:600;min-height:44px;padding:8px 18px;border-radius:8px;border:1px solid var(--cizgi);background:var(--kart);color:var(--fg);cursor:pointer}
button.onayla,button.birincil{background:var(--yesil);color:var(--bg);border-color:var(--yesil)}
button.tehlike{border-color:var(--kirmizi);color:var(--kirmizi)}
button[disabled]{opacity:.55;cursor:wait}
.kart[data-onayli=evet] .onayla,.kart[data-onayli=hayir] .geri{display:none}
.kart[data-onayli=evet]{border-left:6px solid var(--yesil)}
.hata{color:var(--kirmizi);font-weight:600;border:1px solid var(--kirmizi);border-radius:6px;padding:6px 10px;margin:8px 0 0;overflow-wrap:anywhere}
.tamam{color:var(--yesil);font-weight:600;border:1px solid var(--yesil);border-radius:6px;padding:6px 10px;margin:8px 0 0;overflow-wrap:anywhere}
.krsec{position:relative;display:block;cursor:pointer;border:3px solid transparent;border-radius:6px}
.krsec input{position:absolute;top:8px;left:8px;width:22px;height:22px;z-index:1}
.krsec span{position:absolute;right:8px;top:6px;background:var(--vurgu);color:#fff;border-radius:6px;padding:0 8px}
.krsec:has(input:checked){border-color:var(--yesil)}
.duzenle{margin-top:12px;border-top:1px dashed var(--cizgi);padding-top:10px}
.duzenle fieldset{border:1px solid var(--cizgi);border-radius:8px;margin:10px 0;padding:10px 12px;min-width:0}
.duzenle legend{font-weight:700;padding:0 6px}
.duzenle label{display:block;margin:10px 0 2px;font-weight:600}
.duzenle input[type=text],.duzenle input[type=number],.duzenle textarea,.duzenle select{box-sizing:border-box;width:100%;font:inherit;min-height:44px;padding:8px 10px;border-radius:8px;border:1px solid var(--cizgi);background:var(--bg);color:var(--fg)}
.duzenle textarea{min-height:140px;resize:vertical}
.duzenle label.anahtar{display:flex;align-items:center;gap:10px;font-weight:600;min-height:44px;margin:4px 0}
.duzenle label.anahtar input{width:24px;height:24px;flex:none}
.say{font-size:.88rem;color:var(--gri);font-weight:400;margin-left:8px}
.say.asti{color:var(--kirmizi);font-weight:700}
.sayaclar{display:flex;gap:6px 16px;flex-wrap:wrap;font-size:.92rem;margin:8px 0;color:var(--gri)}
.sayaclar .asti{color:var(--kirmizi);font-weight:700}
.sayaclar .kapali{opacity:.45;text-decoration:line-through}
.kaydir{display:flex;gap:6px;align-items:center;flex-wrap:nowrap}
.kaydir input{text-align:center;flex:1;min-width:0}
.kaydir button{flex:none;min-width:52px;padding:8px 10px}
.kutu4{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
.kesim{border:1px solid var(--sari);border-radius:6px;padding:6px 10px;margin:8px 0;color:var(--sari);font-weight:600}
.kesim[data-durum=hata]{border-color:var(--kirmizi);color:var(--kirmizi)}
.kucuk{color:var(--gri);font-size:.88rem}
details summary{cursor:pointer;min-height:32px}
@media (max-width:600px){body{padding:10px} .islem button,.suzgec button{flex:1 1 100%} .govde video{height:auto;width:100%} .kutu4{grid-template-columns:repeat(2,1fr)} .kaydir button{min-width:48px}}
"""

BETIK = """<script>
(function(){
  'use strict';
  var EMOJI=/[\\u{1F000}-\\u{1FAFF}\\u2600-\\u27BF\\uFE0F\\u200D\\u20E3]/gu;
  function belirtec(){var m=document.querySelector('meta[name=belirtec]');return m?m.content:'';}
  function oku(r){return r.json().catch(function(){return {ok:false,mesaj:'Sunucu yanıtı anlaşılamadı (kod '+r.status+').'};});}
  var KOPUK={ok:false,mesaj:'Sunucuya ulaşılamadı: Onay Sayfası penceresi kapanmış olabilir.'};
  function gonder(yol,govde){
    return fetch(yol,{method:'POST',headers:{'Content-Type':'application/json','X-Belirtec':belirtec()},body:JSON.stringify(govde)}).then(oku,function(){return KOPUK;});
  }
  function getirJson(yol){return fetch(yol,{headers:{'X-Belirtec':belirtec()}}).then(oku,function(){return KOPUK;});}
  function getirMetin(yol){
    return fetch(yol,{headers:{'X-Belirtec':belirtec()}}).then(function(r){return r.ok?r.text():null;},function(){return null;});
  }
  function bolumde(kutu){return kutu.closest('fieldset')||kutu.closest('.kart');}
  function mesaj(bolum,tur,metin){
    var h=bolum.querySelector('.hata'),t=bolum.querySelector('.tamam');
    if(h){h.textContent=tur==='hata'?(metin||''):'';h.hidden=!(tur==='hata'&&metin);}
    if(t){t.textContent=tur==='tamam'?(metin||''):'';t.hidden=!(tur==='tamam'&&metin);}
  }
  function ozetYaz(o){
    if(!o)return;
    Object.keys(o).forEach(function(k){var e=document.getElementById('s-'+k);if(e)e.textContent=o[k];});
  }
  function durumYaz(kart,d){
    if(!d)return;
    kart.classList.remove(kart.dataset.sinif);kart.classList.add(d.sinif);kart.dataset.sinif=d.sinif;
    kart.dataset.onayli=d.onayli?'evet':'hayir';
    var p=kart.querySelector('p.durum');p.className='durum '+d.sinif;p.querySelector('.etiket').textContent=d.etiket;
  }

  // ---- süzgeç
  var suz={tur:'hepsi',yayinci:''};
  function suzgecUygula(){
    var say=0,top=0;
    document.querySelectorAll('.kart').forEach(function(k){
      top++;
      var ok=(suz.tur==='hepsi')||(suz.tur==='onayli'&&k.dataset.onayli==='evet')||(suz.tur==='kufur'&&k.dataset.kufur==='1');
      if(ok&&suz.yayinci&&k.dataset.yayinci!==suz.yayinci)ok=false;
      k.hidden=!ok;if(ok)say++;
    });
    var s=document.getElementById('suz-sayi');if(s)s.textContent=say+' / '+top+' gösteriliyor';
    document.querySelectorAll('.suzgec button[data-suz]').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.suz===suz.tur?'true':'false');});
  }

  // ---- karakter sayaçları (sunucudaki denetimin aynası; asıl denetim kaydederken sunucuda)
  function uz(s){return Array.from(s).length;}
  function etiketler(ham){
    var out=[],g={};
    ham.split(/[\\s,;]+/).forEach(function(p){
      p=p.replace(/^#+/,'').replace(/[^\\p{L}\\p{N}_]/gu,'');
      if(p&&!g[p.toLowerCase()]){g[p.toLowerCase()]=1;out.push('#'+p);}
    });
    return out;
  }
  function bolumAlan(b,ad){var e=b.querySelector('[name='+ad+']');return e?e.value:'';}
  function metinSayilari(kart){
    var m=kart.querySelector('.duzenle fieldset.metin');if(!m)return;
    var klip=kart.dataset.tur==='klip';
    var baslik=bolumAlan(m,'baslik').replace(/\\s*\\n\\s*/g,' ').trim();
    var ac=bolumAlan(m,'aciklama').trim();
    var et=etiketler(bolumAlan(m,'etiketler')).join(' ');
    var ig=uz([baslik,ac,et].filter(Boolean).join('\\n\\n').replace(EMOJI,''));
    var ya=[ac,et].filter(Boolean).join('\\n\\n');if(klip)ya=(ya+' #Shorts').trim();
    ya=ya.replace(/[<>]/g,'').replace(EMOJI,'');
    var yb=baslik.replace(/[<>]/g,'').replace(EMOJI,'').trim();
    var lim=m.dataset;
    var gi=m.querySelector('[name=p_instagram]');
    var igAcik=!!(klip&&gi&&gi.checked), ytAcik=m.querySelector('[name=p_youtube]').checked;
    function yaz(sinif,deger,sinir,acik){
      var e=m.querySelector('.'+sinif);if(!e)return;
      e.querySelector('b').textContent=deger;
      e.classList.toggle('asti',acik&&deger>sinir);e.classList.toggle('kapali',!acik);
    }
    yaz('s-ig',ig,+lim.igAcik,igAcik);
    yaz('s-ytb',uz(yb),+lim.ytBaslik,ytAcik);
    yaz('s-yta',uz(ya),+lim.ytAcik,ytAcik);
    var sb=m.querySelector('.say-baslik');if(sb)sb.textContent=uz(baslik)+' karakter';
  }
  function videoSayilari(kart){
    var v=kart.querySelector('.duzenle fieldset.video');if(!v)return;
    var yazi=bolumAlan(v,'aciklama_metni').trim();
    var e=v.querySelector('.say-yazi');
    if(e){e.textContent=uz(yazi)+' / '+v.dataset.yaziSinir;e.classList.toggle('asti',uz(yazi)>+v.dataset.yaziSinir);}
    var s=v.querySelector('.sure-yeni');
    if(s){
      var bas=parseFloat(bolumAlan(v,'bas_kaydir'))||0,son=parseFloat(bolumAlan(v,'son_kaydir'))||0;
      var b0=parseFloat(v.dataset.bas),b1=parseFloat(v.dataset.son);
      if(isFinite(b0)&&isFinite(b1)){s.textContent='Şu an '+b0.toFixed(1)+'–'+b1.toFixed(1)+' sn ('+(b1-b0).toFixed(1)+' sn) → yeni '+(b0+bas).toFixed(1)+'–'+(b1+son).toFixed(1)+' sn ('+((b1+son)-(b0+bas)).toFixed(1)+' sn)';}
    }
  }
  function sayaclar(kart){metinSayilari(kart);videoSayilari(kart);}

  // ---- kart yenileme (sunucunun kaçışladığı parça)
  function kartYerlestir(eski,html){
    var t=document.createElement('template');t.innerHTML=html;
    var yeni=t.content.firstElementChild;if(!yeni)return eski;
    eski.replaceWith(yeni);sayaclar(yeni);suzgecUygula();kesimIzle();return yeni;
  }
  function kartYenile(kart){
    var ac=kart.querySelector('.duzenle')&&!kart.querySelector('.duzenle').hidden;
    return getirMetin('/kart/'+encodeURIComponent(kart.dataset.no)+(ac?'?ac=1':'')).then(function(h){return h?kartYerlestir(kart,h):kart;});
  }

  // ---- yeniden kesim yoklaması
  var zamanlayici=null;
  function kesimIzle(){
    var aktif=document.querySelector('.kesim[data-durum=kuyrukta],.kesim[data-durum=kesiliyor]');
    if(aktif&&!zamanlayici){zamanlayici=setInterval(yokla,3000);}
    if(!aktif&&zamanlayici){clearInterval(zamanlayici);zamanlayici=null;}
  }
  function yokla(){
    getirJson('/api/durum').then(function(d){
      if(!d||!d.ok)return;
      document.querySelectorAll('.kart').forEach(function(k){
        var e=k.querySelector('.kesim');if(!e)return;
        var s=(d.kesimler||{})[k.dataset.no];
        if(!s){if(e.dataset.durum==='kuyrukta'||e.dataset.durum==='kesiliyor')kartYenile(k);return;}
        if(s.durum!==e.dataset.durum){
          if(s.durum==='bitti'||s.durum==='hata'){kartYenile(k);}
          else{e.dataset.durum=s.durum;e.textContent=s.mesaj;}
        }else if(e.dataset.durum==='kuyrukta'||e.dataset.durum==='kesiliyor'){e.textContent=s.mesaj;}
      });
      kesimIzle();
    });
  }

  function dugmeler(kart,kapat){kart.querySelectorAll('button').forEach(function(b){b.disabled=kapat;});}
  function onayliUyari(kart,ne){
    if(kart.dataset.onayli!=='evet')return true;
    return window.confirm('Bu öğe onaylı. '+ne+' onayı DÜŞÜRÜR; sonra yeniden onaylaman gerekir. Devam edilsin mi?');
  }

  document.addEventListener('click',function(e){
    var d=e.target.closest('button');if(!d)return;
    var kart=d.closest('.kart');
    if(d.dataset.suz){suz.tur=d.dataset.suz;suzgecUygula();return;}
    if(!kart)return;
    var bolum=bolumde(d);
    if(d.classList.contains('onayla')||d.classList.contains('geri')){
      var onay=d.classList.contains('onayla');var govde={no:kart.dataset.no};
      mesaj(kart,'hata','');
      if(onay){
        if(kart.dataset.tur==='derleme'){
          var sec=kart.querySelector('input[type=radio]:checked');
          if(!sec){mesaj(kart,'hata','Önce bir küçük resim seç (resme tıkla), sonra onayla.');return;}
          govde.kucuk_resim=parseInt(sec.value,10);
        }
        if(kart.dataset.kufur==='1'&&!window.confirm('Bu kartta küfür uyarısı var. Dinledin ve yine de onaylansın mı?'))return;
      }else if((kart.dataset.sinif==='yayinda'||kart.dataset.sinif==='paylasildi')&&
               !window.confirm('Bu klip medya sunucusuna yüklenmiş ya da paylaşılmış. Onayı geri alınsın mı? (Sunucudaki dosya ve paylaşılmış gönderi silinmez.)')){return;}
      dugmeler(kart,true);
      gonder(onay?'/api/onayla':'/api/geri-al',govde).then(function(r){
        dugmeler(kart,false);
        durumYaz(kart,r.durum);ozetYaz(r.ozet);suzgecUygula();
        if(!r.ok)mesaj(kart,'hata',r.mesaj||'Bilinmeyen hata.');
      });
      return;
    }
    if(d.classList.contains('duzen-ac')){
      var p=kart.querySelector('.duzenle');p.hidden=!p.hidden;
      d.textContent=p.hidden?'Düzenle':'Düzenlemeyi kapat';d.setAttribute('aria-expanded',p.hidden?'false':'true');
      if(!p.hidden)sayaclar(kart);return;
    }
    if(d.classList.contains('adim')){
      var inp=d.parentElement.querySelector('input');
      var yeni=Math.round(((parseFloat(inp.value)||0)+parseFloat(d.dataset.adim))*100)/100;
      inp.value=String(yeni);sayaclar(kart);return;
    }
    if(d.classList.contains('metin-kaydet')){
      mesaj(bolum,'hata','');
      var pl={instagram:false,youtube:false};
      var gi=bolum.querySelector('[name=p_instagram]');if(gi)pl.instagram=gi.checked;pl.youtube=bolum.querySelector('[name=p_youtube]').checked;
      if(!onayliUyari(kart,'Metni ya da platformu değiştirmek'))return;
      dugmeler(kart,true);
      gonder('/api/metin-kaydet',{no:kart.dataset.no,baslik:bolumAlan(bolum,'baslik'),aciklama:bolumAlan(bolum,'aciklama'),
                                 etiketler:bolumAlan(bolum,'etiketler'),platformlar:pl}).then(function(r){
        dugmeler(kart,false);
        if(!r.ok){mesaj(bolum,'hata',r.mesaj||'Bilinmeyen hata.');return;}
        ozetYaz(r.ozet);
        var yeni=r.kart?kartYerlestir(kart,r.kart):kart;
        var b=yeni.querySelector('.duzenle fieldset.metin');if(b)mesaj(b,'tamam',[r.mesaj].concat(r.uyarilar||[]).join(' '));
      });
      return;
    }
    if(d.classList.contains('metin-sifirla')){
      mesaj(bolum,'hata','');
      if(!window.confirm('Elle yazdığın başlık, açıklama ve etiketler silinir; otomatik metne dönülür. Emin misin?'))return;
      if(!onayliUyari(kart,'Metni sıfırlamak'))return;
      dugmeler(kart,true);
      gonder('/api/metin-sifirla',{no:kart.dataset.no}).then(function(r){
        dugmeler(kart,false);
        if(!r.ok){mesaj(bolum,'hata',r.mesaj||'Bilinmeyen hata.');return;}
        ozetYaz(r.ozet);
        var yeni=r.kart?kartYerlestir(kart,r.kart):kart;
        var b=yeni.querySelector('.duzenle fieldset.metin');if(b)mesaj(b,'tamam',r.mesaj);
      });
      return;
    }
    if(d.classList.contains('kesim-baslat')){
      mesaj(bolum,'hata','');
      var g={no:kart.dataset.no};
      ['aciklama_metni','oyun','yayinci_adi'].forEach(function(a){var el=bolum.querySelector('[name='+a+']');if(el&&el.value!==el.dataset.ilk)g[a]=el.value;});
      var bas=parseFloat(bolumAlan(bolum,'bas_kaydir'))||0,son=parseFloat(bolumAlan(bolum,'son_kaydir'))||0;
      if(bas)g.bas_kaydir=bas;if(son)g.son_kaydir=son;
      var du=bolum.querySelector('[name=duzen]');if(du&&du.value!==du.dataset.ilk)g.duzen=du.value;
      var kk=['kx','ky','kw','kh'].map(function(a){return bolumAlan(bolum,a).trim();});
      var ilk=bolum.querySelector('.kutu4').dataset.ilk||'';
      if(kk.join(',')!==ilk&&kk.join('')!==''){
        if(kk.some(function(x){return x==='';})){mesaj(bolum,'hata','Kamera kutusunun dört değerini de gir (x, y, genişlik, yükseklik).');return;}
        g.kamera_kutu=kk;
      }
      if(Object.keys(g).length===1){mesaj(bolum,'hata','Değiştirdiğin bir şey yok.');return;}
      if(g.aciklama_metni!==undefined&&uz(g.aciklama_metni.trim())>+bolum.dataset.yaziSinir){mesaj(bolum,'hata','Video üstü açıklama çok uzun.');return;}
      if(!onayliUyari(kart,'Videoyu yeniden kesmek'))return;
      dugmeler(kart,true);
      gonder('/api/kesim',g).then(function(r){
        dugmeler(kart,false);
        if(!r.ok){mesaj(bolum,'hata',r.mesaj||'Bilinmeyen hata.');return;}
        ozetYaz(r.ozet);
        if(r.kart)kartYerlestir(kart,r.kart);
      });
      return;
    }
  });
  document.addEventListener('input',function(e){var k=e.target.closest('.kart');if(k)sayaclar(k);});
  document.addEventListener('change',function(e){
    var t=e.target;
    if(t.id==='suz-yayinci'){suz.yayinci=t.value;suzgecUygula();return;}
    var k=t.closest('.kart');if(!k)return;
    if(t.type==='checkbox')sayaclar(k);
    if(t.type==='radio'&&k.dataset.tur==='derleme'&&t.name.indexOf('kr')===0){
      if(k.dataset.onayli==='evet'&&!window.confirm('Küçük resmi değiştirmek onayı DÜŞÜRÜR; sonra yeniden onaylaman gerekir. Devam edilsin mi?')){
        kartYenile(k);return;
      }
      gonder('/api/kucuk-resim',{no:k.dataset.no,kucuk_resim:parseInt(t.value,10)}).then(function(r){
        if(!r.ok){mesaj(k,'hata',r.mesaj||'Bilinmeyen hata.');return;}
        ozetYaz(r.ozet);
        if(r.onay_dustu&&r.kart)kartYerlestir(k,r.kart);
      });
    }
  });
  document.addEventListener('DOMContentLoaded',function(){suzgecUygula();kesimIzle();});
})();
</script>"""
