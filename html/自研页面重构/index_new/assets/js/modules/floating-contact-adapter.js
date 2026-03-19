export function initFloatingContactAdapter(mountEl) {
  if (!mountEl) {
    return;
  }

  const SIDEBAR_CSS = "https://static.ysjianzhan.cn/website/plugin/sidebar/css/sidebar.css?v=16860282";
  const SIDEBAR_THEME_CSS = "https://static.jsss999.com/upload/zrsite/ai_platform/sidebar02.css";

  const sidebarHtml = '<div class="wpsidebar-fkf wpsidebar02"><ul class="fkf"><li class="fkf-item"><img src="https://static.jsss999.com/upload/zrsite/common/b7705060bd6d51bcb345c568b992f1835f56bf10a12f-XnFoLp_fw1200.png"><img class="hover" src="https://static.jsss999.com/upload/zrsite/common/b7705060bd6d51bcb345c568b992f1835f56bf10a12f-XnFoLp_fw1200.png"><div class="fkf-item-right"><div class="fkf-item-right-content right-content-tele"><img class="arrow" src="https://static.ysjianzhan.cn/website/plugin/sidebar/images/arrow-r.png"><div class="fkf-item-right-content-top"><img src="https://static.ysjianzhan.cn/website/plugin/sidebar/images/fkf-4.png" style="width:25px;height:25px;"><h2 class="txt_fam">180 6619 0606</h2><p class="txt_fam"></p></div><div class="fkf-item-right-content-top"><img src="https://static.ysjianzhan.cn/website/plugin/sidebar/images/fkf-4.png" style="width:25px;height:25px;"><h2 class="txt_fam">189 6208 2198</h2><p class="txt_fam"></p></div></div></div></li><li class="fkf-item"><img src="https://static.jsss999.com/upload/zrsite/common/20c08a0fe8953915c2f4fbe3f7013b9b1.jpg"><img class="hover" src="https://static.jsss999.com/upload/zrsite/common/20c08a0fe8953915c2f4fbe3f7013b9b1.jpg"><div class="fkf-item-right fkf-item-right-ewm"><div class="right-content-ewm"><img class="arrow" src="https://static.ysjianzhan.cn/website/plugin/sidebar/images/arrow-r.png"><div class="ewm"><div><img src="https://static.jsss999.com/upload/zrsite/common/1_moxe.jpg"></div><p>微信扫一扫</p></div><div class="ewm"><div><img src="https://static.jsss999.com/upload/zrsite/common/2_7gzi.jpg"></div><p>微信扫一扫</p></div></div></div></li><li class="fkf-item sgotop"><img src="https://static.ysjianzhan.cn/website/plugin/sidebar/images/fkf-8.png"><img class="hover" src="https://static.ysjianzhan.cn/website/plugin/sidebar/images/fkf-88.png"></li></ul></div>';

  const goTopSelector = [
    ".wpsidebar02 li.sgotop",
    ".wpsidebar02 li.sgotop img",
    ".wpsidebar03 .sgotop",
    ".wpsidebar03 .sgotop img",
    "li.sgotopdd",
    "li.sgotopdd img",
    ".wp_celan_content p.ptop"
  ].join(", ");

  function ensureStyleTag() {
    if (document.querySelector("style[data-zr-sidebar-inline='1']")) return;
    const style = document.createElement("style");
    style.setAttribute("data-zr-sidebar-inline", "1");
    style.textContent =
      ".wpsidebar-fkf.wpsidebar02 .fkf{margin:0!important;padding:0!important;list-style:none!important;}" +
      ".wpsidebar-fkf.wpsidebar02 .fkf>li{list-style:none!important;}" +
      ".wpsidebar-fkf.wpsidebar02{left:18px!important;right:auto!important;z-index:99999!important;}" +
      ".wpsidebar-fkf.wpsidebar02 .fkf-item-right{right:auto;left:35px;padding-right:0;padding-left:25px;}" +
      ".wpsidebar-fkf.wpsidebar02 .fkf-item-right-content .arrow,.wpsidebar-fkf.wpsidebar02 .right-content-ewm .arrow{right:auto;left:-15px;transform:rotate(180deg);}" +
      ".wpsidebar-fkf.wpsidebar02 .fkf-item-right-ewm{top:initial;bottom:-15px;}" +
      ".wpsidebar-fkf.wpsidebar02,.wpsidebar-fkf.wpsidebar02 .fkf-item,.wpsidebar-fkf.wpsidebar02 .fkf-item img{pointer-events:auto;}";
    document.head.appendChild(style);
  }

  function ensureLink(href, marker) {
    if (document.querySelector(`link[${marker}]`)) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.type = "text/css";
    link.href = href;
    link.setAttribute(marker, "1");
    document.head.appendChild(link);
  }

  function scrollToTopNow() {
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
    if (window.scrollTo) {
      try {
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (err) {
        window.scrollTo(0, 0);
      }
    }
    if (window.jQuery) {
      window.jQuery("html, body").stop(true).animate({ scrollTop: 0 }, 300);
    }
  }

  function ensureSidebarDom() {
    if (document.querySelector(".wpsidebar02")) return;
    document.body.insertAdjacentHTML("beforeend", sidebarHtml);
  }

  function bindEventsOnce() {
    if (window.__zrSidebarBound) return;
    window.__zrSidebarBound = true;

    document.addEventListener(
      "click",
      (e) => {
        const target = e.target;
        if (!(target instanceof Element)) return;

        const goTopTarget = target.closest(goTopSelector);
        if (goTopTarget) {
          e.preventDefault();
          e.stopPropagation();
          scrollToTopNow();
          return;
        }

        const item = target.closest(".wpsidebar02 .fkf-item");
        if (item) {
          if (item.classList.contains("sgotop")) return;
          const panel = item.querySelector(".fkf-item-right");
          if (!panel) return;
          e.preventDefault();
          e.stopPropagation();
          document.querySelectorAll(".wpsidebar02 .fkf-item-right").forEach((p) => {
            if (p !== panel) p.style.display = "none";
          });
          panel.style.display = panel.style.display === "none" || panel.style.display === "" ? "block" : "none";
          return;
        }

        if (!target.closest(".wpsidebar02 .fkf-item-right")) {
          document.querySelectorAll(".wpsidebar02 .fkf-item-right").forEach((p) => {
            p.style.display = "none";
          });
        }
      },
      true
    );
  }

  mountEl.setAttribute("data-floating-adapter", "mounted");
  mountEl.innerHTML = "";
  ensureStyleTag();
  ensureLink(SIDEBAR_CSS, "data-zr-sidebar-css");
  ensureLink(SIDEBAR_THEME_CSS, "data-zr-sidebar-theme");
  ensureSidebarDom();
  bindEventsOnce();
}
