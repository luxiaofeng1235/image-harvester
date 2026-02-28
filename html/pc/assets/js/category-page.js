(function (global) {
  "use strict";

  var state = {
    config: null,
    type: "1",
    sub: null,
    page: 1,
    perPage: 9,
    total: 0,
    totalPages: 0,
    controller: null,
    scenesRendered: false,
    topHeroRendered: false
  };

  var refs = {
    root: document.querySelector(".category-page"),
    topHeroBg: document.getElementById("top-hero-bg"),
    sceneTopImage: document.getElementById("scene-top-image"),
    mainTabs: document.getElementById("main-category-tabs"),
    subTabs: document.getElementById("sub-category-tabs"),
    highlightImage: document.getElementById("highlight-image"),
    highlightTitle: document.getElementById("highlight-title"),
    highlightCopy: document.getElementById("highlight-copy"),
    sceneGrid: document.getElementById("scene-grid"),
    resultMeta: document.getElementById("result-meta"),
    loadingState: document.getElementById("loading-state"),
    errorState: document.getElementById("error-state"),
    emptyState: document.getElementById("empty-state"),
    productGrid: document.getElementById("product-grid"),
    pagination: document.getElementById("pagination")
  };

  function getConfigUrl() {
    return (
      (refs.root && refs.root.getAttribute("data-config-url")) ||
      "./config/home-category-content-config.json"
    );
  }

  function getApiBase() {
    return (
      (refs.root && refs.root.getAttribute("data-api-base")) ||
      "https://zr.jsss999.com/wp-json/wp/v2/posts"
    );
  }

  function toPositiveInt(value, fallback) {
    var num = Number(value);
    if (!Number.isInteger(num) || num <= 0) return fallback;
    return num;
  }

  function parseUrlState(search) {
    var params = new URLSearchParams(search || "");
    return {
      type: params.get("type") || "1",
      sub: params.get("sub") ? toPositiveInt(params.get("sub"), null) : null,
      page: toPositiveInt(params.get("page"), 1)
    };
  }

  function extractSummary(copy) {
    if (!copy) return "";
    if (typeof copy === "string") return copy;
    if (typeof copy === "object") {
      if (copy.summary) return copy.summary;
      if (Array.isArray(copy.paragraphs) && copy.paragraphs[0]) return copy.paragraphs[0];
    }
    return "";
  }

  function getCategoryByType(type) {
    var map = state.config.typeCategoryMap || {};
    var item = map[type] || map["1"];
    if (!item) return null;

    return state.config.categories.find(function (cat) {
      return cat.categoryKey === item.categoryKey;
    }) || null;
  }

  function getActiveCategory() {
    return getCategoryByType(state.type);
  }

  function getActiveSubCategory() {
    var category = getActiveCategory();
    if (!category || !state.sub) return null;

    return category.subCategories.find(function (item) {
      return Number(item.wpCategoryId) === Number(state.sub);
    }) || null;
  }

  function normalizeState() {
    var typeMap = state.config.typeCategoryMap || {};
    if (!typeMap[state.type]) {
      state.type = "1";
    }

    var activeCategory = getActiveCategory();
    if (!activeCategory) return;

    var validSubIds = new Set(
      (activeCategory.subCategories || []).map(function (item) {
        return Number(item.wpCategoryId);
      })
    );

    if (!state.sub || !validSubIds.has(Number(state.sub))) {
      state.sub = null;
    }

    state.page = toPositiveInt(state.page, 1);
  }

  function syncUrl(replace) {
    var params = new URLSearchParams();
    params.set("type", String(state.type));
    if (state.sub) params.set("sub", String(state.sub));
    if (state.page > 1) params.set("page", String(state.page));

    var nextUrl = window.location.pathname + "?" + params.toString();
    if (replace) {
      window.history.replaceState(null, "", nextUrl);
    } else {
      window.history.pushState(null, "", nextUrl);
    }
  }

  function getRequestCategories() {
    var sub = getActiveSubCategory();
    if (sub) return [Number(sub.wpCategoryId)];

    var category = getActiveCategory();
    return Array.isArray(category && category.wpChildCategoryIds) ? category.wpChildCategoryIds : [];
  }

  function renderFixedAssets() {
    if (!state.topHeroRendered && refs.topHeroBg && state.config.topBannerBg) {
      refs.topHeroBg.style.backgroundImage = "url('" + state.config.topBannerBg + "')";
      state.topHeroRendered = true;
    }

    if (refs.sceneTopImage) {
      var sceneTopImageUrl =
        state.config.applicationTopImage ||
        "https://static.jsss999.com/upload/zrsite/common/VCG41N867423914.jpg";
      refs.sceneTopImage.src = sceneTopImageUrl;
    }

    if (!state.scenesRendered) {
      global.CategoryRender.renderSceneImages(
        refs.sceneGrid,
        state.config.applicationScenes || [],
        state.config.applicationSceneLabels || []
      );
      state.scenesRendered = true;
    }
  }

  function renderStaticBlocks() {
    var categories = (state.config.categories || []).slice().sort(function (a, b) {
      return Number(a.type || 0) - Number(b.type || 0);
    });

    global.CategoryRender.renderMainCategoryTabs(refs.mainTabs, categories, state.type, function (nextType) {
      if (String(nextType) === String(state.type)) return;
      state.type = String(nextType);
      state.sub = null;
      state.page = 1;
      loadProducts({ syncHistory: true, replaceHistory: false });
    });

    var activeCategory = getActiveCategory();
    var activeSub = getActiveSubCategory();

    global.CategoryRender.renderSubCategoryTabs(
      refs.subTabs,
      activeCategory ? activeCategory.subCategories : [],
      state.sub,
      function (nextSubId) {
        var parsedSub = Number(nextSubId);
        if (!Number.isInteger(parsedSub)) return;
        if (Number(state.sub) === parsedSub) return;

        state.sub = parsedSub;
        state.page = 1;
        loadProducts({ syncHistory: true, replaceHistory: false });
      }
    );

    var highlightTitle = activeSub
      ? (activeSub.shortName || activeSub.name)
      : (activeCategory.categoryDisplayName || activeCategory.categoryName);

    var highlightCopy = activeSub
      ? extractSummary(activeSub.defaultCopy)
      : extractSummary(activeCategory.defaultCopy);

    var highlightImage = activeSub && activeSub.imageUrl
      ? activeSub.imageUrl
      : (activeCategory.defaultImage || "");

    global.CategoryRender.renderHighlight(refs, {
      title: highlightTitle,
      copy: highlightCopy,
      imageUrl: highlightImage
    });

    renderFixedAssets();
  }

  async function loadProducts(options) {
    var opts = options || {};

    normalizeState();
    renderStaticBlocks();

    if (opts.syncHistory) {
      syncUrl(!!opts.replaceHistory);
    }

    if (state.controller) {
      state.controller.abort();
    }

    state.controller = new AbortController();
    var signal = state.controller.signal;

    global.CategoryRender.renderStatus(refs, {
      loading: true,
      error: "",
      empty: false
    });

    try {
      var categories = getRequestCategories();
      var result = await global.CategoryApi.fetchPosts({
        apiBase: getApiBase(),
        categories: categories,
        page: state.page,
        perPage: state.perPage,
        signal: signal
      });

      if (signal.aborted) return;

      state.total = result.total;
      state.totalPages = result.totalPages || 1;

      if (state.page > state.totalPages) {
        state.page = state.totalPages;
        return loadProducts({ syncHistory: true, replaceHistory: true });
      }

      var list = result.list || [];
      var activeSub = getActiveSubCategory();
      var activeCategory = getActiveCategory();
      var fallbackImage = activeSub && activeSub.imageUrl
        ? activeSub.imageUrl
        : (activeCategory.defaultImage || "");

      global.CategoryRender.renderProductCards(refs.productGrid, list, {
        fallbackImage: fallbackImage
      });

      global.CategoryRender.renderPagination(refs.pagination, {
        page: state.page,
        totalPages: state.totalPages,
        onPageChange: function (nextPage) {
          var parsedPage = Number(nextPage);
          if (!Number.isInteger(parsedPage)) return;
          if (parsedPage < 1 || parsedPage === state.page) return;

          state.page = parsedPage;
          loadProducts({ syncHistory: true, replaceHistory: false });
        }
      });

      global.CategoryRender.renderPageMeta(refs.resultMeta, {
        total: state.total,
        page: state.page,
        totalPages: state.totalPages
      });

      global.CategoryRender.renderStatus(refs, {
        loading: false,
        error: "",
        empty: list.length === 0
      });
    } catch (err) {
      if (err && err.name === "AbortError") return;

      global.CategoryRender.renderProductCards(refs.productGrid, [], {});
      global.CategoryRender.renderPagination(refs.pagination, {
        page: 1,
        totalPages: 1,
        onPageChange: function () {}
      });

      global.CategoryRender.renderStatus(refs, {
        loading: false,
        error: (err && err.message) || "产品数据加载失败，请稍后重试。",
        empty: false
      });
    }
  }

  function bindPopState() {
    global.addEventListener("popstate", function () {
      var next = parseUrlState(window.location.search);
      state.type = String(next.type);
      state.sub = next.sub;
      state.page = next.page;
      loadProducts({ syncHistory: false, replaceHistory: false });
    });
  }

  async function init() {
    try {
      state.config = await global.CategoryApi.fetchConfig(getConfigUrl());

      var initial = parseUrlState(window.location.search);
      state.type = String(initial.type);
      state.sub = initial.sub;
      state.page = initial.page;

      bindPopState();
      loadProducts({ syncHistory: true, replaceHistory: true });
    } catch (err) {
      refs.loadingState.hidden = true;
      refs.errorState.hidden = false;
      refs.errorState.textContent = (err && err.message) || "初始化失败，请检查配置文件。";
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);
