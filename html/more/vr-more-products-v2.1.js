(function () {
  "use strict";

  var root = document.querySelector(".vr-more-page");
  if (!root) return;

  var apiBase = root.getAttribute("data-api-base") || "https://zr.jsss999.com/wp-json/wp/v2/posts";
  var categoryId = Number(root.getAttribute("data-category-id") || 66);
  var defaultPerPage = toPositiveInt(root.getAttribute("data-per-page"), 6, 1, 50);
  var defaultCover = root.getAttribute("data-default-cover") || "";
  var initialQuery = parseInitialQuery();

  var els = {
    meta: document.getElementById("vr-result-meta"),
    loading: document.getElementById("vr-loading"),
    error: document.getElementById("vr-error"),
    empty: document.getElementById("vr-empty"),
    grid: document.getElementById("vr-grid"),
    pagination: document.getElementById("vr-pagination")
  };

  var state = {
    page: initialQuery.page,
    perPage: initialQuery.perPage,
    pageParamKey: initialQuery.pageParamKey,
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

  function toPositiveInt(value, fallback, min, max) {
    var num = Number(value);
    if (!Number.isFinite(num) || num <= 0) return fallback;
    num = Math.floor(num);
    if (Number.isFinite(min) && num < min) return min;
    if (Number.isFinite(max) && num > max) return max;
    return num;
  }

  function parseInitialQuery() {
    var sp = new URLSearchParams(window.location.search);
    var pageKeys = ["vr_page", "pg", "page"];
    var page = 1;
    var pageParamKey = "vr_page";

    pageKeys.some(function (key) {
      var candidate = toPositiveInt(sp.get(key), null, 1, 9999);
      if (!candidate) return false;
      page = candidate;
      pageParamKey = key;
      return true;
    });

    var perPage = toPositiveInt(sp.get("per_page"), defaultPerPage, 1, 50);

    return {
      page: page,
      perPage: perPage,
      pageParamKey: pageParamKey
    };
  }

  function setQueryPage(page) {
    var url = new URL(window.location.href);
    var pageKeys = ["vr_page", "pg", "page"];
    var key = state.pageParamKey || "vr_page";

    if (!pageKeys.includes(key)) key = "vr_page";
    url.searchParams.set(key, String(page));

    pageKeys.forEach(function (k) {
      if (k !== key && url.searchParams.has(k)) {
        url.searchParams.set(k, String(page));
      }
    });

    if (url.searchParams.has("per_page")) {
      url.searchParams.set("per_page", String(state.perPage));
    }
    window.history.replaceState({}, "", url.toString());
  }

  function buildUrl(page) {
    var params = new URLSearchParams({
      categories: String(categoryId),
      per_page: String(state.perPage),
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
    var first = Array.isArray(media) ? media[0] : null;
    if (!first) return state.categoryImage || defaultCover;

    var sizes = first.media_details && first.media_details.sizes;
    if (sizes) {
      if (sizes.medium_large && sizes.medium_large.source_url) return sizes.medium_large.source_url;
      if (sizes.large && sizes.large.source_url) return sizes.large.source_url;
      if (sizes.medium && sizes.medium.source_url) return sizes.medium.source_url;
      if (sizes.full && sizes.full.source_url) return sizes.full.source_url;
    }

    if (first.source_url) return first.source_url;
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
    var start = state.total === 0 ? 0 : (state.page - 1) * state.perPage + 1;
    var end = Math.min(state.page * state.perPage, state.total);
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
        if (res.ok) {
          var total = Number(res.headers.get("X-WP-Total") || 0);
          var totalPages = Number(res.headers.get("X-WP-TotalPages") || 0);
          state.total = Number.isFinite(total) ? total : 0;
          state.totalPages = Number.isFinite(totalPages) ? totalPages : 0;
          return res.json();
        }

        return res
          .json()
          .catch(function () {
            return {};
          })
          .then(function (errBody) {
            var err = new Error("HTTP " + res.status);
            err.status = res.status;
            err.code = errBody && errBody.code ? errBody.code : "";
            throw err;
          });
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
        if (err && err.code === "rest_post_invalid_page_number" && state.page !== 1) {
          state.page = 1;
          setQueryPage(1);
          fetchAndRender(1);
          return;
        }
        showState("error", "列表加载失败（" + err.message + "），请刷新重试。");
      });
  }
})();
