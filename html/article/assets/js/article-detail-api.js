(function (global) {
  "use strict";

  var CATEGORY_CACHE_PREFIX = "zr:article-detail:categories:";
  var CATEGORY_CACHE_TTL = 60 * 60 * 1000;

  function buildUrl(base, path) {
    return new URL(path.replace(/^\//, ""), base.replace(/\/+$/, "") + "/").href;
  }

  function normalizeCategoryIds(categoryIds) {
    return (categoryIds || [])
      .map(function (id) {
        return Number(id);
      })
      .filter(function (id) {
        return Number.isInteger(id) && id > 0;
      })
      .sort(function (a, b) {
        return a - b;
      });
  }

  function buildCategoryCacheKey(apiBase, categoryIds) {
    return CATEGORY_CACHE_PREFIX + apiBase + "::" + normalizeCategoryIds(categoryIds).join(",");
  }

  function readCategoryCache(cacheKey) {
    try {
      var raw = global.localStorage && global.localStorage.getItem(cacheKey);
      if (!raw) {
        return null;
      }

      var payload = JSON.parse(raw);
      if (!payload || !Array.isArray(payload.data) || !payload.expiresAt) {
        global.localStorage.removeItem(cacheKey);
        return null;
      }

      return {
        data: payload.data,
        isExpired: Date.now() > Number(payload.expiresAt)
      };
    } catch (_error) {
      try {
        global.localStorage.removeItem(cacheKey);
      } catch (_innerError) {
        // Ignore storage cleanup failures.
      }
      return null;
    }
  }

  function writeCategoryCache(cacheKey, data) {
    try {
      if (!global.localStorage) {
        return;
      }

      global.localStorage.setItem(
        cacheKey,
        JSON.stringify({
          expiresAt: Date.now() + CATEGORY_CACHE_TTL,
          data: Array.isArray(data) ? data : []
        })
      );
    } catch (_error) {
      // Ignore quota and storage availability failures.
    }
  }

  async function requestJson(url) {
    var response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Request failed: " + response.status + " " + url);
    }
    return response.json();
  }

  function fetchPost(apiBase, articleId) {
    return requestJson(buildUrl(apiBase, "posts/" + articleId + "?_embed=1"));
  }

  function fetchCategories(apiBase, categoryIds) {
    var normalizedIds = normalizeCategoryIds(categoryIds);
    if (!normalizedIds.length) {
      return Promise.resolve([]);
    }

    var cacheKey = buildCategoryCacheKey(apiBase, normalizedIds);
    var cacheEntry = readCategoryCache(cacheKey);
    if (cacheEntry && !cacheEntry.isExpired) {
      return Promise.resolve(cacheEntry.data);
    }

    return requestJson(
      buildUrl(
        apiBase,
        "categories?include=" + normalizedIds.join(",") + "&per_page=100&_fields=id,name,parent,slug"
      )
    ).then(function (data) {
      writeCategoryCache(cacheKey, data);
      return data;
    }).catch(function (error) {
      if (cacheEntry && Array.isArray(cacheEntry.data)) {
        return cacheEntry.data;
      }
      throw error;
    });
  }

  function fetchPostsByCategories(apiBase, categoryIds, excludeId, perPage) {
    if (!Array.isArray(categoryIds) || !categoryIds.length) {
      return Promise.resolve([]);
    }
    return requestJson(
      buildUrl(
        apiBase,
        "posts?categories=" +
          categoryIds.join(",") +
          "&exclude=" +
          excludeId +
          "&per_page=" +
          perPage +
          "&orderby=date&order=desc&_embed=1"
      )
    );
  }

  global.ArticleDetailApi = {
    fetchPost: fetchPost,
    fetchCategories: fetchCategories,
    fetchPostsByCategories: fetchPostsByCategories
  };
})(window);
