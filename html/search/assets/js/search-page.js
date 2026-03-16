(function (global) {
  "use strict";

  var refs = {
    root: document.querySelector(".zr-search-app"),
    form: document.getElementById("zr-search-form"),
    keyword: document.getElementById("zr-search-keyword"),
    summary: document.getElementById("zr-search-summary"),
    loading: document.getElementById("zr-search-loading"),
    error: document.getElementById("zr-search-error"),
    empty: document.getElementById("zr-search-empty"),
    results: document.getElementById("zr-search-results"),
    pagination: document.getElementById("zr-search-pagination")
  };

  function hasQueryValue(value) {
    return value !== null && value !== undefined && String(value).trim() !== "";
  }

  function decodeQueryValue(value) {
    var normalized = String(value || "").replace(/\+/g, "%20");
    try {
      return decodeURIComponent(normalized);
    } catch (_error) {
      return String(value || "");
    }
  }

  function getKeywordFromSearch() {
    var params = new URLSearchParams(global.location.search || "");
    var raw = params.get("q");
    if (!hasQueryValue(raw)) {
      raw = params.get("s");
    }
    return hasQueryValue(raw) ? decodeQueryValue(raw) : "";
  }

  function getPageFromSearch() {
    var params = new URLSearchParams(global.location.search || "");
    var value = Number(params.get("page") || "1");
    return Number.isInteger(value) && value > 0 ? value : 1;
  }

  function getPageSize() {
    var raw = refs.root && refs.root.getAttribute("data-page-size");
    var value = Number(raw || "10");
    return Number.isInteger(value) && value > 0 ? value : 10;
  }

  function getApiBase() {
    return (refs.root && refs.root.getAttribute("data-api-base")) || "https://www.zgzonre.com/wp-json/wp/v2/";
  }

  function getDetailBaseUrl() {
    return (refs.root && refs.root.getAttribute("data-detail-url")) || "https://www.zgzonre.com/detail-base";
  }

  function getDefaultCover() {
    return (
      (refs.root && refs.root.getAttribute("data-default-cover")) ||
      "https://www.zgzonre.com/wp-content/uploads/2026/03/wysm.png"
    );
  }

  function stripHtml(input) {
    var box = document.createElement("div");
    box.innerHTML = input || "";
    return (box.textContent || "").replace(/\s+/g, " ").trim();
  }

  function formatDate(input) {
    if (!input) {
      return "";
    }

    var date = new Date(input);
    if (Number.isNaN(date.getTime())) {
      return String(input);
    }

    return (
      date.getFullYear() +
      "年" +
      String(date.getMonth() + 1) +
      "月" +
      String(date.getDate()) +
      "日 " +
      String(date.getHours()).padStart(2, "0") +
      ":" +
      String(date.getMinutes()).padStart(2, "0")
    );
  }

  function buildDetailUrl(postId) {
    var url = new URL(getDetailBaseUrl(), global.location.href);
    url.searchParams.set("article_id", String(postId));
    return url.href;
  }

  function getFeaturedImage(post) {
    var media = post &&
      post._embedded &&
      post._embedded["wp:featuredmedia"] &&
      post._embedded["wp:featuredmedia"][0];

    return (media && media.source_url) || getDefaultCover();
  }

  function getCategoryNames(post) {
    var groups = (post && post._embedded && post._embedded["wp:term"]) || [];
    var categoryGroup = Array.isArray(groups[0]) ? groups[0] : [];

    return categoryGroup
      .map(function (item) {
        return item && item.name ? String(item.name).trim() : "";
      })
      .filter(Boolean)
      .slice(0, 3);
  }

  function createResultCard(post) {
    var article = document.createElement("article");
    article.className = "zr-search-card";

    var link = document.createElement("a");
    link.className = "zr-search-card-link";
    link.href = buildDetailUrl(post.id);

    var media = document.createElement("div");
    media.className = "zr-search-card-media";

    var image = document.createElement("img");
    image.className = "zr-search-card-image";
    image.src = getFeaturedImage(post);
    image.alt = stripHtml(post.title && post.title.rendered) || "搜索结果封面";
    image.loading = "lazy";
    media.appendChild(image);

    var body = document.createElement("div");
    body.className = "zr-search-card-body";

    var title = document.createElement("h3");
    title.className = "zr-search-card-title";
    title.textContent = stripHtml(post.title && post.title.rendered) || "未命名文章";
    body.appendChild(title);

    var meta = document.createElement("div");
    meta.className = "zr-search-card-meta";

    var date = document.createElement("span");
    date.textContent = formatDate(post.date);
    meta.appendChild(date);

    var categoryNames = getCategoryNames(post);
    if (categoryNames.length) {
      var category = document.createElement("span");
      category.textContent = categoryNames.join(" / ");
      meta.appendChild(category);
    }
    body.appendChild(meta);

    var excerptText = stripHtml(post.excerpt && post.excerpt.rendered);
    if (excerptText) {
      var excerpt = document.createElement("p");
      excerpt.className = "zr-search-card-excerpt";
      excerpt.textContent = excerptText;
      body.appendChild(excerpt);
    } else {
      article.classList.add("is-no-excerpt");
    }

    var action = document.createElement("span");
    action.className = "zr-search-card-action";
    action.textContent = "查看详情";
    body.appendChild(action);

    link.appendChild(media);
    link.appendChild(body);
    article.appendChild(link);

    return article;
  }

  function createPageButton(label, page, isCurrent, isDisabled, keyword) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "zr-search-page-button";
    button.textContent = label;

    if (isCurrent) {
      button.classList.add("is-current");
      button.setAttribute("aria-current", "page");
    }

    if (isDisabled) {
      button.disabled = true;
    } else {
      button.addEventListener("click", function () {
        navigate(keyword, page);
      });
    }

    return button;
  }

  function buildVisiblePages(currentPage, totalPages) {
    var pages = [];
    var start = Math.max(1, currentPage - 2);
    var end = Math.min(totalPages, currentPage + 2);

    if (start > 1) {
      pages.push(1);
    }
    if (start > 2) {
      pages.push("ellipsis-start");
    }

    for (var page = start; page <= end; page += 1) {
      pages.push(page);
    }

    if (end < totalPages - 1) {
      pages.push("ellipsis-end");
    }
    if (end < totalPages) {
      pages.push(totalPages);
    }

    return pages;
  }

  function renderPagination(keyword, currentPage, totalPages) {
    refs.pagination.innerHTML = "";

    if (totalPages <= 1) {
      refs.pagination.hidden = true;
      return;
    }

    refs.pagination.hidden = false;
    refs.pagination.appendChild(
      createPageButton("上一页", currentPage - 1, false, currentPage <= 1, keyword)
    );

    buildVisiblePages(currentPage, totalPages).forEach(function (entry) {
      if (typeof entry === "string") {
        var gap = document.createElement("span");
        gap.className = "zr-search-page-gap";
        gap.textContent = "...";
        refs.pagination.appendChild(gap);
        return;
      }

      refs.pagination.appendChild(
        createPageButton(String(entry), entry, entry === currentPage, false, keyword)
      );
    });

    refs.pagination.appendChild(
      createPageButton("下一页", currentPage + 1, false, currentPage >= totalPages, keyword)
    );
  }

  function showLoading(keyword) {
    refs.loading.hidden = false;
    refs.error.hidden = true;
    refs.empty.hidden = true;
    refs.results.hidden = true;
    refs.pagination.hidden = true;
    refs.summary.textContent = keyword ? "正在搜索 “" + keyword + "” ..." : "请输入关键词开始搜索。";
  }

  function showError(message) {
    refs.loading.hidden = true;
    refs.results.hidden = true;
    refs.pagination.hidden = true;
    refs.empty.hidden = true;
    refs.error.hidden = false;
    refs.error.textContent = message;
  }

  function showEmpty(keyword) {
    refs.loading.hidden = true;
    refs.results.hidden = true;
    refs.pagination.hidden = true;
    refs.error.hidden = true;
    refs.empty.hidden = false;
    refs.empty.textContent = keyword ? "没有找到与 “" + keyword + "” 相关的内容。" : "请输入关键词开始搜索。";
  }

  function navigate(keyword, page) {
    var url = new URL(global.location.href);
    if (hasQueryValue(keyword)) {
      url.searchParams.set("q", String(keyword).trim());
      url.searchParams.set("page", String(page || 1));
    } else {
      url.searchParams.delete("q");
      url.searchParams.delete("page");
      url.searchParams.delete("s");
    }
    global.location.href = url.href;
  }

  function updateDocumentTitle(keyword, total) {
    if (!hasQueryValue(keyword)) {
      document.title = "站内搜索 - 江苏中热机械设备有限公司";
      return;
    }

    document.title =
      "搜索 “" + String(keyword).trim() + "”" +
      (total > 0 ? "（" + total + "）" : "") +
      " - 江苏中热机械设备有限公司";
  }

  async function loadSearchResults() {
    var keyword = getKeywordFromSearch();
    var page = getPageFromSearch();
    var pageSize = getPageSize();

    if (refs.keyword) {
      refs.keyword.value = keyword;
    }

    if (!hasQueryValue(keyword)) {
      updateDocumentTitle("", 0);
      showEmpty("");
      return;
    }

    showLoading(keyword);

    try {
      var payload = await global.SearchCenterApi.fetchPosts(getApiBase(), keyword, page, pageSize);
      var items = Array.isArray(payload.items) ? payload.items : [];
      var total = Number(payload.total) || 0;
      var totalPages = Number(payload.totalPages) || 0;

      updateDocumentTitle(keyword, total);
      refs.summary.textContent =
        "关键词 “" + keyword + "” 共找到 " + total + " 条结果，第 " + page + " / " + Math.max(totalPages, 1) + " 页。";

      if (!items.length) {
        showEmpty(keyword);
        return;
      }

      refs.results.innerHTML = "";
      items.forEach(function (item) {
        refs.results.appendChild(createResultCard(item));
      });

      refs.loading.hidden = true;
      refs.error.hidden = true;
      refs.empty.hidden = true;
      refs.results.hidden = false;
      renderPagination(keyword, page, totalPages);
    } catch (error) {
      if (error && Number(error.status) === 400 && page > 1) {
        navigate(keyword, 1);
        return;
      }

      showError("搜索结果加载失败，请稍后重试。");
      console.error(error);
    }
  }

  function bindForm() {
    if (!refs.form) {
      return;
    }

    refs.form.addEventListener("submit", function (event) {
      event.preventDefault();
      navigate(refs.keyword ? refs.keyword.value : "", 1);
    });
  }

  bindForm();
  loadSearchResults();
})(window);
