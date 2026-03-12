(function (global) {
  "use strict";

  var refs = {
    root: document.querySelector(".zr-article-page"),
    backButton: document.getElementById("zr-article-back"),
    title: document.getElementById("zr-article-title"),
    category: document.getElementById("zr-article-category"),
    loading: document.getElementById("zr-article-loading"),
    error: document.getElementById("zr-article-error"),
    body: document.getElementById("zr-article-body"),
    content: document.getElementById("zr-article-content"),
    postNav: document.getElementById("zr-article-post-nav"),
    recommendSection: document.getElementById("zr-article-recommend"),
    recommendGrid: document.getElementById("zr-article-recommend-grid")
  };

  function getConfigUrl() {
    if (refs.root && refs.root.getAttribute("data-config-url")) {
      return refs.root.getAttribute("data-config-url");
    }
    return "./config/article-detail-runtime-config.json";
  }

  function readArticleId(config) {
    var params = new URLSearchParams(window.location.search || "");
    var raw = params.get("article_id") || params.get("article");
    var id = Number(raw || config.defaultArticleId || 361);
    return Number.isInteger(id) && id > 0 ? id : 361;
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

  async function loadConfig() {
    var response = await fetch(getConfigUrl(), { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Failed to load config");
    }
    return response.json();
  }

  async function bootstrap() {
    try {
      var config = await loadConfig();
      var articleId = readArticleId(config);
      var post = await global.ArticleDetailApi.fetchPost(config.apiBase, articleId);
      var postCategories = Array.isArray(post.categories) ? post.categories.map(Number) : [];
      var categories = await global.ArticleDetailApi.fetchCategories(config.apiBase, postCategories);
      var state = resolveCategoryState(postCategories, categories, config);
      var fallbackUrl = (state.mainGroup && state.mainGroup.fallbackUrl) || config.fallbackListUrl;

      bindBackButton(fallbackUrl);
      global.ArticleDetailRender.setText(refs.title, decodeHtmlText(post.title && post.title.rendered));
      global.ArticleDetailRender.renderCategoryLine(refs.category, state);
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
