(function (global) {
  "use strict";

  function buildUrl(base, path) {
    return new URL(path.replace(/^\//, ""), base.replace(/\/+$/, "") + "/").href;
  }

  async function requestJson(url) {
    var response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      var error = new Error("Request failed: " + response.status + " " + url);
      error.status = response.status;
      error.url = url;
      throw error;
    }

    return {
      items: await response.json(),
      total: Number(response.headers.get("X-WP-Total")) || 0,
      totalPages: Number(response.headers.get("X-WP-TotalPages")) || 0
    };
  }

  function fetchPosts(apiBase, keyword, page, perPage) {
    var params = new URLSearchParams();
    params.set("search", String(keyword || "").trim());
    params.append("search_columns[]", "post_title");
    params.set("page", String(page || 1));
    params.set("per_page", String(perPage || 10));
    params.set("_embed", "1");
    params.set("orderby", "relevance");
    params.set("order", "desc");

    return requestJson(buildUrl(apiBase, "posts?" + params.toString()));
  }

  global.SearchCenterApi = {
    fetchPosts: fetchPosts
  };
})(window);
