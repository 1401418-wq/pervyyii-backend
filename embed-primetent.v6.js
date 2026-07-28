(function () {
  if (window.__primetentChatLoaded) return;
  window.__primetentChatLoaded = true;

  var _s = document.currentScript;
  if (!_s || !_s.src) {
    var _all = document.querySelectorAll("script[src]");
    for (var _i = 0; _i < _all.length; _i++) {
      if (/\/embed-primetent(?:\.v[0-9]+)?\.js(\?|$)/.test(_all[_i].src)) { _s = _all[_i]; break; }
    }
  }
  var ORIGIN = (_s && _s.src) ? _s.src.replace(/\/embed-primetent(?:\.v[0-9]+)?\.js(\?.*)?$/, "") : "";
  // origin для сверки postMessage = только scheme://host (event.origin не содержит путь ORIGIN)
  var ALLOWED_ORIGIN = ORIGIN;
  try { ALLOWED_ORIGIN = new URL(ORIGIN, location.href).origin; } catch (_) {}
  var PT_EVENT_SESSION = "";
  try {
    PT_EVENT_SESSION = sessionStorage.getItem("pt_widget_sid") ||
      (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
    sessionStorage.setItem("pt_widget_sid", PT_EVENT_SESSION);
  } catch (_) { PT_EVENT_SESSION = String(Date.now()); }
  function ptEvent(name) {
    try {
      fetch(ORIGIN + "/widget-events", {method:"POST", mode:"cors",
        headers:{"Content-Type":"application/json"}, keepalive:true,
        body:JSON.stringify({client:"prime-tent", event:name,
          session_id:PT_EVENT_SESSION, page:location.origin + location.pathname})
      }).catch(function(){});
    } catch (_) {}
  }
  ptEvent("widget_loaded");

  // Цели Яндекс.Метрики: счётчик prime-tent.ru привязан к кампаниям Директа.
  // reachGoal зовём в контексте страницы сайта (здесь есть ym), не внутри iframe.
  var PT_COUNTER = 110782967;
  var PT_GOALS = {pt_assistant_open: 1, pt_assistant_message: 1, pt_assistant_lead: 1};
  function ptGoal(g) {
    if (!PT_GOALS[g]) return;
    if (typeof window.ym === "function") {
      try { window.ym(PT_COUNTER, "reachGoal", g); } catch (_) {}
    }
  }
  // Сигналы из iframe (agent-primetent.html): проверяем и origin, и сам источник —
  // иначе любой скрипт на странице клиента мог бы прислать {__ptGoal} и накрутить
  // конверсию, по которой оптимизируется Директ.
  window.addEventListener("message", function (e) {
    if (e.origin !== ALLOWED_ORIGIN || !e.data) return;
    if (!iframe || e.source !== iframe.contentWindow) return;
    if (e.data.__ptGoal) ptGoal(e.data.__ptGoal);
  });

  var style = document.createElement("style");
  style.textContent = [
    "#pt-chat-button{position:fixed;right:24px;bottom:24px;",
    "background:#d13b30;color:#fff;border:0;cursor:pointer;white-space:nowrap;",
    "display:flex;align-items:center;gap:12px;padding:9px 22px 9px 9px;border-radius:44px;",
    "font-family:var(--disp,'Oswald','Arial Narrow',sans-serif);text-transform:uppercase;letter-spacing:.05em;font-weight:600;font-size:15px;line-height:1;",
    "box-shadow:0 8px 26px rgba(209,59,48,.5);z-index:2147483646;transition:transform .15s ease;animation:pt-pulse 2.6s ease-in-out infinite}",
    "#pt-chat-button:hover{transform:translateY(-2px)}",
    "#pt-chat-button img{height:36px;width:auto;border-radius:8px;background:#fff;padding:4px 5px;box-shadow:0 2px 8px rgba(0,0,0,.25);flex:0 0 auto;display:block}",
    "@keyframes pt-pulse{0%,100%{box-shadow:0 8px 26px rgba(209,59,48,.5),0 0 0 0 rgba(209,59,48,.5)}",
    "50%{box-shadow:0 8px 26px rgba(209,59,48,.5),0 0 0 16px rgba(209,59,48,0)}}",
    "#pt-chat-window{position:fixed;right:24px;bottom:96px;width:384px;height:568px;",
    "max-height:calc(100vh - 128px);background:#fff;border-radius:14px;",
    "box-shadow:0 24px 60px rgba(0,0,0,.26);overflow:hidden;z-index:2147483645;",
    "transform:translateY(20px) scale(.96);opacity:0;pointer-events:none;",
    "transition:transform .22s ease,opacity .22s ease}",
    "#pt-chat-window.open{transform:translateY(0) scale(1);opacity:1;pointer-events:auto}",
    "#pt-chat-window iframe{width:100%;height:100%;border:0;display:block}",
    "@media (max-width:480px){#pt-chat-window{right:12px;left:12px;width:auto;bottom:88px}",
    "#pt-chat-button{right:16px;bottom:16px;padding:8px 18px 8px 8px;font-size:14px}}",
  ].join("");
  document.head.appendChild(style);

  var btn = document.createElement("button");
  btn.id = "pt-chat-button";
  btn.setAttribute("aria-label", "Задать вопрос помощнику");
  btn.innerHTML =
    '<img src="https://prime-tent.ru/assets/logo_prime_tent.gif" alt="">' +
    "<span>Задать вопрос</span>";

  var win = document.createElement("div");
  win.id = "pt-chat-window";
  var iframe = document.createElement("iframe");
  iframe.title = "Помощник ПРАЙМ-ТЕНТ";
  iframe.setAttribute("loading", "lazy");
  win.appendChild(iframe);

  var loaded = false;
  btn.addEventListener("click", function () {
    ptEvent("widget_opened");
    if (!loaded) {
      // источник: только origin+pathname, без query/fragment/userinfo (сервер валидирует повторно)
      var ref = (location.origin + location.pathname).slice(0, 300);
      iframe.src = ORIGIN + "/agent-primetent.html?ref=" + encodeURIComponent(ref);
      loaded = true;
    }
    win.classList.toggle("open");
    if (win.classList.contains("open")) ptGoal("pt_assistant_open");
  });

  document.body.appendChild(win);
  document.body.appendChild(btn);
})();
