(function () {
  "use strict";

  var sidebarHtml = '<div class="wpsidebar-fkf wpsidebar02"><ul class="fkf"><li class="fkf-item"><img src="https://static.jsss999.com/upload/zrsite/common/b7705060bd6d51bcb345c568b992f1835f56bf10a12f-XnFoLp_fw1200.png"><img class="hover" src="https://static.jsss999.com/upload/zrsite/common/b7705060bd6d51bcb345c568b992f1835f56bf10a12f-XnFoLp_fw1200.png"><div class="fkf-item-right"><div class="fkf-item-right-content right-content-tele"><img class="arrow" src="https://static.ysjianzhan.cn/website/plugin/sidebar/images/arrow-r.png"><div class="fkf-item-right-content-top"><img src="https://static.ysjianzhan.cn/website/plugin/sidebar/images/fkf-4.png" style="width:25px;height:25px;"><h2 class="txt_fam">180 6619 0606</h2><p class="txt_fam"></p></div><div class="fkf-item-right-content-top"><img src="https://static.ysjianzhan.cn/website/plugin/sidebar/images/fkf-4.png" style="width:25px;height:25px;"><h2 class="txt_fam">189 6208 2198</h2><p class="txt_fam"></p></div></div></div></li><li class="fkf-item"><img src="https://static.jsss999.com/upload/zrsite/common/20c08a0fe8953915c2f4fbe3f7013b9b1.jpg"><img class="hover" src="https://static.jsss999.com/upload/zrsite/common/20c08a0fe8953915c2f4fbe3f7013b9b1.jpg"><div class="fkf-item-right fkf-item-right-ewm"><div class="right-content-ewm"><img class="arrow" src="https://static.ysjianzhan.cn/website/plugin/sidebar/images/arrow-r.png"><div class="ewm"><div><img src="https://static.jsss999.com/upload/zrsite/common/1_moxe.jpg"></div><p>微信扫一扫</p></div><div class="ewm"><div><img src="https://static.jsss999.com/upload/zrsite/common/2_7gzi.jpg"></div><p>微信扫一扫</p></div></div></div></li><li class="fkf-item sgotop"><img src="https://static.ysjianzhan.cn/website/plugin/sidebar/images/fkf-8.png"><img class="hover" src="https://static.ysjianzhan.cn/website/plugin/sidebar/images/fkf-88.png"></li></ul></div>';
  var goTopSelector = [
    ".wpsidebar02 li.sgotop",
    ".wpsidebar02 li.sgotop img",
    ".wpsidebar03 .sgotop",
    ".wpsidebar03 .sgotop img",
    "li.sgotopdd",
    "li.sgotopdd img",
    ".wp_celan_content p.ptop"
  ].join(", ");

  function scrollToTopNow() {
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
    if (window.jQuery) {
      window.jQuery("html, body").stop(true).animate({ scrollTop: 0 }, 300);
    }
    if (window.scrollTo) {
      try {
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (_err) {
        window.scrollTo(0, 0);
      }
    }
  }

  function ensureAssets() {
    if (!document.querySelector("link[data-zr-sidebar02]")) {
      var link = document.createElement("link");
      link.rel = "stylesheet";
      link.type = "text/css";
      link.href = "https://static.jsss999.com/upload/zrsite/ai_platform/sidebar02.css";
      link.setAttribute("data-zr-sidebar02", "1");
      document.head.appendChild(link);
    }
    if (window.jQuery && !document.querySelector("script[data-zr-rightmenu]")) {
      var script = document.createElement("script");
      script.src = "https://static.jsss999.com/upload/zrsite/ai_platform/rightmenu.js";
      script.type = "text/javascript";
      script.setAttribute("data-zr-rightmenu", "1");
      document.body.appendChild(script);
    }
  }

  function ensureSidebarDom() {
    if (!document.querySelector(".wpsidebar02")) {
      document.body.insertAdjacentHTML("beforeend", sidebarHtml);
    }
  }

  function resetPanelDisplay(panel) {
    if (!panel) {
      return;
    }
    panel.style.removeProperty("display");
  }

  function clearInlinePanels(exceptPanel) {
    document.querySelectorAll(".wpsidebar02 .fkf-item-right").forEach(function (node) {
      if (node !== exceptPanel) {
        resetPanelDisplay(node);
      }
    });
  }

  function bindEventsOnce() {
    if (window.__zrCategorySidebarBound) return;
    window.__zrCategorySidebarBound = true;

    document.addEventListener("click", function (event) {
      var goTopTarget = event.target && event.target.closest ? event.target.closest(goTopSelector) : null;
      if (goTopTarget) {
        event.preventDefault();
        event.stopPropagation();
        scrollToTopNow();
        return;
      }

      var item = event.target && event.target.closest ? event.target.closest(".wpsidebar02 .fkf-item") : null;
      if (item) {
        if (item.classList.contains("sgotop")) return;
        var panel = item.querySelector(".fkf-item-right");
        if (!panel) return;
        event.preventDefault();
        event.stopPropagation();
        clearInlinePanels(panel);
        if (panel.style.display === "block") {
          resetPanelDisplay(panel);
        } else {
          panel.style.display = "block";
        }
        return;
      }

      if (!event.target.closest(".wpsidebar02 .fkf-item-right")) {
        clearInlinePanels();
      }
    }, true);
  }

  function initSidebar() {
    if (!document.body) return;
    ensureAssets();
    ensureSidebarDom();
    bindEventsOnce();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSidebar);
  } else {
    initSidebar();
  }
})();
