(function (global) {
  "use strict";

  function fetchJson(url, options) {
    return fetch(url, options || {}).then(function (response) {
      if (!response.ok) {
        throw new Error("请求失败：" + response.status);
      }
      return response.json();
    });
  }

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

  function normalizeText(text) {
    if (!text) return "";
    return String(text).replace(/\r\n/g, "\n").trim();
  }

  function filterSystemCategories(list) {
    return (Array.isArray(list) ? list : []).filter(function (item) {
      return (
        item &&
        Number(item.id) !== 1 &&
        item.slug !== "uncategorized" &&
        item.name !== "未分类"
      );
    });
  }

  function simplifyCategory(item, order) {
    return {
      id: Number(item && item.id) || 0,
      name: item && item.name ? String(item.name) : "",
      parent: Number(item && item.parent) || 0,
      slug: item && item.slug ? String(item.slug) : "",
      count: Number(item && item.count) || 0,
      order: order
    };
  }

  function sortByOrder(list) {
    return (list || []).slice().sort(function (left, right) {
      if (Number(left.order) !== Number(right.order)) {
        return Number(left.order) - Number(right.order);
      }
      return Number(left.id) - Number(right.id);
    });
  }

  function buildVrTree(rootId, categories) {
    var all = filterSystemCategories(categories).map(function (item, index) {
      return simplifyCategory(item, index);
    });

    var categoryMap = {};
    var childrenByParent = {};

    all.forEach(function (item) {
      categoryMap[item.id] = item;
      if (!childrenByParent[item.parent]) {
        childrenByParent[item.parent] = [];
      }
      childrenByParent[item.parent].push(item);
    });

    var root = categoryMap[Number(rootId) || 0] || null;
    if (!root) {
      throw new Error("未找到 VR 根分类。");
    }

    var secondLevel = sortByOrder(childrenByParent[root.id] || []).map(function (item) {
      var children = sortByOrder(childrenByParent[item.id] || []).map(function (child) {
        return {
          id: child.id,
          name: child.name,
          slug: child.slug,
          parent: child.parent,
          count: child.count,
          imageUrl: "",
          copy: ""
        };
      });

      return {
        id: item.id,
        name: item.name,
        slug: item.slug,
        parent: item.parent,
        count: item.count,
        imageUrl: "",
        copy: "",
        children: children
      };
    });

    return {
      root: {
        id: root.id,
        name: root.name,
        slug: root.slug,
        parent: root.parent,
        count: root.count
      },
      secondLevel: secondLevel
    };
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

  function buildDetailUrl(base, id) {
    if (!base || !id) return "#";

    try {
      var url = new URL(base, global.location.href);
      url.searchParams.set("article_id", String(id));
      return url.href;
    } catch (_error) {
      var joiner = base.indexOf("?") === -1 ? "?" : "&";
      return base + joiner + "article_id=" + encodeURIComponent(String(id));
    }
  }

  function normalizePost(post, detailBase) {
    var title = decodeHtml(post && post.title ? post.title.rendered : "").trim();
    var excerpt = stripHtml(post && post.excerpt ? post.excerpt.rendered : "");
    var contentText = stripHtml(post && post.content ? post.content.rendered : "");
    var summary = excerpt || contentText;

    if (summary.length > 90) {
      summary = summary.slice(0, 90) + "...";
    }

    return {
      id: post && post.id ? post.id : "",
      title: title || "未命名文章",
      summary: summary,
      link: buildDetailUrl(detailBase, post && post.id),
      imageUrl: getFeaturedImage(post),
      categories: Array.isArray(post && post.categories) ? post.categories : []
    };
  }

  function fetchConfig(url) {
    return fetchJson(url);
  }

  function fetchVrCategoryTree(apiBase, rootId) {
    var url = new URL(apiBase);
    url.searchParams.set("per_page", "100");
    url.searchParams.set("_fields", "id,name,parent,slug,count");
    return fetchJson(url.toString()).then(function (categories) {
      return buildVrTree(rootId, categories);
    });
  }

  function fetchPosts(params) {
    var url = new URL(params.postApiBase);
    url.searchParams.set("categories", (params.categories || []).join(","));
    url.searchParams.set("per_page", String(params.perPage || 9));
    url.searchParams.set("page", String(params.page || 1));
    url.searchParams.set("orderby", "date");
    url.searchParams.set("order", "desc");
    url.searchParams.set("_embed", "1");

    return fetch(url.toString(), { signal: params.signal }).then(function (response) {
      if (!response.ok) {
        throw new Error("文章列表请求失败：" + response.status);
      }

      var total = Number(response.headers.get("X-WP-Total") || 0);
      var totalPages = Number(response.headers.get("X-WP-TotalPages") || 0);

      return response.json().then(function (list) {
        return {
          list: Array.isArray(list)
            ? list.map(function (item) {
                return normalizePost(item, params.detailBase);
              })
            : [],
          total: Number.isFinite(total) ? total : 0,
          totalPages: Number.isFinite(totalPages) ? totalPages : 0,
          page: params.page || 1
        };
      });
    });
  }

  global.VrCategoryApi = {
    fetchConfig: fetchConfig,
    fetchVrCategoryTree: fetchVrCategoryTree,
    fetchPosts: fetchPosts
  };
})(window);
