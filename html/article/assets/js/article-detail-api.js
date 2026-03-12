(function (global) {
  "use strict";

  var CATEGORY_CACHE_PREFIX = "zr:article-detail:category-index:";
  var CATEGORY_CACHE_TTL = 60 * 60 * 1000;

  function buildUrl(base, path) {
    return new URL(path.replace(/^\//, ""), base.replace(/\/+$/, "") + "/").href;
  }

  function sanitizeCategoryIds(categoryIds) {
    var seen = {};

    return (categoryIds || [])
      .map(function (id) {
        return Number(id);
      })
      .filter(function (id) {
        if (!Number.isInteger(id) || id <= 0 || seen[id]) {
          return false;
        }
        seen[id] = true;
        return true;
      });
  }

  function buildCategoryCacheKey(apiBase) {
    return CATEGORY_CACHE_PREFIX + apiBase + "::page-1";
  }

  function simplifyCategory(item) {
    return {
      id: Number(item && item.id) || 0,
      name: item && item.name ? String(item.name) : "",
      parent: Number(item && item.parent) || 0,
      slug: item && item.slug ? String(item.slug) : "",
      count: Number(item && item.count) || 0
    };
  }

  function buildCategoryIndex(items) {
    var categories = Array.isArray(items) ? items.map(simplifyCategory).filter(function (item) {
      return item.id > 0 && item.name;
    }) : [];

    var topLevelIdMap = {};
    categories.forEach(function (item) {
      if (item.parent === 0) {
        topLevelIdMap[item.id] = true;
      }
    });

    return categories.filter(function (item) {
      return item.parent === 0 || topLevelIdMap[item.parent];
    });
  }

  function pickCategoriesFromIndex(items, categoryIds) {
    var requestedIds = sanitizeCategoryIds(categoryIds);
    if (!requestedIds.length) {
      return [];
    }

    var categoryMap = {};
    items.forEach(function (item) {
      categoryMap[item.id] = item;
    });

    var selected = [];
    var selectedIdMap = {};

    function appendCategory(id) {
      var numericId = Number(id) || 0;
      if (!numericId || selectedIdMap[numericId] || !categoryMap[numericId]) {
        return;
      }
      selectedIdMap[numericId] = true;
      selected.push(categoryMap[numericId]);
    }

    requestedIds.forEach(function (id) {
      appendCategory(id);
    });

    requestedIds.forEach(function (id) {
      var item = categoryMap[id];
      if (item && item.parent > 0) {
        appendCategory(item.parent);
      }
    });

    return selected;
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

  function fetchCategoryIndex(apiBase) {
    var cacheKey = buildCategoryCacheKey(apiBase);
    var cacheEntry = readCategoryCache(cacheKey);
    if (cacheEntry && !cacheEntry.isExpired) {
      return Promise.resolve(cacheEntry.data);
    }

    return requestJson(
      buildUrl(apiBase, "categories?per_page=100&page=1&_fields=id,name,parent,slug,count")
    ).then(function (data) {
      var categoryIndex = buildCategoryIndex(data);
      writeCategoryCache(cacheKey, categoryIndex);
      return categoryIndex;
    }).catch(function (error) {
      if (cacheEntry && Array.isArray(cacheEntry.data)) {
        return cacheEntry.data;
      }
      throw error;
    });
  }

  function fetchCategories(apiBase, categoryIds) {
    var requestedIds = sanitizeCategoryIds(categoryIds);
    if (!requestedIds.length) {
      return Promise.resolve([]);
    }

    return fetchCategoryIndex(apiBase).then(function (categoryIndex) {
      return pickCategoriesFromIndex(categoryIndex, requestedIds);
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
