(function (global) {
  "use strict";

  var MISSING_PARAM_REDIRECT_URL = "https://zgzonre.com/product";
  var MISSING_PARAM_REDIRECT_DELAY = 3000;
  var DEFAULT_ARTICLE_ID = 395;
  var DEFAULT_API_BASE = "https://www.zgzonre.com/wp-json/wp/v2/";
  var DEFAULT_FALLBACK_LIST_URL = "https://www.zgzonre.com/product";
  var DEFAULT_VR_FALLBACK_LIST_URL = "https://www.zgzonre.com/index-more";
  var VR_ROOT_CATEGORY_ID = 66;
  var VR_ROOT_CATEGORY_NAME = "VR展示";
  var DEFAULT_COVER_IMAGE = "https://www.zgzonre.com/wp-content/uploads/2026/03/wysm.png";
  var DEFAULT_RECOMMENDATION_DISPLAY_COUNT = 6;
  var DEFAULT_RECOMMENDATION_CANDIDATE_COUNT = 12;
  var DEFAULT_SHARED_CATEGORY_CONFIG_URL =
    "https://static.jsss999.com/upload/zrsite/category/common/dynamic/home-category-runtime-config-v1.2.json";
  var redirectTimer = null;

  var refs = {
    root: document.querySelector(".zr-article-page"),
    backButton: document.getElementById("zr-article-back"),
    title: document.getElementById("zr-article-title"),
    category: document.getElementById("zr-article-category"),
    date: document.getElementById("zr-article-date"),
    loading: document.getElementById("zr-article-loading"),
    error: document.getElementById("zr-article-error"),
    body: document.getElementById("zr-article-body"),
    content: document.getElementById("zr-article-content"),
    postNav: document.getElementById("zr-article-post-nav"),
    recommendSection: document.getElementById("zr-article-recommend"),
    recommendGrid: document.getElementById("zr-article-recommend-grid"),
    noticeModal: document.getElementById("zr-article-missing-param-modal"),
    noticeAction: document.getElementById("zr-article-modal-action"),
    noticeTitle: document.getElementById("zr-article-modal-title"),
    noticeText: document.getElementById("zr-article-modal-text")
  };

  function getSharedCategoryConfigUrl() {
    return DEFAULT_SHARED_CATEGORY_CONFIG_URL;
  }

  function createRuntimeConfig() {
    return {
      apiBase: DEFAULT_API_BASE,
      fallbackListUrl: DEFAULT_FALLBACK_LIST_URL,
      vrFallbackListUrl: DEFAULT_VR_FALLBACK_LIST_URL,
      vrRootCategoryId: VR_ROOT_CATEGORY_ID,
      vrRootCategoryName: VR_ROOT_CATEGORY_NAME,
      defaultCover: DEFAULT_COVER_IMAGE,
      recommendationDisplayCount: DEFAULT_RECOMMENDATION_DISPLAY_COUNT,
      recommendationCandidateCount: DEFAULT_RECOMMENDATION_CANDIDATE_COUNT,
      mainCategoryGroups: []
    };
  }

  function hasQueryValue(value) {
    return value !== null && value !== undefined && String(value).trim() !== "";
  }

  function parseArticleId(value) {
    var id = Number(String(value || "").trim());
    return Number.isInteger(id) && id > 0 ? id : null;
  }

  function getArticleIdFromParams(params) {
    if (!params) {
      return "";
    }

    var raw = params.get("article_id");
    if (hasQueryValue(raw)) {
      return raw;
    }

    raw = params.get("article");
    return hasQueryValue(raw) ? raw : "";
  }

  function decodeQueryValue(value) {
    var normalized = String(value || "").replace(/\+/g, "%20");
    try {
      return decodeURIComponent(normalized);
    } catch (_error) {
      return String(value || "");
    }
  }

  function getArticleIdFromHref(input) {
    var match = String(input || "").match(/[?&#]+(?:article_id|article)=([^&#?]+)/i);
    return match ? decodeQueryValue(match[1]) : "";
  }

  function readArticleIdFromQuery() {
    var raw = getArticleIdFromParams(new URLSearchParams(window.location.search || ""));

    if (!hasQueryValue(raw)) {
      raw = getArticleIdFromHref(window.location.href);
    }

    if (!hasQueryValue(raw)) {
      raw = getArticleIdFromParams(
        new URLSearchParams(String(window.location.hash || "").replace(/^#\??/, ""))
      );
    }

    if (!hasQueryValue(raw)) {
      raw = getArticleIdFromHref(window.location.hash || "");
    }

    if (!hasQueryValue(raw)) {
      return DEFAULT_ARTICLE_ID;
    }

    return parseArticleId(raw);
  }

  function shuffle(list) {
    var items = list.slice();
    for (var i = items.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var temp = items[i];
      items[i] = items[j];
      items[j] = temp;
    }
    return items;
  }

  function decodeHtmlText(input) {
    var box = document.createElement("div");
    box.innerHTML = input || "";
    return box.textContent || "";
  }

  function updateDocumentTitle(title) {
    var cleanTitle = String(title || "").trim();
    if (!cleanTitle) {
      return;
    }
    document.title = cleanTitle + " - 江苏中热机械设备有限公司";
  }

  function formatPublishedDate(input) {
    if (!input) {
      return "";
    }

    var normalized = String(input).trim().replace("T", " ");
    var match = normalized.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
    if (!match) {
      return normalized;
    }

    return (
      match[1] +
      "年" +
      String(Number(match[2])) +
      "月" +
      String(Number(match[3])) +
      "日 " +
      match[4] +
      ":" +
      match[5]
    );
  }

  function buildSubCategoryUrl(baseUrl, subId) {
    if (!baseUrl || !subId) {
      return baseUrl || "";
    }

    try {
      var parsed = new URL(baseUrl, window.location.href);
      parsed.searchParams.set("sub", String(subId));
      return parsed.href;
    } catch (_error) {
      var joiner = baseUrl.indexOf("?") === -1 ? "?" : "&";
      return baseUrl + joiner + "sub=" + encodeURIComponent(String(subId));
    }
  }

  function buildMainCategoryUrl(baseUrl, type) {
    if (!baseUrl || !type) {
      return baseUrl || "";
    }

    try {
      var parsed = new URL(baseUrl, window.location.href);
      parsed.searchParams.set("type", String(type));
      return parsed.href;
    } catch (_error) {
      var joiner = baseUrl.indexOf("?") === -1 ? "?" : "&";
      return baseUrl + joiner + "type=" + encodeURIComponent(String(type));
    }
  }

  function buildCategoryMap(categories) {
    var categoryMap = {};
    (categories || []).forEach(function (item) {
      var id = Number(item && item.id) || 0;
      if (id > 0) {
        categoryMap[id] = item;
      }
    });
    return categoryMap;
  }

  function getCategoryDepth(category, categoryMap) {
    var depth = 0;
    var current = category;
    var visited = {};

    while (current && !visited[current.id]) {
      visited[current.id] = true;
      depth += 1;

      var parentId = Number(current.parent) || 0;
      if (!parentId) {
        break;
      }

      current = categoryMap[parentId] || null;
    }

    return depth;
  }

  function findPrimaryCategory(postCategories, categories, categoryMap) {
    var requestedIndexMap = {};
    (postCategories || []).forEach(function (id, index) {
      var numericId = Number(id) || 0;
      if (numericId > 0 && requestedIndexMap[numericId] === undefined) {
        requestedIndexMap[numericId] = index;
      }
    });

    var selected = null;
    var selectedDepth = -1;
    var selectedIndex = Number.MAX_SAFE_INTEGER;

    (categories || []).forEach(function (item) {
      var itemId = Number(item && item.id) || 0;
      if (requestedIndexMap[itemId] === undefined) {
        return;
      }

      var depth = getCategoryDepth(item, categoryMap);
      var itemIndex = requestedIndexMap[itemId];

      if (
        depth > selectedDepth ||
        (depth === selectedDepth && itemIndex < selectedIndex)
      ) {
        selected = item;
        selectedDepth = depth;
        selectedIndex = itemIndex;
      }
    });

    return selected || (categories && categories[0]) || null;
  }

  function buildCategoryTrail(targetCategory, categoryMap) {
    if (!targetCategory) {
      return [];
    }

    var trail = [];
    var current = targetCategory;
    var visited = {};

    while (current && !visited[current.id]) {
      visited[current.id] = true;
      trail.unshift(current);

      var parentId = Number(current.parent) || 0;
      if (!parentId) {
        break;
      }

      current = categoryMap[parentId] || null;
    }

    return trail;
  }

  function buildCategoryTrailItems(trail, mainGroup, config) {
    if (!Array.isArray(trail) || !trail.length) {
      return [];
    }

    var isVrGroup = !!(mainGroup && mainGroup.type === "vr");
    var vrFallbackUrl =
      (config && config.vrFallbackListUrl) || DEFAULT_VR_FALLBACK_LIST_URL;
    var fallbackUrl = (mainGroup && mainGroup.fallbackUrl) || "";

    return trail.map(function (category, index) {
      var href = "";

      if (isVrGroup) {
        href = index === 0 ? vrFallbackUrl : "";
      } else if (fallbackUrl) {
        href = index === 0 ? fallbackUrl : buildSubCategoryUrl(fallbackUrl, category.id);
      }

      return {
        id: Number(category.id) || 0,
        name: category.name || "",
        href: href,
        isCurrent: index === trail.length - 1
      };
    });
  }

  function mapSharedMainCategoryGroups(sharedConfig, fallbackListUrl) {
    var mainCategories =
      sharedConfig && Array.isArray(sharedConfig.mainCategories)
        ? sharedConfig.mainCategories
        : [];

    return mainCategories
      .map(function (item) {
        var parentId = Number(item && item.parentId) || 0;
        var type = item && item.type ? String(item.type) : "";
        var categoryIds = Array.isArray(item && item.childCategoryIds)
          ? item.childCategoryIds
              .map(function (id) {
                return Number(id);
              })
              .filter(function (id) {
                return Number.isInteger(id) && id > 0;
              })
          : [];

        if (!parentId || !type || !categoryIds.length) {
          return null;
        }

        return {
          id: parentId,
          type: type,
          name: item.displayName || item.label || "",
          categoryIds: categoryIds,
          fallbackUrl: buildMainCategoryUrl(
            fallbackListUrl || MISSING_PARAM_REDIRECT_URL,
            type
          )
        };
      })
      .filter(function (item) {
        return !!item;
      });
  }

  function resolveCategoryState(postCategories, categories, config) {
    var vrRootCategoryId = Number(config && config.vrRootCategoryId) || 0;
    var categoryMap = buildCategoryMap(categories);
    var primaryCategory = findPrimaryCategory(postCategories, categories, categoryMap);
    var categoryTrail = buildCategoryTrail(primaryCategory, categoryMap);
    var rootCategory = categoryTrail[0] || null;
    var isVrArticle = vrRootCategoryId && postCategories.indexOf(vrRootCategoryId) !== -1;

    var group = null;
    if (isVrArticle) {
      var vrRootCategory = categoryMap[vrRootCategoryId] || rootCategory || {
        id: vrRootCategoryId,
        name: (config && config.vrRootCategoryName) || VR_ROOT_CATEGORY_NAME,
        parent: 0,
        slug: "vr",
        count: 0
      };

      group = {
        id: vrRootCategoryId,
        type: "vr",
        name:
          vrRootCategory.name ||
          ((config && config.vrRootCategoryName) || VR_ROOT_CATEGORY_NAME),
        categoryIds: [vrRootCategoryId],
        fallbackUrl:
          (config && config.vrFallbackListUrl) || DEFAULT_VR_FALLBACK_LIST_URL
      };
    } else {
      group =
        (config.mainCategoryGroups || []).find(function (item) {
        return (
          Number(item.id) === Number(rootCategory && rootCategory.id) ||
          item.categoryIds.some(function (id) {
            return postCategories.indexOf(Number(id)) !== -1;
          })
        );
        }) || null;
    }

    var trailItems = buildCategoryTrailItems(categoryTrail, group, config);

    return {
      firstCategory: categoryTrail[0] || categories[0] || null,
      firstCategoryUrl: trailItems[0] ? trailItems[0].href : "",
      childCategory: categoryTrail.length > 1 ? categoryTrail[categoryTrail.length - 1] : null,
      parentCategory: categoryTrail[0] || null,
      mainGroup: group,
      parentCategoryUrl: trailItems[0] ? trailItems[0].href : "",
      childCategoryUrl:
        trailItems.length > 1 ? trailItems[trailItems.length - 1].href : "",
      categoryTrail: trailItems
    };
  }

  function readPostNavigation() {
    var nav = document.querySelector('nav[aria-label="文章导航"]');
    if (!nav) {
      return { previousPost: null, nextPost: null };
    }

    var prevLink = nav.querySelector(".post-navigation-link-previous a");
    var nextLink = nav.querySelector(".post-navigation-link-next a");

    return {
      previousPost: prevLink
        ? { href: prevLink.href, title: prevLink.textContent.trim() }
        : null,
      nextPost: nextLink
        ? { href: nextLink.href, title: nextLink.textContent.trim() }
        : null
    };
  }

  function bindBackButton(fallbackUrl) {
    if (!refs.backButton) {
      return;
    }

    refs.backButton.addEventListener("click", function () {
      if (window.history.length > 1) {
        window.history.back();
        return;
      }
      window.location.href = fallbackUrl;
    });
  }

  function showError(message) {
    refs.loading.hidden = true;
    refs.body.hidden = true;
    refs.postNav.hidden = true;
    refs.recommendSection.hidden = true;
    refs.error.hidden = false;
    refs.error.textContent = message;
  }

  function redirectToFallback() {
    if (redirectTimer) {
      global.clearTimeout(redirectTimer);
      redirectTimer = null;
    }

    global.location.replace(MISSING_PARAM_REDIRECT_URL);
  }

  function showNoticeModal(title, text) {
    refs.loading.hidden = true;
    refs.body.hidden = true;
    refs.postNav.hidden = true;
    refs.recommendSection.hidden = true;
    refs.error.hidden = true;

    if (!refs.noticeModal) {
      redirectToFallback();
      return;
    }

    if (refs.noticeTitle) {
      refs.noticeTitle.textContent = title || "提示";
    }

    if (refs.noticeText) {
      refs.noticeText.textContent = text || "";
    }

    if (refs.noticeAction) {
      refs.noticeAction.onclick = function (event) {
        event.preventDefault();
        redirectToFallback();
      };
    }

    refs.noticeModal.hidden = false;
    redirectTimer = global.setTimeout(redirectToFallback, MISSING_PARAM_REDIRECT_DELAY);
  }

  function showInvalidParamModal() {
    showNoticeModal("参数缺失", "未检测到有效的文章 ID，页面将自动跳转到产品列表。");
  }

  function showArticleNotFoundModal() {
    showNoticeModal("文章资源不存在", "未找到对应文章内容，页面将自动跳转到产品列表。");
  }

  async function loadSharedCategoryConfig() {
    var configUrl = getSharedCategoryConfigUrl();
    if (!configUrl) {
      return null;
    }

    try {
      var response = await fetch(configUrl, { cache: "default" });
      if (!response.ok) {
        throw new Error("Failed to load shared category config");
      }
      return response.json();
    } catch (error) {
      console.warn("Failed to load shared category config.", error);
      return null;
    }
  }

  async function loadRuntimeConfig() {
    var detailConfig = createRuntimeConfig();
    var sharedCategoryConfig = await loadSharedCategoryConfig();
    detailConfig.mainCategoryGroups = mapSharedMainCategoryGroups(
      sharedCategoryConfig,
      detailConfig.fallbackListUrl
    );
    return detailConfig;
  }

  async function loadRecommendations(config, state, postCategories, articleId) {
    var recommendationIds = state.mainGroup ? state.mainGroup.categoryIds : postCategories;
    if (!recommendationIds.length) {
      global.ArticleDetailRender.renderRecommendations(
        refs.recommendSection,
        refs.recommendGrid,
        [],
        config.defaultCover
      );
      return;
    }

    try {
      var recommendationCandidates = await global.ArticleDetailApi.fetchPostsByCategories(
        config.apiBase,
        recommendationIds,
        articleId,
        config.recommendationCandidateCount || DEFAULT_RECOMMENDATION_CANDIDATE_COUNT
      );

      var recommendations = shuffle(recommendationCandidates).slice(
        0,
        config.recommendationDisplayCount || DEFAULT_RECOMMENDATION_DISPLAY_COUNT
      );

      global.ArticleDetailRender.renderRecommendations(
        refs.recommendSection,
        refs.recommendGrid,
        recommendations,
        config.defaultCover
      );
    } catch (error) {
      console.warn("Failed to load recommendations.", error);
      global.ArticleDetailRender.renderRecommendations(
        refs.recommendSection,
        refs.recommendGrid,
        [],
        config.defaultCover
      );
    }
  }

  async function bootstrap() {
    try {
      var articleId = readArticleIdFromQuery();
      if (!articleId) {
        showInvalidParamModal();
        return;
      }

      var config = await loadRuntimeConfig();
      var post = await global.ArticleDetailApi.fetchPost(config.apiBase, articleId);
      var postCategories = Array.isArray(post.categories) ? post.categories.map(Number) : [];
      var categories = await global.ArticleDetailApi.fetchCategories(config.apiBase, postCategories);
      var state = resolveCategoryState(postCategories, categories, config);
      var fallbackUrl = (state.mainGroup && state.mainGroup.fallbackUrl) || config.fallbackListUrl;

      bindBackButton(fallbackUrl);

      var articleTitle = decodeHtmlText(post.title && post.title.rendered);
      updateDocumentTitle(articleTitle);
      global.ArticleDetailRender.setText(refs.title, articleTitle);
      global.ArticleDetailRender.renderCategoryLine(refs.category, state);
      global.ArticleDetailRender.setText(refs.date, "发布日期：" + formatPublishedDate(post.date));
      global.ArticleDetailRender.renderContent(
        refs.content,
        post.content && post.content.rendered
      );
      if (
        global.ArticleDetailGallery &&
        typeof global.ArticleDetailGallery.enhance === "function"
      ) {
        try {
          global.ArticleDetailGallery.enhance(refs.content);
        } catch (galleryError) {
          console.warn("Failed to build article gallery.", galleryError);
        }
      }
      global.ArticleDetailRender.renderPostNavigation(refs.postNav, readPostNavigation());

      refs.loading.hidden = true;
      refs.error.hidden = true;
      refs.body.hidden = false;

      await loadRecommendations(config, state, postCategories, articleId);
    } catch (error) {
      if (error && Number(error.status) === 404) {
        showArticleNotFoundModal();
        return;
      }

      showError("文章详情加载失败，请检查 article_id 和接口配置。");
      console.error(error);
    }
  }

  bootstrap();
})(window);
