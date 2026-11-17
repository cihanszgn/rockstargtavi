#!/bin/bash
# Saatlik hat. Günlük calistir.sh ile hem flock hem SQLite kilidi ortaktır.
set -uo pipefail
H=/home/haberci
R=$H/rockstargtavi
G=$H/gunluk
export HOME=$H PATH=$H/.local/bin:$H/bin:/usr/local/bin:/usr/bin:/bin TZ=Europe/Istanbul
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
mkdir -p "$G" "$H/calisma"
LOG=$G/$(date +%F).log
SON=$G/son-durum-saatlik.txt
# Deneme için ortamdan değiştirilebilir (varsayılanlar gerçek yollar).
PC_NABIZ=${PC_NABIZ:-$H/pc-nabiz}
PC_SONUC=${PC_SONUC:-$H/pc-sonuc.json}
IZLE_DURUM=${IZLE_DURUM:-$H/izleme-durum.json}
DENEME=0; NABIZ=1; BILDIRIM_KURU=0; IZLE_DENEME=0
for arg in "$@"; do
  case "$arg" in
    --deneme) DENEME=1 ;;
    --nabiz-yoksay) NABIZ=0 ;;
    --bildirim-deneme) BILDIRIM_KURU=1 ;;
    --izle-deneme) IZLE_DENEME=1 ;;
    *) echo "Bilinmeyen seçenek: $arg" >&2; exit 2 ;;
  esac
done
yaz() { echo "$(date '+%F %T') [saatlik-hat] $*" | tee -a "$LOG"; }
bildir() {
  [ -s "$H/.bildirim-adresi" ] || return 1
  printf '%s' "$1" | py -c 'import json,sys; print(json.dumps({"metin":sys.stdin.read()[:3500]}))' > "$H/calisma/hat-bildirim.json" || return 1
  if [ "$BILDIRIM_KURU" = 1 ]; then echo "BILDIRIM_KURU: adres tanımlı; JSON üretildi; POST yapılmadı"; return 0; fi
  local http
  http=$(curl -s --max-time 20 -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' --data @"$H/calisma/hat-bildirim.json" "$(cat "$H/.bildirim-adresi")") || return 1
  [[ "$http" = 2* ]]
}
bitir() {
  local kod=$1 ileti=$2 onceki
  onceki=$(cut -d' ' -f3 "$SON" 2>/dev/null || true)
  yaz "bitti kod=$kod $ileti"
  if [ "$DENEME" = 0 ]; then
    printf '%s kod=%s %s\n' "$(date '+%F %T')" "$kod" "$ileti" > "$SON"
    if [ "$kod" != 0 ] && [ "$onceki" != "kod=$kod" ]; then
      bildir "🔴 Site otomasyonu (saatlik hat) çalışamadı: $ileti" || yaz "bildirim gönderilemedi"
    elif [ "$kod" = 0 ] && [ -n "$onceki" ] && [ "$onceki" != 'kod=0' ]; then
      bildir '🟢 Site otomasyonu (saatlik hat) yeniden çalışıyor.' || yaz "bildirim gönderilemedi"
    fi
  fi
  exit "$kod"
}
# Sessiz arıza bekçisi. Nabız nedeniyle tur atlansa bile her çağrıda çalışır (atlama
# bildirimsiz hata sessizliğinin kaynağıydı). Yalnız DURUM DEĞİŞİNCE mesaj gider; mesaj
# gerçekten gitmeden durum kaydedilmez, gitmezse ertesi saat yeniden denenir.
izle() {
  local satirlar anahtar durum metin
  satirlar=$(py tools/haber_hatti.py --izle --pc-sonuc "$PC_SONUC" --izle-durum "$IZLE_DURUM" 2>>"$LOG") \
    || { echo "izleme çalışmadı (tur etkilenmez)" >> "$LOG"; return 0; }
  while IFS=$'\t' read -r anahtar durum metin; do
    [ -n "$anahtar" ] || continue
    if [ "$DENEME" = 1 ]; then echo "IZLEME_KURU: $anahtar -> $durum: $metin"; continue; fi
    if bildir "$metin"; then
      py tools/haber_hatti.py --izle-kaydet "$anahtar" "$durum" --izle-durum "$IZLE_DURUM" </dev/null || yaz 'izleme durumu yazılamadı'
    else
      yaz 'izleme bildirimi gönderilemedi; sonraki turda yeniden denenecek'
    fi
  done <<< "$satirlar"
}
if [ "$BILDIRIM_KURU" = 1 ]; then bildir 'Geçiş tamam (kuru doğrulama).'; exit $?; fi
cd "$R" || bitir 2 'depo bulunamadı'
NABIZ_DURUM=
if [ "$IZLE_DENEME" = 1 ]; then
  # Bildirim ve durum dosyası değişmez; yalnız kararlar yazdırılır.
  DENEME=1
  NABIZ_DURUM=$(py tools/haber_hatti.py --nabiz-kontrol "$PC_NABIZ" --pc-sonuc "$PC_SONUC")
  echo "NABIZ_KARARI: $NABIZ_DURUM (atla = sunucu turu atlar; hatali/eski = sunucu turu çalıştırır)"
  izle
  exit 0
fi
izle
if [ "$NABIZ" = 1 ] && NABIZ_DURUM=$(py tools/haber_hatti.py --nabiz-kontrol "$PC_NABIZ" --pc-sonuc "$PC_SONUC"); then
  bitir 0 'bilgisayar çalışıyor; nabız 50 dakikadan yeni ve son turu hatasız, sunucu atlandı'
fi
exec 9>"$H/calisma.kilit"
flock -n 9 || bitir 0 'günlük/saatlik ortak çalışma kilidi meşgul'
if [ "$NABIZ_DURUM" = hatali ]; then NEDEN='bilgisayarın son turu hatayla bitti, yedek devrede'; else NEDEN='bilgisayar nabzı eski veya denemede devre dışı'; fi
yaz "tur başladı deneme=$DENEME; $NEDEN"
[ -s "$H/.haber.env" ] && { set -a; . "$H/.haber.env"; set +a; }
git pull --ff-only origin main >> "$LOG" 2>&1 || bitir 3 'git pull başarısız; ağaç korundu'
# PC hafızası atomik teslim edilir. Her URL için iki makinedeki en yeni kararı tut.
if [ "$DENEME" = 0 ]; then
py - <<'PY' >> "$LOG" 2>&1
import json, pathlib
from datetime import datetime
dst = pathlib.Path('.git/haber-oto/gorulen.json')
src = pathlib.Path('/home/haberci/pc-gorulen.json')
try:
    incoming = json.loads(src.read_text(encoding='utf-8'))
    current = json.loads(dst.read_text(encoding='utf-8')) if dst.exists() else {}
    if not isinstance(incoming, dict) or not isinstance(current, dict):
        raise ValueError('hafıza nesnesi gerekli')
    for url, item in incoming.items():
        try:
            if url not in current or datetime.fromisoformat(item['zaman']) > datetime.fromisoformat(current[url]['zaman']):
                current[url] = item
        except (ValueError, TypeError, KeyError):
            continue
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(current, ensure_ascii=False), encoding='utf-8')
except (OSError, ValueError) as exc:
    print('PC hafızası aktarılmadı (tur devam ediyor):', type(exc).__name__)
PY
fi
ARGS=(--modeller "${HABER_MODELLER:-otomasyon/modeller-sunucu.json}")
[ "$DENEME" = 1 ] && ARGS+=(--deneme)
RUN=$G/hat-$(date +%Y%m%d-%H%M%S)-$$.log
py tools/haber_hatti.py "${ARGS[@]}" > "$RUN" 2>&1
KOD=$?
cat "$RUN" >> "$LOG"
[ "$KOD" = 0 ] || bitir "$KOD" "hat hata verdi; günlük: $RUN"
OZET=$(py - <<'PY'
import json
d=json.load(open('.git/haber-oto/sonuc.json', encoding='utf-8'))
print('kaynak=%s aday=%s onay=%s commit=%s süre=%ss' % (len(d['kaynaklar']), d.get('aday_sayisi',0), len(d.get('onaylanan',[])), d.get('commit'), d['sure_saniye']))
PY
) || bitir 4 'sonuç okunamadı'
if [ "$DENEME" = 0 ]; then
  COMMIT=$(py -c 'import json; print(json.load(open(".git/haber-oto/sonuc.json",encoding="utf-8")).get("commit") or "")')
  if [ -n "$COMMIT" ]; then bildir "📰 Yeni haber yayında: $OZET" || yaz 'yayın bildirimi gönderilemedi'; fi
fi
bitir 0 "$OZET; günlük: $RUN"
