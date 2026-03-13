(function (global) {
  "use strict";

  var state = {
    config: null,
    tree: null,
    rootExpanded: false,
    secondId: null,
    thirdId: null,
    page: 1,
    perPage: 9,
    total: 0,
    totalPages: 0,
    controller: null,
    scenesRendered: false,
    topHeroRendered: false
  };

  var refs = {
    root: document.querySelector(".zr-vr-page"),
    topHeroBg: document.getElementById("zr-vr-top-hero-bg"),
    rootTabs: document.getElementById("zr-vr-root-category-tabs"),
    mainSection: document.getElementById("zr-vr-main-category-section"),
    mainTabs: document.getElementById("zr-vr-main-category-tabs"),
    subSection: document.getElementById("zr-vr-sub-category-section"),
    subTabs: document.getElementById("zr-vr-sub-category-tabs"),
    sceneTopImage: document.getElementById("zr-vr-scene-top-image"),
    sceneGrid: document.getElementById("zr-vr-scene-grid"),
    resultMeta: document.getElementById("zr-vr-result-meta"),
    loadingState: document.getElementById("zr-vr-loading-state"),
    errorState: document.getElementById("zr-vr-error-state"),
    emptyState: document.getElementById("zr-vr-empty-state"),
    productGrid: document.getElementById("zr-vr-product-grid"),
    pagination: document.getElementById("zr-vr-pagination")
  };

  function getConfigUrl() {
    return (
      (refs.root && refs.root.getAttribute("data-config-url")) ||
      "https://static.jsss999.com/upload/zrsite/category/common/dynamic/home-category-runtime-config-v1.2.json"
    );
  }

  function getCategoryApiBase() {
    return (
      (refs.root && refs.root.getAttribute("data-category-api-base")) ||
      "https://www.zgzonre.com/wp-json/wp/v2/categories"
    );
  }

  function getPostApiBase() {
    return (
      (refs.root && refs.root.getAttribute("data-post-api-base")) ||
      "https://www.zgzonre.com/wp-json/wp/v2/posts"
    );
  }

  function getDetailBase() {
    return (
      (refs.root && refs.root.getAttribute("data-detail-base")) ||
      "../article/detail.local.html"
    );
  }

  function getRootCategoryId() {
    return Number((refs.root && refs.root.getAttribute("data-root-category-id")) || 66) || 66;
  }

  function toPositiveInt(value, fallback) {
    var num = Number(value);
    if (!Number.isInteger(num) || num <= 0) return fallback;
    return num;
  }

  function parseUrlState(search) {
    var params = new URLSearchParams(search || "");
    var pageParam = params.get("pg") || params.get("page");
    return {
      rootExpanded: params.get("open") === "1" || !!params.get("cat") || !!params.get("sub"),
      secondId: params.get("cat") ? toPositiveInt(params.get("cat"), null) : null,
      thirdId: params.get("sub") ? toPositiveInt(params.get("sub"), null) : null,
      page: toPositiveInt(pageParam, 1)
    };
  }

  function getSecondCategories() {
    return state.tree && Array.isArray(state.tree.secondLevel) ? state.tree.secondLevel : [];
  }

  function getActiveSecondCategory() {
    return getSecondCategories().find(function (item) {
      return Number(item.id) === Number(state.secondId);
    }) || null;
  }

  function getActiveThirdCategory() {
    var second = getActiveSecondCategory();
    if (!second || !state.thirdId) return null;
    return (second.children || []).find(function (item) {
      return Number(item.id) === Number(state.thirdId);
    }) || null;
  }

  function normalizeState() {
    var secondCategories = getSecondCategories();
    if (!secondCategories.length) {
      state.secondId = null;
      state.thirdId = null;
      return;
    }

    var hasSecond = secondCategories.some(function (item) {
      return Number(item.id) === Number(state.secondId);
    });

    if (!hasSecond) {
      state.secondId = null;
    }

    var activeSecond = getActiveSecondCategory();
    var thirdIds = (activeSecond && activeSecond.children || []).map(function (item) {
      return Number(item.id);
    });

    if (!thirdIds.length) {
      state.thirdId = null;
    } else if (state.thirdId && thirdIds.indexOf(Number(state.thirdId)) === -1) {
      state.thirdId = null;
    }

    state.page = toPositiveInt(state.page, 1);
  }

  function syncUrl(replace) {
    var params = new URLSearchParams();
    if (state.rootExpanded && !state.secondId && !state.thirdId) {
      params.set("open", "1");
    }
    if (state.secondId) params.set("cat", String(state.secondId));
    if (state.thirdId) params.set("sub", String(state.thirdId));
    if (state.page > 1) params.set("pg", String(state.page));

    var nextUrl = window.location.pathname + (params.toString() ? "?" + params.toString() : "");
    if (replace) {
      window.history.replaceState(null, "", nextUrl);
    } else {
      window.history.pushState(null, "", nextUrl);
    }
  }

  function getRequestCategories() {
    var activeThird = getActiveThirdCategory();
    if (activeThird) {
      return [Number(activeThird.id)];
    }

    var activeSecond = getActiveSecondCategory();
    if (activeSecond) {
      return [Number(activeSecond.id)];
    }

    return [getRootCategoryId()];
  }

  function renderFixedAssets() {
    if (!state.topHeroRendered && refs.topHeroBg && state.config.topBannerBg) {
      refs.topHeroBg.style.backgroundImage = "url('" + state.config.topBannerBg + "')";
      state.topHeroRendered = true;
    }

    if (refs.sceneTopImage) {
      refs.sceneTopImage.src =
        state.config.applicationTopImage ||
        "https://static.jsss999.com/upload/zrsite/common/VCG41N867423914.jpg";
    }

    if (!state.scenesRendered) {
      global.VrCategoryRender.renderSceneImages(
        refs.sceneGrid,
        state.config.applicationScenes || [],
        state.config.applicationSceneLabels || []
      );
      state.scenesRendered = true;
    }
  }

  function renderStaticBlocks() {
    var secondCategories = getSecondCategories();
    var activeSecond = getActiveSecondCategory();
    var activeThird = getActiveThirdCategory();
    var rootId = getRootCategoryId();
    var rootName = state.tree && state.tree.root ? state.tree.root.name : "VR展示";

    global.VrCategoryRender.renderMainTabs(
      refs.rootTabs,
      [{ id: rootId, name: rootName }],
      rootId,
      function () {
        state.rootExpanded = true;
        state.secondId = null;
        state.thirdId = null;
        state.page = 1;
        loadProducts({ syncHistory: true, replaceHistory: false });
      }
    );

    if (refs.mainSection) {
      refs.mainSection.hidden = !state.rootExpanded;
    }

    global.VrCategoryRender.renderMainTabs(
      refs.mainTabs,
      secondCategories,
      state.secondId,
      function (nextId) {
        state.rootExpanded = true;

        if (Number(nextId) === Number(state.secondId)) {
          if (state.thirdId) {
            state.thirdId = null;
            state.page = 1;
            loadProducts({ syncHistory: true, replaceHistory: false });
          }
          return;
        }

        state.secondId = Number(nextId);
        state.thirdId = null;
        state.page = 1;
        loadProducts({ syncHistory: true, replaceHistory: false });
      }
    );

    global.VrCategoryRender.renderSubTabs(
      refs.subSection,
      refs.subTabs,
      activeSecond ? activeSecond.children : [],
      state.thirdId,
      function (nextThirdId) {
        var normalized = Number(nextThirdId);
        if (!Number.isInteger(normalized) || normalized <= 0) return;
        if (Number(state.thirdId) === Number(normalized)) return;
        state.rootExpanded = true;
        state.thirdId = normalized;
        state.page = 1;
        loadProducts({ syncHistory: true, replaceHistory: false });
      }
    );

    renderFixedAssets();
  }

  function loadProducts(options) {
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

    global.VrCategoryRender.renderStatus(refs, {
      loading: true,
      error: "",
      empty: false
    });

    return global.VrCategoryApi.fetchPosts({
      postApiBase: getPostApiBase(),
      categories: getRequestCategories(),
      page: state.page,
      perPage: state.perPage,
      signal: signal,
      detailBase: getDetailBase()
    }).then(function (result) {
      if (signal.aborted) return;

      state.total = result.total;
      state.totalPages = result.totalPages || 1;

      if (state.page > state.totalPages && state.totalPages > 0) {
        state.page = state.totalPages;
        return loadProducts({ syncHistory: true, replaceHistory: true });
      }

      var list = result.list || [];

      global.VrCategoryRender.renderProductCards(refs.productGrid, list);
      global.VrCategoryRender.renderPageMeta(refs.resultMeta, {
        total: state.total,
        page: state.page,
        totalPages: state.totalPages || 1
      });
      global.VrCategoryRender.renderPagination(refs.pagination, {
        page: state.page,
        totalPages: state.totalPages || 1,
        onPageChange: function (nextPage) {
          var parsedPage = Number(nextPage);
          if (!Number.isInteger(parsedPage) || parsedPage === state.page || parsedPage < 1) {
            return;
          }
          state.page = parsedPage;
          loadProducts({ syncHistory: true, replaceHistory: false });
        }
      });
      global.VrCategoryRender.renderStatus(refs, {
        loading: false,
        error: "",
        empty: !list.length
      });
    }).catch(function (error) {
      if (signal.aborted) return;
      global.VrCategoryRender.renderStatus(refs, {
        loading: false,
        error: error && error.message ? error.message : "加载失败，请稍后重试。",
        empty: false
      });
    });
  }

  function init() {
    var urlState = parseUrlState(window.location.search);
    state.rootExpanded = urlState.rootExpanded;
    state.secondId = urlState.secondId;
    state.thirdId = urlState.thirdId;
    state.page = urlState.page;

    Promise.all([
      global.VrCategoryApi.fetchConfig(getConfigUrl()),
      global.VrCategoryApi.fetchVrCategoryTree(getCategoryApiBase(), getRootCategoryId())
    ]).then(function (results) {
      state.config = results[0] || {};
      state.tree = results[1] || null;
      normalizeState();
      return loadProducts({ syncHistory: true, replaceHistory: true });
    }).catch(function (error) {
      global.VrCategoryRender.renderStatus(refs, {
        loading: false,
        error: error && error.message ? error.message : "加载失败，请稍后重试。",
        empty: false
      });
    });

    window.addEventListener("popstate", function () {
      var current = parseUrlState(window.location.search);
      state.secondId = current.secondId;
      state.thirdId = current.thirdId;
      state.page = current.page;
      loadProducts({ syncHistory: false, replaceHistory: true });
    });
  }

  init();
})(window);
