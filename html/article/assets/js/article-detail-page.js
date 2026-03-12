(function (global) {
  "use strict";

  var MISSING_PARAM_REDIRECT_URL = "https://zgzonre.com/product";
  var MISSING_PARAM_REDIRECT_DELAY = 1600;
  var DEFAULT_ARTICLE_ID = 395;
  var DEFAULT_API_BASE = "https://www.zgzonre.com/wp-json/wp/v2/";
  var DEFAULT_FALLBACK_LIST_URL = "https://www.zgzonre.com/product";
  var DEFAULT_COVER_IMAGE = "https://www.zgzonre.com/wp-content/uploads/2026/03/wysm.png";
  var DEFAULT_RECOMMENDATION_DISPLAY_COUNT = 6;
  var DEFAULT_RECOMMENDATION_CANDIDATE_COUNT = 12;
  var DEFAULT_SHARED_CATEGORY_CONFIG_URL =
    "https://static.jsss999.com/upload/zrsite/category/common/dynamic/home-category-runtime-config-v1.2.json";
  var missingParamRedirectTimer = null;

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
    missingParamModal: document.getElementById("zr-article-missing-param-modal"),
    missingParamAction: document.getElementById("zr-article-modal-action")
  };

  function getSharedCategoryConfigUrl() {
    return DEFAULT_SHARED_CATEGORY_CONFIG_URL;
  }

  function createRuntimeConfig() {
    return {
      apiBase: DEFAULT_API_BASE,
      fallbackListUrl: DEFAULT_FALLBACK_LIST_URL,
      defaultCover: DEFAULT_COVER_IMAGE,
      recommendationDisplayCount: DEFAULT_RECOMMENDATION_DISPLAY_COUNT,
      recommendationCandidateCount: DEFAULT_RECOMMENDATION_CANDIDATE_COUNT,
      mainCategoryGroups: []
    };
  }

  function readArticleIdFromQuery() {
    var params = new URLSearchParams(window.location.search || "");
    var raw = params.get("article_id");

    if (raw === null || !String(raw).trim()) {
      raw = params.get("article");
    }

    if (raw === null || !String(raw).trim()) {
      return DEFAULT_ARTICLE_ID;
    }

    var id = Number(String(raw).trim());
    return Number.isInteger(id) && id > 0 ? id : null;
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
    if (!cleanTitle) return;
    document.title = cleanTitle + " - 江苏中热机械设备有限公司";
  }

  function formatPublishedDate(input) {
    if (!input) return "";
    var normalized = String(input).trim().replace("T", " ");
    var match = normalized.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
    if (!match) return normalized;
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
    if (!baseUrl || !subId) return baseUrl || "";
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

  function mapSharedMainCategoryGroups(sharedConfig, fallbackListUrl) {
    var mainCategories = sharedConfig && Array.isArray(sharedConfig.mainCategories)
      ? sharedConfig.mainCategories
      : [];

    return mainCategories
      .map(function (item) {
        var parentId = Number(item && item.parentId) || 0;
        var type = item && item.type ? String(item.type) : "";
        var categoryIds = Array.isArray(item && item.childCategoryIds)
          ? item.childCategoryIds.map(function (id) {
              return Number(id);
            }).filter(function (id) {
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
          fallbackUrl: buildMainCategoryUrl(fallbackListUrl || MISSING_PARAM_REDIRECT_URL, type)
        };
      })
      .filter(function (item) {
        return !!item;
      });
  }

  function resolveCategoryState(postCategories, categories, config) {
    var childCategory = categories.find(function (item) {
      return Number(item.parent) > 0;
    }) || null;

    var parentCategory = categories.find(function (item) {
      return Number(item.parent) === 0;
    }) || null;

    if (!parentCategory && childCategory) {
      parentCategory = categories.find(function (item) {
        return Number(item.id) === Number(childCategory.parent);
      }) || null;
    }

    var group = (config.mainCategoryGroups || []).find(function (item) {
      return (
        Number(item.id) === Number(parentCategory && parentCategory.id) ||
        item.categoryIds.some(function (id) {
          return postCategories.indexOf(Number(id)) !== -1;
        })
      );
    }) || null;

    return {
      firstCategory: categories[0] || null,
      childCategory: childCategory,
      parentCategory: parentCategory,
      mainGroup: group,
      parentCategoryUrl: group ? group.fallbackUrl : "",
      childCategoryUrl: group && childCategory ? buildSubCategoryUrl(group.fallbackUrl, childCategory.id) : ""
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
    if (!refs.backButton) return;
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
    refs.recommendSection.hidden = true;
    refs.error.hidden = false;
    refs.error.textContent = message;
  }

  function redirectToMissingParamFallback() {
    if (missingParamRedirectTimer) {
      global.clearTimeout(missingParamRedirectTimer);
      missingParamRedirectTimer = null;
    }

    global.location.replace(MISSING_PARAM_REDIRECT_URL);
  }

  function showMissingParamModal() {
    refs.loading.hidden = true;
    refs.body.hidden = true;
    refs.postNav.hidden = true;
    refs.recommendSection.hidden = true;
    refs.error.hidden = true;

    if (!refs.missingParamModal) {
      redirectToMissingParamFallback();
      return;
    }

    if (refs.missingParamAction) {
      refs.missingParamAction.onclick = function (event) {
        event.preventDefault();
        redirectToMissingParamFallback();
      };
    }

    refs.missingParamModal.hidden = false;
    missingParamRedirectTimer = global.setTimeout(
      redirectToMissingParamFallback,
      MISSING_PARAM_REDIRECT_DELAY
    );
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
      console.warn("Failed to load shared category config, fallback to local config.", error);
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

  async function bootstrap() {
    try {
      var articleId = readArticleIdFromQuery();
      if (!articleId) {
        showMissingParamModal();
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
      global.ArticleDetailRender.renderContent(refs.content, post.content && post.content.rendered);
      global.ArticleDetailRender.renderPostNavigation(refs.postNav, readPostNavigation());

      refs.loading.hidden = true;
      refs.error.hidden = true;
      refs.body.hidden = false;

      var recommendationIds = state.mainGroup ? state.mainGroup.categoryIds : postCategories;
      var recommendationCandidates = await global.ArticleDetailApi.fetchPostsByCategories(
        config.apiBase,
        recommendationIds,
        articleId,
        config.recommendationCandidateCount || 12
      );
      var recommendations = shuffle(recommendationCandidates).slice(0, config.recommendationDisplayCount || 6);
      global.ArticleDetailRender.renderRecommendations(
        refs.recommendSection,
        refs.recommendGrid,
        recommendations,
        config.defaultCover
      );
    } catch (error) {
      showError("文章详情加载失败，请检查 article_id 和接口配置。");
      console.error(error);
    }
  }

  bootstrap();
})(window);
