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

  function normalizeText(text) {
    if (!text) return "";
    return String(text).replace(/\r\n/g, "\n").trim();
  }

  function filterSystemCategories(list) {
    return (Array.isArray(list) ? list : []).filter(function (item) {
      return item &&
        Number(item.id) !== 1 &&
        item.slug !== "uncategorized" &&
        item.name !== "未分类";
    });
  }

  function sortByIdOrder(list, orderIds) {
    if (!Array.isArray(orderIds) || !orderIds.length) {
      return (list || []).slice();
    }

    var orderMap = new Map();
    orderIds.forEach(function (id, index) {
      orderMap.set(Number(id), index);
    });

    return (list || []).slice().sort(function (left, right) {
      var leftRank = orderMap.has(Number(left.id)) ? orderMap.get(Number(left.id)) : Number.MAX_SAFE_INTEGER;
      var rightRank = orderMap.has(Number(right.id)) ? orderMap.get(Number(right.id)) : Number.MAX_SAFE_INTEGER;
      if (leftRank !== rightRank) return leftRank - rightRank;
      return Number(left.id) - Number(right.id);
    });
  }

  async function fetchWpCategories(url) {
    var list = await fetchJson(url);
    return filterSystemCategories(list);
  }

  function getCategoryApiBase(config) {
    return (config && config.categoryApiBase) || "https://www.zgzonre.com/wp-json/wp/v2/categories";
  }

  async function fetchParentCategories(config) {
    var mainCategories = Array.isArray(config.mainCategories) ? config.mainCategories : [];
    var parentIds = mainCategories.map(function (item) { return Number(item.parentId); }).filter(Boolean);
    var url = new URL(getCategoryApiBase(config));
    url.searchParams.set("include", parentIds.join(","));
    url.searchParams.set("orderby", "include");
    url.searchParams.set("per_page", "100");
    url.searchParams.set("_fields", "id,name,slug,parent,description,z_taxonomy_image_url");
    return fetchWpCategories(url.toString());
  }

  async function fetchChildCategories(config, parentId) {
    var url = new URL(getCategoryApiBase(config));
    url.searchParams.set("parent", String(parentId));
    url.searchParams.set("per_page", "100");
    url.searchParams.set("_fields", "id,name,slug,parent,description,z_taxonomy_image_url");
    return fetchWpCategories(url.toString());
  }

  function buildLegacyConfig(simpleConfig, parentCategories, childrenByParent) {
    var shortTitleMap = simpleConfig.shortTitleMap || {};
    var parentMap = new Map((parentCategories || []).map(function (item) {
      return [Number(item.id), item];
    }));

    var categories = (simpleConfig.mainCategories || []).map(function (entry) {
      var parentId = Number(entry.parentId);
      var parent = parentMap.get(parentId) || {};
      var childList = sortByIdOrder(childrenByParent[parentId] || [], entry.childCategoryIds);

      return {
        type: Number(entry.type || 0),
        categoryKey: parent.slug || entry.label || ("type_" + entry.type),
        categoryName: entry.label || normalizeText(parent.name).replace(/系列产品$/, ""),
        categoryDisplayName: entry.displayName || parent.name || entry.label || "产品系列",
        wpParentCategoryId: parentId,
        wpChildCategoryIds: childList.map(function (item) { return Number(item.id); }),
        defaultCopy: normalizeText(parent.description),
        defaultImage: parent.z_taxonomy_image_url || "",
        subCategories: childList.map(function (item) {
          var categoryName = normalizeText(item.name);
          return {
            key: item.slug || "",
            name: categoryName ? categoryName + "系列产品" : "",
            shortName: categoryName,
            shortTitle: shortTitleMap[String(item.id)] || "",
            wpCategoryId: Number(item.id),
            imageUrl: item.z_taxonomy_image_url || "",
            defaultCopy: normalizeText(item.description),
            slug: item.slug || "",
            parent: Number(item.parent || 0)
          };
        })
      };
    });

    var typeCategoryMap = {};
    categories.forEach(function (item) {
      typeCategoryMap[String(item.type)] = {
        categoryKey: item.categoryKey,
        categoryName: item.categoryName,
        wpChildCategoryIds: item.wpChildCategoryIds
      };
    });

    return {
      version: simpleConfig.version || "",
      configName: simpleConfig.configName || "home-category-runtime-config",
      topBannerBg: simpleConfig.topBannerBg || "",
      applicationScenes: simpleConfig.applicationScenes || [],
      applicationSceneLabels: simpleConfig.applicationSceneLabels || [],
      applicationTopImage: simpleConfig.applicationTopImage || "",
      categories: categories,
      typeCategoryMap: typeCategoryMap
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

  function buildDetailUrl(id) {
    if (!id) return "#";
    return "https://www.zgzonre.com/detail-base?article_id=" + encodeURIComponent(String(id));
  }

  function normalizePost(post) {
    var title = decodeHtml(post && post.title ? post.title.rendered : "").trim();
    var excerpt = stripHtml(post && post.excerpt ? post.excerpt.rendered : "");
    var contentText = stripHtml(post && post.content ? post.content.rendered : "");

    var summary = excerpt || contentText;
    if (summary.length > 90) summary = summary.slice(0, 90) + "...";

    var id = post && post.id ? post.id : "";

    return {
      id: id,
      title: title || "未命名文章",
      summary: summary,
      link: buildDetailUrl(id),
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
    if (config && Array.isArray(config.categories) && config.typeCategoryMap) {
      return config;
    }

    if (!config || !Array.isArray(config.mainCategories)) {
      throw new Error("配置文件结构不正确，请检查分类配置。");
    }

    var parentCategories = await fetchParentCategories(config);
    var childrenByParent = {};

    await Promise.all(config.mainCategories.map(async function (entry) {
      var parentId = Number(entry.parentId);
      childrenByParent[parentId] = await fetchChildCategories(config, parentId);
    }));

    return buildLegacyConfig(config, parentCategories, childrenByParent);
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
