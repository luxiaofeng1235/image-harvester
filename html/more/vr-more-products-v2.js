(function () {
  "use strict";

  var root = document.querySelector(".vr-more-page");
  if (!root) return;

  var apiBase = root.getAttribute("data-api-base") || "https://zr.jsss999.com/wp-json/wp/v2/posts";
  var categoryId = Number(root.getAttribute("data-category-id") || 66);
  var perPage = Number(root.getAttribute("data-per-page") || 6);
  var defaultCover = root.getAttribute("data-default-cover") || "";

  var els = {
    meta: document.getElementById("vr-result-meta"),
    loading: document.getElementById("vr-loading"),
    error: document.getElementById("vr-error"),
    empty: document.getElementById("vr-empty"),
    grid: document.getElementById("vr-grid"),
    pagination: document.getElementById("vr-pagination")
  };

  var state = {
    page: getInitialPage(),
    total: 0,
    totalPages: 0,
    categoryName: "VR展示",
    categoryImage: defaultCover
  };

  init();

  function init() {
    fetchCategoryInfo();
    fetchAndRender(state.page);
  }

  function getInitialPage() {
    var sp = new URLSearchParams(window.location.search);
    var p = Number(sp.get("vr_page") || 1);
    return Number.isFinite(p) && p > 0 ? p : 1;
  }

  function setQueryPage(page) {
    var url = new URL(window.location.href);
    url.searchParams.set("vr_page", String(page));
    window.history.replaceState({}, "", url.toString());
  }

  function buildUrl(page) {
    var params = new URLSearchParams({
      categories: String(categoryId),
      per_page: String(perPage),
      page: String(page),
      orderby: "date",
      order: "desc",
      _embed: "1"
    });
    return apiBase + "?" + params.toString();
  }

  function decodeHTML(value) {
    var t = document.createElement("textarea");
    t.innerHTML = value || "";
    return t.value;
  }

  function stripHTML(html) {
    var d = document.createElement("div");
    d.innerHTML = html || "";
    return (d.textContent || d.innerText || "").trim();
  }

  function formatDate(iso) {
    var dt = new Date(iso);
    if (Number.isNaN(dt.getTime())) return "";
    return dt.toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    });
  }

  function pickCover(post) {
    var media = post && post._embedded && post._embedded["wp:featuredmedia"];
    if (Array.isArray(media) && media[0] && media[0].source_url) return media[0].source_url;
    return state.categoryImage || defaultCover;
  }

  function extractVrUrl(post) {
    var html = post && post.content && post.content.rendered ? post.content.rendered : "";
    var match = html.match(/<iframe[^>]+src=["']([^"']+)["']/i);
    return match && match[1] ? match[1] : "";
  }

  function showState(name, errorText) {
    els.loading.hidden = name !== "loading";
    els.error.hidden = name !== "error";
    els.empty.hidden = name !== "empty";
    els.grid.hidden = name !== "grid";
    els.pagination.hidden = name !== "grid";
    if (name === "error") {
      els.error.textContent = errorText || "列表加载失败，请稍后重试。";
    }
  }

  function renderCards(items) {
    els.grid.innerHTML = "";

    items.forEach(function (post) {
      var a = document.createElement("a");
      a.className = "vr-card";
      a.href = post.link;
      a.target = "_self";
      a.rel = "noopener";

      var img = document.createElement("img");
      img.className = "vr-card-cover";
      img.loading = "lazy";
      img.alt = decodeHTML(post.title && post.title.rendered);
      img.src = pickCover(post);

      var body = document.createElement("div");
      body.className = "vr-card-body";

      var title = document.createElement("h3");
      title.className = "vr-card-title";
      title.textContent = decodeHTML(post.title && post.title.rendered) || "未命名文章";

      var meta = document.createElement("p");
      meta.className = "vr-card-meta";
      var vrUrl = extractVrUrl(post);
      var dateText = formatDate(post.date);
      meta.textContent = vrUrl ? (dateText + " · VR链接已配置") : (dateText + " · 文章页");

      var action = document.createElement("div");
      action.className = "vr-card-action";
      action.textContent = "查看展厅 >";

      body.appendChild(title);
      body.appendChild(meta);
      body.appendChild(action);

      a.appendChild(img);
      a.appendChild(body);

      els.grid.appendChild(a);
    });
  }

  function renderPagination() {
    var page = state.page;
    var totalPages = state.totalPages;

    els.pagination.innerHTML = "";
    if (!totalPages || totalPages <= 1) {
      return;
    }

    var prevBtn = createPageBtn("上一页", page - 1, page <= 1);
    els.pagination.appendChild(prevBtn);

    var start = Math.max(1, page - 2);
    var end = Math.min(totalPages, page + 2);

    if (start > 1) {
      els.pagination.appendChild(createPageBtn("1", 1, false, page === 1));
      if (start > 2) {
        els.pagination.appendChild(createDots());
      }
    }

    for (var i = start; i <= end; i += 1) {
      els.pagination.appendChild(createPageBtn(String(i), i, false, i === page));
    }

    if (end < totalPages) {
      if (end < totalPages - 1) {
        els.pagination.appendChild(createDots());
      }
      els.pagination.appendChild(createPageBtn(String(totalPages), totalPages, false, page === totalPages));
    }

    var nextBtn = createPageBtn("下一页", page + 1, page >= totalPages);
    els.pagination.appendChild(nextBtn);
  }

  function createDots() {
    var span = document.createElement("span");
    span.className = "vr-page-btn";
    span.textContent = "...";
    span.setAttribute("aria-hidden", "true");
    span.style.pointerEvents = "none";
    span.style.background = "#f7f9fc";
    span.style.color = "#9aa4b2";
    return span;
  }

  function createPageBtn(text, targetPage, disabled, isActive) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "vr-page-btn" + (isActive ? " is-active" : "");
    btn.textContent = text;
    btn.disabled = !!disabled;
    btn.setAttribute("data-page", String(targetPage));
    btn.addEventListener("click", function () {
      if (btn.disabled || targetPage === state.page) return;
      fetchAndRender(targetPage);
    });
    return btn;
  }

  function updateMeta() {
    if (!els.meta) return;
    var start = state.total === 0 ? 0 : (state.page - 1) * perPage + 1;
    var end = Math.min(state.page * perPage, state.total);
    els.meta.textContent = state.categoryName + " · 共 " + state.total + " 篇，当前显示 " + start + "-" + end;
  }

  function fetchCategoryInfo() {
    var url = "https://zr.jsss999.com/wp-json/wp/v2/categories/" + categoryId;
    fetch(url)
      .then(function (res) {
        if (!res.ok) return null;
        return res.json();
      })
      .then(function (cat) {
        if (!cat) return;
        state.categoryName = cat.name || state.categoryName;
        state.categoryImage = cat.z_taxonomy_image_url || state.categoryImage;
        updateMeta();
      })
      .catch(function () {
        /* ignore category meta fail */
      });
  }

  function fetchAndRender(page) {
    state.page = page;
    setQueryPage(page);
    showState("loading");

    fetch(buildUrl(page))
      .then(function (res) {
        if (!res.ok) {
          throw new Error("HTTP " + res.status);
        }
        var total = Number(res.headers.get("X-WP-Total") || 0);
        var totalPages = Number(res.headers.get("X-WP-TotalPages") || 0);
        state.total = Number.isFinite(total) ? total : 0;
        state.totalPages = Number.isFinite(totalPages) ? totalPages : 0;
        return res.json();
      })
      .then(function (items) {
        updateMeta();
        if (!Array.isArray(items) || items.length === 0) {
          showState("empty");
          return;
        }
        renderCards(items);
        renderPagination();
        showState("grid");
      })
      .catch(function (err) {
        showState("error", "列表加载失败（" + err.message + "），请刷新重试。");
      });
  }
})();
