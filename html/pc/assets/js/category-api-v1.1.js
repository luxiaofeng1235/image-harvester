(function (global) {
  "use strict";

  function decodeHtml(text) {
    if (!text) return "";
    var textarea = document.createElement("textarea");
    textarea.innerHTML = text;
    return textarea.value;
  }

  function stripHtml(html) {
    if (!html) return "";
    var div = document.createElement("div");
    div.innerHTML = html;
    var raw = div.textContent || div.innerText || "";
    return raw.replace(/\s+/g, " ").trim();
  }

  function getFeaturedImage(post) {
    if (!post) return "";

    var embedded = post._embedded && post._embedded["wp:featuredmedia"];
    if (Array.isArray(embedded) && embedded[0] && embedded[0].source_url) {
      return embedded[0].source_url;
    }

    var contentHtml = post.content && post.content.rendered ? post.content.rendered : "";
    var match = contentHtml.match(/<img[^>]+src=["']([^"']+)["']/i);
    return match ? match[1] : "";
  }

  function normalizePost(post) {
    var title = decodeHtml(post && post.title ? post.title.rendered : "").trim();
    var excerpt = stripHtml(post && post.excerpt ? post.excerpt.rendered : "");
    var contentText = stripHtml(post && post.content ? post.content.rendered : "");

    var summary = excerpt || contentText;
    if (summary.length > 90) summary = summary.slice(0, 90) + "...";

    var link = post && post.link ? post.link : "";
    var slug = post && post.slug ? post.slug : "";
    var id = post && post.id ? post.id : "";

    if (!link) {
      if (slug) {
        link = "https://www.zgzonre.com/index.php/" + slug + "/";
      } else if (id) {
        link = "https://www.zgzonre.com/?p=" + id;
      }
    }

    return {
      id: id,
      title: title || "未命名文章",
      summary: summary,
      link: link,
      imageUrl: getFeaturedImage(post),
      categories: Array.isArray(post && post.categories) ? post.categories : []
    };
  }

  async function fetchJson(url, options) {
    var response = await fetch(url, options || {});
    if (!response.ok) {
      var message = "请求失败：" + response.status;
      try {
        var errorBody = await response.json();
        if (errorBody && errorBody.message) {
          message = errorBody.message;
        }
      } catch (_err) {
        // ignore response body parse error
      }
      throw new Error(message);
    }
    return response.json();
  }

  async function fetchConfig(url, options) {
    var config = await fetchJson(url, options || {});
    if (!config || !Array.isArray(config.categories) || !config.typeCategoryMap) {
      throw new Error("配置文件结构不正确，请检查 home-category-content-config.json");
    }
    return config;
  }

  async function fetchPosts(params) {
    var apiBase = params.apiBase;
    var categories = params.categories;
    var page = params.page || 1;
    var perPage = params.perPage || 9;
    var signal = params.signal;

    var url = new URL(apiBase);
    url.searchParams.set("categories", categories.join(","));
    url.searchParams.set("per_page", String(perPage));
    url.searchParams.set("page", String(page));
    url.searchParams.set("orderby", "date");
    url.searchParams.set("order", "desc");
    url.searchParams.set("_embed", "1");

    var response = await fetch(url.toString(), { signal: signal });
    if (!response.ok) {
      var text = await response.text();
      var errorMessage = "文章列表请求失败：" + response.status;
      if (text) {
        try {
          var json = JSON.parse(text);
          if (json && json.message) errorMessage = json.message;
        } catch (_parseErr) {
          // ignore parse error
        }
      }
      throw new Error(errorMessage);
    }

    var total = Number(response.headers.get("X-WP-Total") || 0);
    var totalPages = Number(response.headers.get("X-WP-TotalPages") || 0);
    var data = await response.json();

    return {
      list: Array.isArray(data) ? data.map(normalizePost) : [],
      total: Number.isFinite(total) ? total : 0,
      totalPages: Number.isFinite(totalPages) ? totalPages : 0,
      page: page
    };
  }

  global.CategoryApi = {
    fetchConfig: fetchConfig,
    fetchPosts: fetchPosts,
    normalizePost: normalizePost
  };
})(window);
