#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Splash Code Studio - Patch 056 "Dil Secici + Temiz AI + Resize"
1) Dil secici geri gelir: <select> DEGIL, ozel listbox (054'un select-avcisi
   artik dokunamaz). Arama, klavye, kendi scrollbar'i, secimde yesil onay.
2) 054'un agresif select-gizleyicisi kaldirilir, sessiz bildirim politikasi
   aynen korunarak yeniden kurulur.
3) AI paneli tertemiz acilir (karsilama mesaji yok, bos-durum ekrani var).
4) AI paneli yeniden boyutlandirilabilir: surukle, cift tikla sifirla,
   klavye ile ayarla, genislik hatirlanir.

    py path.py --check
    py path.py --dry-run
    py path.py
"""

import argparse
import os
import re
import sys
import tempfile
import time
import zipfile

PATCH_ID = "056"
TITLE = "Dil secici onarim + temiz AI paneli + AI resize"
HTML_REL = "splash_code/templates/index.html"

QUIET_MARK = "<!--SC-QUIET-054-->"
QUIET_END = "<!--/SC-QUIET-054-->"
MARK = "<!--SC-UI-056-->"
END = "<!--/SC-UI-056-->"

GREETING_RE = re.compile(
    r'<div[^>]*class="[^"]*ai-msg[^"]*"[^>]*>\s*Merhaba![\s\S]*?</div>',
    re.I)

INJECT = r"""
<!--SC-UI-056-->
<style>
/* eski seciciler tamamen sahneden cekilir */
#scLangSelect,#scLangPick,#sc55Lang{display:none!important}

/* ══ DIL SECICI ══ */
#sc56Lang{position:relative;display:inline-flex;flex:0 0 auto;margin:0 6px;font-family:var(--font-ui,system-ui,sans-serif)}
#sc56Btn{display:inline-flex;align-items:center;gap:7px;height:28px;padding:0 10px;
 background:var(--bg,#0d1117);border:1px solid var(--border,#21262d);border-radius:8px;
 color:var(--text,#e6edf3);font:600 11.5px var(--font-ui,system-ui,sans-serif);cursor:pointer;
 transition:border-color .16s,box-shadow .16s,background .16s;max-width:158px}
#sc56Btn:hover{border-color:var(--accent,#2f81f7);background:var(--bg-hover,#161b22)}
#sc56Btn:focus-visible{outline:none;border-color:var(--accent,#2f81f7);
 box-shadow:0 0 0 3px color-mix(in srgb,var(--accent,#2f81f7) 22%,transparent)}
#sc56Btn .g{font-size:13px;line-height:1;flex:0 0 auto}
#sc56Btn .nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
#sc56Btn .cv{flex:0 0 auto;opacity:.6;transition:transform .18s}
#sc56Lang.open #sc56Btn .cv{transform:rotate(180deg)}
#sc56Lang.ok #sc56Btn{border-color:var(--success,#3fb950);
 box-shadow:0 0 0 3px color-mix(in srgb,var(--success,#3fb950) 24%,transparent)}
#sc56Tick{position:absolute;right:-6px;top:-6px;width:15px;height:15px;border-radius:50%;
 background:var(--success,#3fb950);color:#04120a;font-size:9px;font-weight:900;
 display:grid;place-items:center;opacity:0;transform:scale(.3);transition:.22s;pointer-events:none}
#sc56Lang.ok #sc56Tick{opacity:1;transform:scale(1)}

#sc56Menu{position:absolute;top:34px;right:0;width:224px;z-index:400;display:none;
 background:var(--bg-alt,#161b22);border:1px solid var(--border,#21262d);border-radius:11px;
 box-shadow:0 22px 54px rgba(0,0,0,.62);overflow:hidden}
#sc56Lang.open #sc56Menu{display:block;animation:sc56in .15s cubic-bezier(.2,.9,.3,1.2)}
@keyframes sc56in{from{opacity:0;transform:translateY(-6px) scale(.98)}}
#sc56Search{width:100%;box-sizing:border-box;padding:9px 11px;background:var(--bg,#0d1117);
 border:none;border-bottom:1px solid var(--border,#21262d);color:var(--text,#e6edf3);
 font:500 12px var(--font-ui,system-ui,sans-serif);outline:none}
#sc56Search::placeholder{color:var(--dim,#7d8590)}
#sc56List{max-height:288px;overflow-y:auto;padding:5px;
 scrollbar-width:thin;scrollbar-color:var(--accent,#2f81f7) transparent}
#sc56List::-webkit-scrollbar{width:9px}
#sc56List::-webkit-scrollbar-track{background:transparent;margin:4px 0}
#sc56List::-webkit-scrollbar-thumb{background:linear-gradient(180deg,var(--accent,#2f81f7),#8b5cf6);
 border-radius:99px;border:2px solid var(--bg-alt,#161b22);background-clip:padding-box}
#sc56List::-webkit-scrollbar-thumb:hover{background:var(--accent,#2f81f7);background-clip:padding-box}
.sc56Item{display:flex;align-items:center;gap:9px;padding:7px 9px;border-radius:7px;cursor:pointer;
 color:var(--text,#e6edf3);font-size:12.5px;line-height:1.3}
.sc56Item .code{margin-left:auto;font:600 9.5px var(--font-mono,monospace);color:var(--dim,#7d8590);
 border:1px solid var(--border,#21262d);border-radius:4px;padding:1px 5px;text-transform:uppercase}
.sc56Item .mk{width:13px;flex:0 0 13px;color:var(--success,#3fb950);font-size:11px;opacity:0}
.sc56Item.cur .mk{opacity:1}
.sc56Item.cur{background:color-mix(in srgb,var(--accent,#2f81f7) 15%,transparent)}
.sc56Item.act,.sc56Item:hover{background:var(--bg-hover,#1f242c)}
.sc56Item.act{box-shadow:inset 2px 0 0 var(--accent,#2f81f7)}
#sc56None{padding:14px;text-align:center;color:var(--dim,#7d8590);font-size:11.5px}

/* ══ AI BOS DURUM ══ */
#sc56AiEmpty{display:flex;flex-direction:column;align-items:center;justify-content:center;
 gap:10px;padding:34px 22px;text-align:center;margin:auto;min-height:180px;
 animation:sc56fade .35s ease}
@keyframes sc56fade{from{opacity:0;transform:translateY(8px)}}
#sc56AiEmpty .mk{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;
 background:color-mix(in srgb,var(--accent,#2f81f7) 13%,transparent);
 border:1px solid color-mix(in srgb,var(--accent,#2f81f7) 34%,transparent)}
#sc56AiEmpty .mk svg{width:22px;height:22px;stroke:var(--accent,#2f81f7);fill:none;stroke-width:1.6;
 stroke-linecap:round;stroke-linejoin:round}
#sc56AiEmpty b{font-size:13px;font-weight:650;color:var(--text,#e6edf3);letter-spacing:-.01em}
#sc56AiEmpty span{font-size:11.5px;color:var(--dim,#7d8590);max-width:230px;line-height:1.6}
#sc56AiEmpty .kb{display:flex;gap:5px;flex-wrap:wrap;justify-content:center;margin-top:2px}
#sc56AiEmpty .kb i{font-style:normal;font:600 9.5px var(--font-mono,monospace);color:var(--dim,#7d8590);
 border:1px solid var(--border,#21262d);border-radius:99px;padding:3px 8px;background:var(--bg,#0d1117)}

/* ══ AI RESIZE ══ */
#sc56AiRz{flex:0 0 7px;width:7px;cursor:col-resize;display:none;position:relative;z-index:20;
 background:transparent;touch-action:none}
#sc56AiRz.on{display:block}
#sc56AiRz::after{content:"";position:absolute;left:2px;top:0;bottom:0;width:2px;border-radius:2px;
 background:var(--border,#21262d);transition:background .15s,box-shadow .15s}
#sc56AiRz:hover::after,#sc56AiRz.drag::after,#sc56AiRz:focus-visible::after{
 background:var(--accent,#2f81f7);box-shadow:0 0 10px color-mix(in srgb,var(--accent,#2f81f7) 70%,transparent)}
#sc56AiRz:focus-visible{outline:none}
#sc56AiBadge{position:fixed;z-index:9999;pointer-events:none;display:none;
 background:var(--accent,#2f81f7);color:#04121f;font:700 10.5px var(--font-mono,monospace);
 padding:3px 8px;border-radius:6px;box-shadow:0 6px 18px rgba(0,0,0,.5)}
#sc56AiBadge.on{display:block}
</style>
<script>
(function(){
'use strict';
if(window.__SC056__)return;
window.__SC056__=true;

var ORDER=["tr","en","de","fr","es","it","pt","ru","ja","ko","zh","ar"];
var NAMES={tr:"Türkçe",en:"English",de:"Deutsch",fr:"Français",es:"Español",it:"Italiano",
pt:"Português",ru:"Русский",ja:"日本語",ko:"한국어",zh:"中文",ar:"العربية"};
/* kendi yeni metinlerimiz icin 12 dil */
var T56={
lang:["Dil","Language","Sprache","Langue","Idioma","Lingua","Idioma","Язык","言語","언어","语言","اللغة"],
search:["Ara...","Search...","Suchen...","Rechercher...","Buscar...","Cerca...","Pesquisar...","Поиск...","検索...","검색...","搜索...","بحث..."],
none:["Sonuç yok","No results","Keine Ergebnisse","Aucun résultat","Sin resultados","Nessun risultato","Sem resultados","Нет результатов","結果なし","결과 없음","无结果","لا نتائج"],
aiTitle:["AI asistan hazır","AI assistant ready","KI-Assistent bereit","Assistant IA prêt","Asistente IA listo","Assistente IA pronto","Assistente IA pronto","ИИ-ассистент готов","AIアシスタント準備完了","AI 어시스턴트 준비됨","AI 助手已就绪","مساعد الذكاء جاهز"],
aiHint:["Aktif dosya hakkında bir şey sor. Bağlam otomatik eklenir.","Ask about the active file. Context is attached automatically.","Frage zur aktiven Datei. Kontext wird automatisch angehängt.","Demandez sur le fichier actif. Le contexte est joint automatiquement.","Chiedi sul file attivo. Il contesto è allegato automaticamente.","Pergunte sobre o arquivo ativo. O contexto é anexado automaticamente.","Спросите об активном файле. Контекст добавляется автоматически.","アクティブなファイルについて質問。コンテキストは自動付加。","활성 파일에 대해 질문하세요. 컨텍스트가 자동 첨부됩니다.","就当前文件提问，上下文会自动附加。","اسأل عن الملف النشط. يُرفق السياق تلقائياً."],
rz:["Sürükle: AI panelini boyutlandır · çift tık: sıfırla","Drag: resize AI panel · double-click: reset","Ziehen: KI-Panelgröße · Doppelklick: zurücksetzen","Glisser : taille du panneau IA · double-clic : réinit.","Arrastra: tamaño del panel IA · doble clic: reiniciar","Trascina: dimensione pannello IA · doppio clic: reset","Arraste: tamanho do painel IA · duplo clique: redefinir","Перетащите: размер панели ИИ · двойной клик: сброс","ドラッグ：AIパネル幅 · ダブルクリック：リセット","드래그: AI 패널 크기 · 더블클릭: 초기화","拖动：AI 面板宽度 · 双击：重置","اسحب: حجم لوحة الذكاء · نقرة مزدوجة: تصفير"]
};
function lang(){
  try{ return (window.settings&&window.settings.language)||localStorage.getItem("sc_lang")||"tr"; }
  catch(e){ return "tr"; }
}
function t56(k){
  var a=T56[k]; if(!a)return k;
  var i=ORDER.indexOf(lang()); if(i<0)i=0;
  return a[i]||a[0];
}
function E(i){return document.getElementById(i);}
function api(){return (window.pywebview&&window.pywebview.api)||null;}
function relayout(){ try{ if(window.editor)editor.layout(); }catch(e){}
  try{ if(window.editor2)editor2.layout(); }catch(e){} }

/* ═════════ 1) SESSIZ BILDIRIM (054 politikasi, yeniden) ═════════ */
var ALLOW_UNTIL=0;
var READY=/(hazır|hazir|ready|kuruldu|installed|kullanıma hazır|kullanima hazir)/i;
var SUBJ=/(lsp|language\s*server|dil\s*sunucusu|dil\s*paketi|language\s*pack|runtime|basedpyright|pyright|pylsp|gopls|rust-analyzer|jdtls|clangd|typescript-language-server|node\.?js|python|golang|\bgo\b|rust|java|jdk|ruby|php|lua|perl|gcc|mingw)/i;
function allowed(m){
  if(window.__sc54verbose||window.__sc56verbose)return true;
  if(Date.now()<ALLOW_UNTIL)return true;
  var s=String(m==null?"":m);
  return READY.test(s)&&SUBJ.test(s);
}
function gate(){
  if(typeof window.toast!=="function"||window.toast.__sc56)return;
  var prev=window.toast;
  var g=function(m,t,d){
    if(allowed(m))return prev(m,t,d);
    try{ if(window.console)console.debug("[silent]",m); }catch(e){}
    return undefined;
  };
  g.__sc56=true; window.toast=g; window.scToast=g;
  try{ window.sc23Toast=g; }catch(e){}
}
function hookInstallers(){
  var a=api(); if(!a)return false;
  var hit=false;
  Object.keys(a).forEach(function(k){
    if(!/kur|install/i.test(k))return;
    var f=a[k]; if(typeof f!=="function"||f.__sc56)return;
    var w=function(){
      var p=f.apply(this,arguments);
      try{ if(p&&typeof p.then==="function")
        p.then(function(r){ if(r&&r.ok)ALLOW_UNTIL=Date.now()+5000; }); }catch(e){}
      return p;
    };
    w.__sc56=true; try{ a[k]=w; hit=true; }catch(e){}
  });
  return hit;
}
window.scToastVerbose=function(on){ window.__sc56verbose=!!on; window.__sc54verbose=!!on; };
gate();
try{ if(window._notifications&&window._notifications.length){
  window._notifications.length=0; if(window.renderNotif)window.renderNotif(); } }catch(e){}
var gi=0, gt=setInterval(function(){ gi++; gate(); if(hookInstallers()||gi>60)clearInterval(gt); },250);

/* ═════════ 2) DIL SECICI (ozel listbox) ═════════ */
var ACT=0, FILTERED=ORDER.slice();
function currentEngine(){
  return window.sc55SetLang||window.sc38SetLang||window.sc35SetLang||null;
}
function applyLang(l){
  l=(l||"tr").toLowerCase();
  if(ORDER.indexOf(l)<0)l="tr";
  var eng=currentEngine();
  if(eng){ try{ eng(l,true); }catch(e){ try{ eng(l); }catch(e2){} } }
  try{ if(window.settings)window.settings.language=l; }catch(e){}
  try{ localStorage.setItem("sc_lang",l); }catch(e){}
  var a=api(); if(a&&a.dil_ayarla){ try{ a.dil_ayarla(l); }catch(e){} }
  window._i18n=window._i18n||{}; window._i18n.lang=l;
  syncLabel(); paintEmpty(); paintRz();
  try{ if(window.scI18nApply)window.scI18nApply(); }catch(e){}
}
window.scSetLanguage=applyLang;
window.scChangeLang=applyLang;
window.sc56SetLang=applyLang;

function syncLabel(){
  var b=E("sc56Btn"); if(!b)return;
  var nm=b.querySelector(".nm"); if(nm)nm.textContent=NAMES[lang()]||lang();
  b.title=t56("lang");
  var s=E("sc56Search"); if(s)s.placeholder=t56("search");
}
function renderList(){
  var box=E("sc56List"); if(!box)return;
  var q=(E("sc56Search")&&E("sc56Search").value||"").toLowerCase().trim();
  FILTERED=ORDER.filter(function(c){
    if(!q)return true;
    return c.indexOf(q)>=0||NAMES[c].toLowerCase().indexOf(q)>=0;
  });
  if(ACT>=FILTERED.length)ACT=Math.max(0,FILTERED.length-1);
  if(!FILTERED.length){ box.innerHTML='<div id="sc56None">'+t56("none")+'</div>'; return; }
  box.innerHTML=FILTERED.map(function(c,i){
    return '<div class="sc56Item'+(c===lang()?" cur":"")+(i===ACT?" act":"")+'" role="option" '+
      'aria-selected="'+(c===lang())+'" data-c="'+c+'">'+
      '<span class="mk">✓</span><span>'+NAMES[c]+'</span><span class="code">'+c+'</span></div>';
  }).join("");
  Array.prototype.forEach.call(box.querySelectorAll(".sc56Item"),function(el){
    el.onmousedown=function(ev){ ev.preventDefault(); };
    el.onclick=function(){ choose(el.dataset.c); };
    el.onmouseenter=function(){ ACT=FILTERED.indexOf(el.dataset.c); markActive(); };
  });
}
function markActive(){
  var box=E("sc56List"); if(!box)return;
  Array.prototype.forEach.call(box.querySelectorAll(".sc56Item"),function(el,i){
    el.classList.toggle("act",i===ACT);
    if(i===ACT){ try{ el.scrollIntoView({block:"nearest"}); }catch(e){} }
  });
}
function openMenu(){
  var w=E("sc56Lang"); if(!w)return;
  w.classList.add("open");
  E("sc56Btn").setAttribute("aria-expanded","true");
  ACT=Math.max(0,FILTERED.indexOf(lang()));
  var s=E("sc56Search"); if(s){ s.value=""; }
  renderList();
  setTimeout(function(){ if(s)s.focus(); },30);
}
function closeMenu(focusBack){
  var w=E("sc56Lang"); if(!w)return;
  w.classList.remove("open");
  E("sc56Btn").setAttribute("aria-expanded","false");
  if(focusBack){ try{ E("sc56Btn").focus(); }catch(e){} }
}
function choose(c){
  applyLang(c);
  closeMenu(true);
  var w=E("sc56Lang");
  if(w){ w.classList.add("ok"); setTimeout(function(){ w.classList.remove("ok"); },1100); }
}
function mountLang(){
  ["scLangSelect","scLangPick","sc55Lang"].forEach(function(id){
    var n=E(id); if(n)n.style.display="none";
  });
  if(E("sc56Lang"))return;
  var tb=E("topbar"); if(!tb)return;
  var w=document.createElement("div");
  w.id="sc56Lang";
  w.innerHTML=
    '<button id="sc56Btn" type="button" aria-haspopup="listbox" aria-expanded="false">'+
      '<span class="g">🌐</span><span class="nm"></span>'+
      '<svg class="cv" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" '+
      'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>'+
    '</button><i id="sc56Tick">✓</i>'+
    '<div id="sc56Menu" role="dialog">'+
      '<input id="sc56Search" type="text" autocomplete="off" spellcheck="false" aria-label="filter">'+
      '<div id="sc56List" role="listbox"></div>'+
    '</div>';
  var sp=tb.querySelector(".spacer");
  if(sp)tb.insertBefore(w,sp); else tb.appendChild(w);
  syncLabel(); renderList();
  E("sc56Btn").onclick=function(ev){
    ev.stopPropagation();
    if(w.classList.contains("open"))closeMenu(false); else openMenu();
  };
  E("sc56Search").addEventListener("input",function(){ ACT=0; renderList(); });
  w.addEventListener("keydown",function(ev){
    var open=w.classList.contains("open");
    if(ev.key==="Escape"){ if(open){ ev.preventDefault(); closeMenu(true); } return; }
    if(!open&&(ev.key==="Enter"||ev.key===" "||ev.key==="ArrowDown")){
      ev.preventDefault(); openMenu(); return;
    }
    if(!open)return;
    if(ev.key==="ArrowDown"){ ev.preventDefault(); ACT=Math.min(FILTERED.length-1,ACT+1); markActive(); }
    else if(ev.key==="ArrowUp"){ ev.preventDefault(); ACT=Math.max(0,ACT-1); markActive(); }
    else if(ev.key==="Home"){ ev.preventDefault(); ACT=0; markActive(); }
    else if(ev.key==="End"){ ev.preventDefault(); ACT=FILTERED.length-1; markActive(); }
    else if(ev.key==="Enter"){ ev.preventDefault(); if(FILTERED[ACT])choose(FILTERED[ACT]); }
  });
  document.addEventListener("mousedown",function(ev){
    if(!w.contains(ev.target))closeMenu(false);
  });
}
mountLang();
setTimeout(mountLang,500); setTimeout(mountLang,1600); setTimeout(mountLang,3400);
setInterval(function(){
  mountLang();
  var b=E("sc56Btn"); if(!b)return;
  var nm=b.querySelector(".nm");
  if(nm&&nm.textContent!==(NAMES[lang()]||lang()))syncLabel();
},1200);

/* ═════════ 3) AI PANELI: TEMIZ ACILIS ═════════ */
var EMPTY_HTML=
  '<div class="mk"><svg viewBox="0 0 24 24">'+
  '<path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z"/>'+
  '<path d="M18.5 16.5l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"/></svg></div>'+
  '<b id="sc56AiT"></b><span id="sc56AiH"></span>'+
  '<div class="kb"><i>Ctrl+Enter</i><i>Esc</i></div>';
function msgsBox(){ return E("aiMessages")||E("aiMsgs"); }
function paintEmpty(){
  var e=E("sc56AiEmpty"); if(!e)return;
  var t=E("sc56AiT"), h=E("sc56AiH");
  if(t)t.textContent=t56("aiTitle");
  if(h)h.textContent=t56("aiHint");
}
function ensureEmpty(){
  var box=msgsBox(); if(!box)return;
  var e=E("sc56AiEmpty");
  if(!e){
    e=document.createElement("div");
    e.id="sc56AiEmpty";
    e.innerHTML=EMPTY_HTML;
    box.appendChild(e);
    paintEmpty();
  }
  var n=box.querySelectorAll(".ai-msg,.msg").length;
  e.style.display=n?"none":"flex";
}
function wipeAI(){
  var box=msgsBox(); if(!box)return;
  Array.prototype.forEach.call(box.querySelectorAll(".ai-msg,.msg"),function(n){ n.remove(); });
  ensureEmpty();
}
var GREET=/^(merhaba|hello|hallo|bonjour|hola|ciao|olá|привет|こんにちは|안녕하세요|你好|مرحبا)/i;
function sweep(){
  var box=msgsBox(); if(!box)return;
  Array.prototype.forEach.call(box.querySelectorAll(".ai-msg,.msg"),function(n){
    var tx=(n.textContent||"").trim();
    if(GREET.test(tx)&&tx.length<220)n.remove();
  });
  ensureEmpty();
}
(function hookAI(){
  var box=msgsBox();
  if(!box){ setTimeout(hookAI,400); return; }
  wipeAI();
  try{
    new MutationObserver(function(){ ensureEmpty(); })
      .observe(box,{childList:true,subtree:false});
  }catch(e){}
  var ac=window.aiClear||window.aiTemizle;
  if(typeof ac==="function"){
    var w=function(){ var r; try{ r=ac.apply(this,arguments); }catch(e){} wipeAI(); return r; };
    window.aiClear=w; window.aiTemizle=w;
  }
  [200,900,1800,3200,5200].forEach(function(ms){ setTimeout(sweep,ms); });
})();

/* ═════════ 4) AI PANEL RESIZE ═════════ */
var MINW=280, DEFW=380;
function maxW(){ return Math.max(MINW+40, Math.min(760, Math.round(window.innerWidth*0.62))); }
function panel(){ return E("aiPanel"); }
function getW(){
  var v=parseInt(localStorage.getItem("sc_ai_w")||"",10);
  if(!v||isNaN(v))v=DEFW;
  return Math.max(MINW,Math.min(maxW(),v));
}
function setW(w,save){
  var p=panel(); if(!p)return;
  w=Math.max(MINW,Math.min(maxW(),Math.round(w)));
  p.style.width=w+"px";
  p.style.flex="0 0 "+w+"px";
  p.style.minWidth=w+"px";
  var rz=E("sc56AiRz");
  if(rz){ rz.setAttribute("aria-valuenow",String(w));
          rz.setAttribute("aria-valuemin",String(MINW));
          rz.setAttribute("aria-valuemax",String(maxW())); }
  if(save){ try{ localStorage.setItem("sc_ai_w",String(w)); }catch(e){} }
  relayout();
  return w;
}
function paintRz(){ var rz=E("sc56AiRz"); if(rz)rz.title=t56("rz"); }
function rzVisible(){
  var p=panel(), rz=E("sc56AiRz"); if(!p||!rz)return;
  var open=p.classList.contains("open")||getComputedStyle(p).display!=="none";
  rz.classList.toggle("on",!!open);
}
function mountRz(){
  var p=panel(); if(!p)return;
  if(!E("sc56AiRz")){
    var rz=document.createElement("div");
    rz.id="sc56AiRz";
    rz.setAttribute("role","separator");
    rz.setAttribute("aria-orientation","vertical");
    rz.setAttribute("tabindex","0");
    rz.title=t56("rz");
    p.parentNode.insertBefore(rz,p);
    var badge=document.createElement("div");
    badge.id="sc56AiBadge";
    document.body.appendChild(badge);

    var drag=false,sx=0,sw=0,raf=0,pend=null;
    function frame(){
      raf=0; if(pend==null)return;
      var w=setW(pend,false); pend=null;
      var b=E("sc56AiBadge");
      if(b)b.textContent=w+" px";
    }
    rz.addEventListener("pointerdown",function(ev){
      ev.preventDefault();
      drag=true; sx=ev.clientX; sw=p.getBoundingClientRect().width;
      rz.classList.add("drag");
      try{ rz.setPointerCapture(ev.pointerId); }catch(e){}
      document.body.style.userSelect="none";
      document.body.style.cursor="col-resize";
      var b=E("sc56AiBadge");
      if(b){ b.classList.add("on"); b.textContent=Math.round(sw)+" px";
             b.style.left=(ev.clientX-46)+"px"; b.style.top=(ev.clientY-30)+"px"; }
    });
    rz.addEventListener("pointermove",function(ev){
      if(!drag)return;
      pend=sw+(sx-ev.clientX);
      var b=E("sc56AiBadge");
      if(b){ b.style.left=(ev.clientX-46)+"px"; b.style.top=(ev.clientY-30)+"px"; }
      if(!raf)raf=requestAnimationFrame(frame);
    });
    function stop(ev){
      if(!drag)return;
      drag=false;
      rz.classList.remove("drag");
      try{ rz.releasePointerCapture(ev.pointerId); }catch(e){}
      document.body.style.userSelect="";
      document.body.style.cursor="";
      var b=E("sc56AiBadge"); if(b)b.classList.remove("on");
      setW(p.getBoundingClientRect().width,true);
    }
    rz.addEventListener("pointerup",stop);
    rz.addEventListener("pointercancel",stop);
    rz.addEventListener("dblclick",function(){ setW(DEFW,true); });
    rz.addEventListener("keydown",function(ev){
      var cur=p.getBoundingClientRect().width, step=ev.shiftKey?48:16, done=true;
      if(ev.key==="ArrowLeft")setW(cur+step,true);
      else if(ev.key==="ArrowRight")setW(cur-step,true);
      else if(ev.key==="Home")setW(MINW,true);
      else if(ev.key==="End")setW(maxW(),true);
      else if(ev.key==="Enter"||ev.key===" ")setW(DEFW,true);
      else done=false;
      if(done)ev.preventDefault();
    });
  }
  setW(getW(),false);
  rzVisible();
}
(function bootRz(){
  if(!panel()){ setTimeout(bootRz,400); return; }
  mountRz();
  try{
    new MutationObserver(function(){ rzVisible(); })
      .observe(panel(),{attributes:true,attributeFilter:["class","style"]});
  }catch(e){}
  window.addEventListener("resize",function(){ setW(getW(),false); rzVisible(); });
  [300,1200,2600].forEach(function(ms){ setTimeout(function(){ mountRz(); rzVisible(); },ms); });
})();

/* dil motoru hazir olunca etiketleri tazele */
setTimeout(function(){ syncLabel(); paintEmpty(); paintRz(); },1500);
setTimeout(function(){ syncLabel(); paintEmpty(); paintRz(); },3500);
})();
</script>
<!--/SC-UI-056-->
"""


def find_root(cli=None):
    c = []
    if cli:
        c.append(os.path.abspath(cli))
    here = os.path.dirname(os.path.abspath(__file__))
    c += [here, os.getcwd(), os.path.dirname(here)]
    for p in c:
        if p and os.path.isdir(os.path.join(p, "splash_code")):
            return p
    return here


def rd(p):
    with open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def wr(path, content):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".sctmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise


def strip_block(src, s, e):
    while True:
        i = src.find(s)
        if i < 0:
            return src
        j = src.find(e, i)
        src = src[:i] if j < 0 else src[:i] + src[j + len(e):]


def backup(root):
    bd = os.path.join(root, "_backups")
    os.makedirs(bd, exist_ok=True)
    zp = os.path.join(bd, "pre_patch%s_%s.zip"
                      % (PATCH_ID, time.strftime("%Y%m%d_%H%M%S")))
    hp = os.path.join(root, HTML_REL)
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        if os.path.isfile(hp):
            z.write(hp, HTML_REL)
    return zp


def restore(root, zp):
    if not os.path.isfile(zp):
        print("Backup yok: " + zp)
        return 1
    with zipfile.ZipFile(zp) as z:
        for name in z.namelist():
            t = os.path.join(root, name.replace("/", os.sep))
            os.makedirs(os.path.dirname(t), exist_ok=True)
            with open(t, "wb") as f:
                f.write(z.read(name))
    print("Geri yuklendi.")
    return 0


def check(root):
    hp = os.path.join(root, HTML_REL)
    idx = rd(hp) if os.path.isfile(hp) else ""
    print("\n  --- TANI ---")
    print("  SC-QUIET-054 (select avcisi) : %s"
          % ("VAR -> kaldirilacak" if QUIET_MARK in idx else "YOK"))
    print("  SC-I18N-055 (motor)          : %s"
          % ("VAR" if "SC-I18N-055" in idx else "YOK"))
    print("  SC-UI-056                    : %s" % ("VAR" if MARK in idx else "YOK"))
    print("  AI karsilama mesaji          : %s"
          % ("VAR -> silinecek" if GREETING_RE.search(idx) else "YOK"))
    print("  sc56Lang / sc56AiRz          : %s / %s"
          % ("VAR" if "sc56Lang" in idx else "YOK",
             "VAR" if "sc56AiRz" in idx else "YOK"))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--restore", metavar="ZIP")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    root = find_root(a.root)

    print("=" * 62)
    print("  Splash Code Studio - Patch %s" % PATCH_ID)
    print("  " + TITLE)
    print("=" * 62)
    print("  Kok: " + root)

    if a.restore:
        return restore(root, a.restore)
    if not os.path.isdir(os.path.join(root, "splash_code")):
        print("splash_code/ yok")
        return 1
    if a.check:
        return check(root)

    hp = os.path.join(root, HTML_REL)
    if not os.path.isfile(hp):
        print("index.html yok")
        return 1

    src = rd(hp)
    src = strip_block(src, QUIET_MARK, QUIET_END)
    src = strip_block(src, MARK, END)

    src, n_greet = GREETING_RE.subn("", src)

    i = src.lower().rfind("</body>")
    if i < 0:
        print("</body> bulunamadi")
        return 2
    src = src[:i] + INJECT + src[i:]

    print("\n  Kaynak degisiklik : %d karsilama mesaji silindi" % n_greet)
    print("  054 select-avcisi : kaldirildi (sessiz politika 056'da yeniden)")
    print("\n  Plan:")
    print("    %-34s INJECT" % HTML_REL)
    print("    - dil secici: ozel listbox (arama + klavye + kendi scrollbar)")
    print("    - AI paneli: bos-durum ekrani, karsilama yok")
    print("    - AI resize: surukle / cift tik / klavye / hatirla")

    if a.dry_run:
        print("\n  --dry-run: temiz.")
        return 0

    zp = None
    if not a.no_backup:
        zp = backup(root)
        print("\n  Backup: %s" % zp)

    try:
        wr(hp, src)
        print("    + " + HTML_REL)
    except Exception as e:
        print("    YAZMA HATASI: %s" % e)
        if zp:
            restore(root, zp)
        return 1

    print("\n" + "=" * 62)
    print("  Patch %s UYGULANDI" % PATCH_ID)
    if zp:
        print("  Geri al: py path.py --restore \"%s\"" % zp)
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
