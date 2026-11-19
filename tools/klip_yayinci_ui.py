"""Onay panelinin "Yayıncılar" sekmesi: sabit HTML iskeleti, CSS ve tarayıcı betiği (klip_yayin.py sayfa).
Sunucudan gelen her değer (yayıncı adı, kanal, başlık...) sayfaya yalnız `textContent`/`value` ile yazılır; HTML olarak eklenmez."""

SEKMELER = ('<nav class=sekmeler role=group aria-label="Bölümler">'
            '<button type=button data-sekme=klipler aria-pressed=true>Klipler</button>'
            '<button type=button data-sekme=yayincilar aria-pressed=false>Yayıncılar</button></nav>'
            '<div id=bildirim class=tamam hidden><span id=bildirim-metin></span> <button type=button id=bildirim-yenile class=birincil>Klip listesini yenile</button></div>'
            '<div class=ykart id=yayinla-bar><div class=islem><button type=button id=y-yayinla class=birincil>Onaylananları yayınla</button>'
            '<span id=y-yayinla-sayi class=kucuk></span></div>'
            '<p class=kucuk>Onaylı ve henüz yüklenmemiş klipleri sunucuya yükler, kaydı GitHub\'a gönderir. Yalnız sen basınca çalışır; '
            'çalışırken onay/düzenleme yapma.</p><div id=y-yayinla-durum class=kesim hidden></div></div>')

BOLUM = """<section id=sekme-yayincilar hidden>
<h2>Yayıncılar</h2>
<p class=not>Klip aranacak yayıncılar. Buradan ekleyebilir, kapatabilir, adını düzeltebilir, listeden çıkarabilirsin; dosya düzenlemen gerekmez.
Çıkardığın yayıncının mevcut klipleri silinmez. <b>Bu pencere (Onay Sayfası) kapanırsa çalışan klip çıkarma işi de durur.</b></p>
<div id=y-is class=kesim hidden></div>
<div id=y-liste><p class=kucuk>Yükleniyor…</p></div>
<div id=y-genel-mesaj class=hata hidden></div>
<div class=ykart id=y-ekle>
<h3>Yayıncı ekle</h3>
<p class=kucuk>Yayıncının adını ya da bağlantısını tek kutuya yaz: Kick adı (Hype), kick.com bağlantısı ya da YouTube bağlantısı / @tanıtıcı.
Doğrularım, listeye eklerim ve son yayınından klip çıkarmayı kendim başlatırım. Çıkan klipler onay listesine düşer; onaylamadıkça hiçbir şey paylaşılmaz.</p>
<label for=y-girdi><b>Yayıncı</b></label>
<input type=text id=y-girdi autocomplete=off spellcheck=false maxlength=200 placeholder="Hype   ·   kick.com/hype   ·   youtube.com/@kanal">
<div class=islem><button type=button id=y-ekle-cikar class=birincil>Ekle ve klip çıkar</button><button type=button id=y-kontrol>Yalnız kontrol et</button></div>
<div id=y-ekle-mesaj class=hata hidden></div>
<div id=y-onizleme hidden>
<h3>Bulunan kanal</h3>
<div id=y-onizleme-satir></div>
<label for=y-ad><b>Ad</b> (listede görünen)</label>
<input type=text id=y-ad maxlength=60 autocomplete=off>
<label for=y-kisa><b>Kısa ad</b> (videonun üstüne yazılan; boş bırakırsan adın ilk kelimesi)</label>
<input type=text id=y-kisa maxlength=60 autocomplete=off>
<div class=islem><button type=button id=y-onayla class=birincil>Yalnız listeye ekle</button><button type=button id=y-vazgec>Vazgeç</button></div>
</div>
</div>
<details class=ykart id=y-kaldirilan><summary><b>Kaldırılanlar</b> <span id=y-kaldirilan-say class=kucuk></span></summary><div id=y-kaldirilan-liste></div></details>
</section>"""

CSS = """
.sekmeler{display:flex;gap:8px;margin:10px 0 4px}
.sekmeler button[aria-pressed=true]{background:var(--vurgu);color:#fff;border-color:var(--vurgu)}
.ykart{background:var(--kart);border:1px solid var(--cizgi);border-radius:10px;padding:12px 14px;margin:10px 0}
.ykart.kapali{opacity:.8;border-style:dashed}
.ykart h3{margin:0 0 4px;font-size:1.05rem;overflow-wrap:anywhere}
.ykart p{margin:3px 0;overflow-wrap:anywhere}
.ykart .rozet{display:inline-block;font-size:.75rem;font-weight:700;border-radius:4px;padding:1px 6px;margin-left:6px;background:var(--gri);color:var(--bg);vertical-align:middle}
.ykart label.anahtar{display:flex;align-items:center;gap:10px;font-weight:600;min-height:44px}
.ykart label.anahtar input{width:24px;height:24px;flex:none}
.ykart input[type=text],#y-ekle input[type=text]{box-sizing:border-box;width:100%;font:inherit;min-height:44px;padding:8px 10px;border-radius:8px;border:1px solid var(--cizgi);background:var(--bg);color:var(--fg)}
.ykart label,#y-ekle label{display:block;margin:10px 0 2px}
.ykart label.anahtar{margin:2px 0}
.birincil{background:var(--vurgu);color:#fff;border-color:var(--vurgu)}
.tehlike{color:var(--kirmizi);border-color:var(--kirmizi)}
#y-onizleme{margin-top:12px;border-top:1px dashed var(--cizgi);padding-top:8px}
#y-onizleme-satir p{margin:3px 0;overflow-wrap:anywhere}
"""

BETIK = r"""<script>
(function(){
  'use strict';
  // Betik <head> içinde yüklenir: sayfa gövdesi oluşmadan çalışırsa hiçbir düğme bağlanmaz (sessiz arıza). Gövdeyi bekle.
  function basla(){
  var kok=document.getElementById('sekme-yayincilar');if(!kok)return;
  function belirtec(){var m=document.querySelector('meta[name=belirtec]');return m?m.content:'';}
  function oku(r){return r.json().catch(function(){return {ok:false,mesaj:'Sunucu yanıtı anlaşılamadı (kod '+r.status+').'};});}
  var KOPUK={ok:false,mesaj:'Sunucuya ulaşılamadı: Onay Sayfası penceresi kapanmış olabilir.'};
  function gonder(yol,govde){
    return fetch(yol,{method:'POST',headers:{'Content-Type':'application/json','X-Belirtec':belirtec()},body:JSON.stringify(govde)}).then(oku,function(){return KOPUK;});
  }
  function al(yol){return fetch(yol,{headers:{'X-Belirtec':belirtec()}}).then(oku,function(){return KOPUK;});}
  function $(id){return document.getElementById(id);}
  function el(t,sinif,metin){var e=document.createElement(t);if(sinif)e.className=sinif;if(metin!=null)e.textContent=metin;return e;}
  function dugme(metin,sinif,fn){var b=el('button',sinif,metin);b.type='button';b.addEventListener('click',function(){fn(b);});return b;}
  function mesaj(kutu,metin){kutu.textContent=metin||'';kutu.hidden=!metin;}
  var KICK_RE=/^[A-Za-z0-9_-]{1,40}$/,UC_RE=/^UC[A-Za-z0-9_-]{22}$/;

  // ---- sekmeler
  var aktif='klipler',zamanlayici=null,onceki='';
  function sekme(ad){
    aktif=ad;
    ['klipler','yayincilar'].forEach(function(s){var e=$('sekme-'+s);if(e)e.hidden=(s!==ad);});
    document.querySelectorAll('.sekmeler button[data-sekme]').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.sekme===ad?'true':'false');});
    try{history.replaceState(null,'','#'+ad);}catch(e){}
    if(ad==='yayincilar'){yukle();isDurumu();}
  }
  document.querySelectorAll('.sekmeler button[data-sekme]').forEach(function(b){b.addEventListener('click',function(){sekme(b.dataset.sekme);});});

  // ---- liste
  var calisiyor=false;
  function yukle(){
    return al('/api/yayinci/liste').then(function(v){
      if(!v.ok){mesaj($('y-genel-mesaj'),v.mesaj||'Liste okunamadı.');return;}
      mesaj($('y-genel-mesaj'),'');
      ciz(v);
    });
  }
  function baglanti(metin,adres){var a=el('a',null,metin);a.href=adres;a.target='_blank';a.rel='noopener noreferrer';return a;}
  function satir(){return el('p');}
  function kartCiz(y,kaldirilmis){
    var k=el('div','ykart'+(y.etkin||kaldirilmis?'':' kapali'));
    var h=el('h3',null,y.ad);
    if(y.kisa_ad&&y.kisa_ad!==y.ad)h.appendChild(el('span','say','videoda: '+y.kisa_ad));
    if(!y.etkin&&!kaldirilmis)h.appendChild(el('span','rozet','kapalı'));
    k.appendChild(h);
    var p;
    if(y.platform==='kick'){
      p=satir();p.appendChild(document.createTextNode('Kick: '));
      if(KICK_RE.test(y.kanal))p.appendChild(baglanti('kick.com/'+y.kanal,'https://kick.com/'+y.kanal));else p.appendChild(document.createTextNode(y.kanal));
      k.appendChild(p);
    }else{
      k.appendChild(el('p','kucuk','Kick kanalı yok: yalnız YouTube kaynağı.'));
    }
    y.youtube.forEach(function(c){
      p=satir();p.appendChild(document.createTextNode('YouTube: '));
      var ad=c.tanitici?'@'+c.tanitici:c.kanal_id;
      if(UC_RE.test(c.kanal_id))p.appendChild(baglanti(ad,'https://www.youtube.com/channel/'+c.kanal_id));else p.appendChild(document.createTextNode(ad));
      if(!c.etkin)p.appendChild(el('span','rozet','kapalı'));
      k.appendChild(p);
    });
    k.appendChild(el('p','kucuk','Kayıtlı klip: '+y.klip_sayisi));
    if(kaldirilmis){
      if(y.kaldirildi)k.appendChild(el('p','kucuk','Kaldırıldı: '+y.kaldirildi.replace('T',' ').replace('Z',' UTC')));
      var isl=el('div','islem');
      isl.appendChild(dugme('Geri getir','birincil',function(b){islem(b,k,'/api/yayinci/geri-getir',{anahtar:y.anahtar});}));
      k.appendChild(isl);
      k.appendChild(el('div','hata')).hidden=true;
      return k;
    }
    var ac=el('label','anahtar'),cb=el('input');cb.type='checkbox';cb.checked=y.etkin;
    ac.appendChild(cb);ac.appendChild(document.createTextNode('Açık (klip aranır)'));
    cb.addEventListener('change',function(){cb.disabled=true;islem(cb,k,'/api/yayinci/duzenle',{anahtar:y.anahtar,etkin:cb.checked});});
    k.appendChild(ac);
    var is=el('div','islem'),form=null;
    is.appendChild(dugme('Düzenle',null,function(){
      if(form){form.remove();form=null;return;}
      form=duzenleFormu(y,k,function(){form.remove();form=null;});k.insertBefore(form,hata);
    }));
    var cb2=dugme('Son yayından klip çıkar','cikar',function(b){
      if(!y.etkin){mesaj(hata,'Bu yayıncı kapalı; önce "Açık" anahtarını aç.');return;}
      var ok=window.confirm(y.ad+' için son yayından klip çıkarılsın mı?\n\nBu işlem UZUN sürer (2 saatlik yayın yaklaşık 30-35 dakika) ve Claude kotanı harcar.\nBilgisayarı ve Onay Sayfası penceresini kapatma: pencere kapanırsa iş de durur.');
      if(ok)islem(b,k,'/api/yayinci/klip-cikar',{anahtar:y.anahtar},isDurumu);
    });
    cb2.disabled=calisiyor;
    is.appendChild(cb2);
    is.appendChild(dugme('Kaldır','tehlike',function(b){
      if(window.confirm(y.ad+' listeden çıkarılsın mı?\n\nMevcut klipleri silinmez; istersen "Kaldırılanlar"dan geri getirirsin.'))islem(b,k,'/api/yayinci/kaldir',{anahtar:y.anahtar});
    }));
    k.appendChild(is);
    var hata=el('div','hata');hata.hidden=true;k.appendChild(hata);
    return k;
  }
  function islem(dg,kart,yol,govde,sonra){
    var hata=kart.querySelector(':scope > .hata');dg.disabled=true;
    gonder(yol,govde).then(function(v){
      dg.disabled=false;
      if(!v.ok){if(hata)mesaj(hata,v.mesaj||'İşlem başarısız.');yukle();return;}
      if(sonra)sonra();
      yukle();
    });
  }
  function duzenleFormu(y,kart,kapat){
    var f=el('div','yduzenle');
    var l1=el('label',null,'Ad');l1.htmlFor='';var ad=el('input');ad.type='text';ad.maxLength=60;ad.value=y.ad;
    var l2=el('label',null,'Kısa ad (videoda yazan)');var kisa=el('input');kisa.type='text';kisa.maxLength=60;kisa.value=y.kisa_ad;
    f.appendChild(l1);f.appendChild(ad);f.appendChild(l2);f.appendChild(kisa);
    var yts=[];
    y.youtube.forEach(function(c){
      var lb=el('label','anahtar'),c1=el('input');c1.type='checkbox';c1.checked=c.etkin;
      lb.appendChild(c1);lb.appendChild(document.createTextNode('YouTube '+(c.tanitici?'@'+c.tanitici:c.kanal_id)+' açık'));
      f.appendChild(lb);yts.push({kanal_id:c.kanal_id,kutu:c1});
    });
    var m=el('div','hata');m.hidden=true;
    var is=el('div','islem');
    is.appendChild(dugme('Kaydet','birincil',function(b){
      b.disabled=true;
      gonder('/api/yayinci/duzenle',{anahtar:y.anahtar,ad:ad.value,kisa_ad:kisa.value,
        youtube:yts.map(function(x){return {kanal_id:x.kanal_id,etkin:x.kutu.checked};})}).then(function(v){
        b.disabled=false;
        if(!v.ok){mesaj(m,v.mesaj||'Kaydedilemedi.');return;}
        kapat();yukle();
      });
    }));
    is.appendChild(dugme('Vazgeç',null,kapat));
    f.appendChild(m);f.appendChild(is);
    return f;
  }
  function ciz(v){
    var kutu=$('y-liste');kutu.textContent='';
    if(!v.yayincilar.length)kutu.appendChild(el('p',null,'Henüz yayıncı yok. Aşağıdan ekle.'));
    v.yayincilar.forEach(function(y){kutu.appendChild(kartCiz(y,false));});
    var kk=$('y-kaldirilan-liste');kk.textContent='';
    v.kaldirilanlar.forEach(function(y){kk.appendChild(kartCiz(y,true));});
    $('y-kaldirilan-say').textContent='('+v.kaldirilanlar.length+')';
    $('y-kaldirilan').hidden=!v.kaldirilanlar.length;
  }

  // ---- iş durumu
  function sureYaz(sn){var d=Math.floor(sn/60),s=sn%60;return d+' dk '+(s<10?'0':'')+s+' sn';}
  var DURUM={calisiyor:'çalışıyor…',bitti:'bitti',hata:'başarısız',iptal:'iptal edildi'};
  function bildirimGoster(n){
    $('bildirim-metin').textContent=n+' yeni klip hazır ve onay listesinde bekliyor.';$('bildirim').hidden=false;
  }
  $('bildirim-yenile').addEventListener('click',function(){location.hash='#klipler';location.reload();});
  function isDurumu(){
    return al('/api/yayinci/is').then(function(v){
      var kutu=$('y-is');
      if(!v.ok||v.durum==='yok'){kutu.hidden=true;calisiyor=false;onceki='';ciftBekle();return;}
      calisiyor=v.durum==='calisiyor';
      kutu.hidden=false;kutu.textContent='';kutu.dataset.durum=v.durum==='hata'?'hata':'';
      kutu.appendChild(el('div',null,'Klip çıkarma: '+v.yayinci+' — '+(v.asama||DURUM[v.durum]||v.durum)+' ('+sureYaz(v.gecen_sn)+')'));
      if(v.klip)kutu.appendChild(el('div','kucuk','Hazır klip: '+v.klip));
      if(v.sirada&&v.sirada.length)kutu.appendChild(el('div','kucuk','Sırada: '+v.sirada.join(', ')));
      if(calisiyor&&v.sessiz_sn>120)kutu.appendChild(el('div','kucuk','Son çıktıdan beri '+sureYaz(v.sessiz_sn)+' geçti: ağır bir adım (konuşma çözme/analiz) sürüyor olabilir; iş çalışıyor.'));
      if(calisiyor&&v.son_satir)kutu.appendChild(el('div','kucuk','Son satır: '+v.son_satir));
      if(!calisiyor&&v.uyarilar&&v.uyarilar.length)kutu.appendChild(el('div','kucuk','Notlar: '+v.uyarilar.join(' | ')));
      if(v.mesaj)kutu.appendChild(el('div',null,v.mesaj));
      var is=el('div','islem');
      if(calisiyor){is.appendChild(dugme('İptal','tehlike',function(b){
        if(!window.confirm('Çalışan klip çıkarma işi durdurulsun mu? Sıradakiler de iptal olur.'))return;
        b.disabled=true;gonder('/api/yayinci/iptal',{}).then(function(){isDurumu();});}));}
      else if(v.klip)is.appendChild(dugme('Klip listesini yenile',null,function(){location.hash='#klipler';location.reload();}));
      kutu.appendChild(is);
      document.querySelectorAll('#y-liste button.cikar').forEach(function(b){b.disabled=calisiyor;});
      if(onceki==='calisiyor'&&!calisiyor&&v.durum==='bitti'&&v.klip&&!(v.sirada&&v.sirada.length))bildirimGoster(v.klip);
      onceki=v.durum;
      ciftBekle();
    });
  }
  function ciftBekle(){
    if(zamanlayici){clearTimeout(zamanlayici);zamanlayici=null;}
    if(calisiyor)zamanlayici=setTimeout(isDurumu,3000);
  }

  // ---- ekle (tek kutu: ekle + klip çıkar)
  var jeton='';
  function onizlemeKapat(){jeton='';$('y-onizleme').hidden=true;}
  function sonuc(m,v,varsayilan){m.className=v.ok?'tamam':'hata';mesaj(m,v.mesaj||varsayilan);}
  function ekleCikar(){
    var b=$('y-ekle-cikar'),m=$('y-ekle-mesaj'),g=$('y-girdi').value.trim();onizlemeKapat();
    if(!g){m.className='hata';mesaj(m,'Yayıncının adını ya da bağlantısını yaz.');return;}
    b.disabled=true;mesaj(m,'');var eski=b.textContent;b.textContent='Doğrulanıyor ve ekleniyor… (birkaç saniye)';
    gonder('/api/yayinci/ekle-cikar',{girdi:g}).then(function(v){
      b.disabled=false;b.textContent=eski;
      sonuc(m,v,'Eklenemedi.');
      if(v.ok)$('y-girdi').value='';
      yukle();isDurumu();
    });
  }
  $('y-ekle-cikar').addEventListener('click',ekleCikar);
  $('y-girdi').addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();ekleCikar();}});
  function girdiAyir(g){
    if(/^(https?:\/\/)?((www|m)\.)?youtube\.com(\/|$)/i.test(g)||UC_RE.test(g)||g.charAt(0)==='@')return {kick:'',youtube:g};
    return {kick:g,youtube:''};
  }
  $('y-kontrol').addEventListener('click',function(){
    var b=$('y-kontrol'),m=$('y-ekle-mesaj');onizlemeKapat();
    var g=$('y-girdi').value.trim();
    if(!g){m.className='hata';mesaj(m,'Yayıncının adını ya da bağlantısını yaz.');return;}
    b.disabled=true;mesaj(m,'');b.textContent='Kontrol ediliyor…';
    gonder('/api/yayinci/onizle',girdiAyir(g)).then(function(v){
      b.disabled=false;b.textContent='Yalnız kontrol et';
      if(!v.ok){m.className='hata';mesaj(m,v.mesaj||'Kanal doğrulanamadı.');return;}
      jeton=v.jeton;var kt=v.kart,s=$('y-onizleme-satir');s.textContent='';
      if(kt.kick)s.appendChild(el('p',null,'Kick: kick.com/'+kt.kick.kanal+' — '+kt.kick.ad+(kt.kick.canli?' (şu an canlı)':'')+(kt.kick.son_yayin?' — son yayın: '+kt.kick.son_yayin:'')));
      if(kt.youtube)s.appendChild(el('p',null,'YouTube: '+(kt.youtube.tanitici?'@'+kt.youtube.tanitici:kt.youtube.kanal_id)+' — '+kt.youtube.ad+(kt.youtube.son_video?' — son video: '+kt.youtube.son_video:'')));
      if(!kt.kick)s.appendChild(el('p','kucuk','Kick kanalı yok: yalnız YouTube kaynağından klip çıkarılır.'));
      $('y-ad').value=kt.ad;$('y-kisa').value=kt.kisa_ad;$('y-onizleme').hidden=false;
    });
  });
  $('y-vazgec').addEventListener('click',function(){onizlemeKapat();mesaj($('y-ekle-mesaj'),'');});
  $('y-onayla').addEventListener('click',function(){
    var b=$('y-onayla'),m=$('y-ekle-mesaj');if(!jeton)return;
    b.disabled=true;
    gonder('/api/yayinci/ekle',{jeton:jeton,ad:$('y-ad').value,kisa_ad:$('y-kisa').value}).then(function(v){
      b.disabled=false;
      if(!v.ok){m.className='hata';mesaj(m,v.mesaj||'Eklenemedi.');return;}
      onizlemeKapat();$('y-girdi').value='';sonuc(m,v,'');
      yukle();
    });
  });

  // ---- onaylananları yayınla (yalnız tıklamayla)
  var yayinlaZaman=null;
  function yayinlaDurumu(){
    return al('/api/yayinci/yayinla-durum').then(function(v){
      var kutu=$('y-yayinla-durum'),d=$('y-yayinla');
      if(!v.ok){kutu.hidden=false;kutu.dataset.durum='hata';kutu.textContent=v.mesaj||'Durum okunamadı.';return;}
      var calis=v.durum==='calisiyor';
      $('y-yayinla-sayi').textContent=(v.bekleyen==null?'':v.bekleyen+' onaylı klip yüklenmeyi bekliyor');
      d.disabled=calis||!v.bekleyen;
      if(v.durum==='yok'){kutu.hidden=true;}
      else{
        kutu.hidden=false;kutu.textContent='';kutu.dataset.durum=v.durum==='hata'?'hata':'';
        kutu.appendChild(el('div',null,(v.adim||'')+' ('+sureYaz(v.gecen_sn)+')'));
        if(v.mesaj)kutu.appendChild(el('div',null,v.mesaj));
        (v.satirlar||[]).forEach(function(x){kutu.appendChild(el('div','kucuk',x));});
      }
      if(yayinlaZaman){clearTimeout(yayinlaZaman);yayinlaZaman=null;}
      if(calis)yayinlaZaman=setTimeout(yayinlaDurumu,2000);
    });
  }
  $('y-yayinla').addEventListener('click',function(){
    var b=$('y-yayinla'),kutu=$('y-yayinla-durum');
    if(!window.confirm('Onaylı klipler sunucuya YÜKLENECEK ve klipler.json kaydı GitHub\'a GÖNDERİLECEK. Devam edilsin mi?'))return;
    b.disabled=true;
    gonder('/api/yayinci/yayinla',{}).then(function(v){
      if(!v.ok){kutu.hidden=false;kutu.dataset.durum='hata';kutu.textContent=v.mesaj||'Başlatılamadı.';b.disabled=false;return;}
      yayinlaDurumu();
    });
  });

  sekme(location.hash==='#yayincilar'?'yayincilar':'klipler');
  isDurumu();yayinlaDurumu();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',basla);else basla();
})();
</script>"""
