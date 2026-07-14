(function () {
  if (window.__primetentChatLoaded) return;
  window.__primetentChatLoaded = true;

  var _s = document.currentScript;
  if (!_s || !_s.src) {
    var _all = document.querySelectorAll("script[src]");
    for (var _i = 0; _i < _all.length; _i++) {
      if (/\/embed-primetent\.js(\?|$)/.test(_all[_i].src)) { _s = _all[_i]; break; }
    }
  }
  var ORIGIN = (_s && _s.src) ? _s.src.replace(/\/embed-primetent\.js(\?.*)?$/, "") : "";

  var style = document.createElement("style");
  style.textContent = [
    "#pt-chat-button{position:fixed;right:24px;bottom:24px;height:56px;border-radius:28px;",
    "background:#2f7fd1;color:#fff;border:none;cursor:pointer;white-space:nowrap;",
    "box-shadow:0 10px 30px rgba(0,0,0,.3);display:flex;align-items:center;gap:10px;padding:0 24px;",
    "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;font-size:15px;font-weight:600;line-height:1;",
    "z-index:2147483646;transition:transform .15s ease;animation:pt-pulse 2.6s ease-in-out infinite}",
    "#pt-chat-button:hover{transform:translateY(-2px)}",
    "#pt-chat-button svg{width:22px;height:22px;display:block;flex:none}",
    "@keyframes pt-pulse{0%,100%{box-shadow:0 10px 30px rgba(0,0,0,.3),0 0 0 0 rgba(47,127,209,.55)}",
    "50%{box-shadow:0 10px 30px rgba(0,0,0,.3),0 0 0 15px rgba(47,127,209,0)}}",
    "#pt-chat-window{position:fixed;right:24px;bottom:96px;width:384px;height:568px;",
    "max-height:calc(100vh - 128px);background:#fff;border-radius:14px;",
    "box-shadow:0 24px 60px rgba(0,0,0,.26);overflow:hidden;z-index:2147483645;",
    "transform:translateY(20px) scale(.96);opacity:0;pointer-events:none;",
    "transition:transform .22s ease,opacity .22s ease}",
    "#pt-chat-window.open{transform:translateY(0) scale(1);opacity:1;pointer-events:auto}",
    "#pt-chat-window iframe{width:100%;height:100%;border:0;display:block}",
    "@media (max-width:480px){#pt-chat-window{right:12px;left:12px;width:auto;bottom:88px}",
    "#pt-chat-button{right:16px;bottom:16px;height:52px;padding:0 20px;font-size:14px}}",
  ].join("");
  document.head.appendChild(style);

  var btn = document.createElement("button");
  btn.id = "pt-chat-button";
  btn.setAttribute("aria-label", "Задать вопрос помощнику");
  btn.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>' +
    "</svg><span>Задать вопрос</span>";

  var win = document.createElement("div");
  win.id = "pt-chat-window";
  var iframe = document.createElement("iframe");
  iframe.title = "Помощник ПРАЙМ-ТЕНТ";
  iframe.setAttribute("loading", "lazy");
  win.appendChild(iframe);

  var loaded = false;
  btn.addEventListener("click", function () {
    if (!loaded) {
      // источник: только origin+pathname, без query/fragment/userinfo (сервер валидирует повторно)
      var ref = (location.origin + location.pathname).slice(0, 300);
      iframe.src = ORIGIN + "/agent-primetent.html?ref=" + encodeURIComponent(ref);
      loaded = true;
    }
    win.classList.toggle("open");
  });

  document.body.appendChild(win);
  document.body.appendChild(btn);
})();
