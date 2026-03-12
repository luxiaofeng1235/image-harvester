(function (global) {
  "use strict";

  function buildUrl(base, path) {
    return new URL(path.replace(/^\//, ""), base.replace(/\/+$/, "") + "/").href;
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
    if (!Array.isArray(categoryIds) || !categoryIds.length) {
      return Promise.resolve([]);
    }
    return requestJson(
      buildUrl(
        apiBase,
        "categories?include=" + categoryIds.join(",") + "&per_page=100&_fields=id,name,parent,slug"
      )
    );
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
