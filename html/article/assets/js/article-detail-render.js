(function (global) {
  "use strict";

  function setText(el, value) {
    if (!el) return;
    el.textContent = value || "";
  }

  function getFeaturedImage(item, fallback) {
    var embedded = item && item._embedded && item._embedded["wp:featuredmedia"];
    if (Array.isArray(embedded) && embedded[0] && embedded[0].source_url) {
      return embedded[0].source_url;
    }
    return fallback || "";
  }

  function renderCategoryLine(el, payload) {
    if (!el) return;
    el.innerHTML = "";

    var prefix = document.createElement("span");
    prefix.textContent = "分类：";
    el.appendChild(prefix);

    function appendLink(name, href) {
      if (!name) return;
      var link = document.createElement("a");
      link.className = "zr-article-category-link";
      link.href = href || "#";
      link.textContent = name;
      el.appendChild(link);
    }

    if (payload.parentCategory && payload.parentCategory.name) {
      appendLink(payload.parentCategory.name, payload.parentCategoryUrl);
    }

    if (payload.childCategory && payload.childCategory.name) {
      if (el.childNodes.length > 1) {
        el.appendChild(document.createTextNode(" / "));
      }
      appendLink(payload.childCategory.name, payload.childCategoryUrl);
    }

    if (el.childNodes.length === 1 && payload.firstCategory && payload.firstCategory.name) {
      appendLink(payload.firstCategory.name, payload.firstCategoryUrl || "");
    }
  }

  function renderContent(el, html) {
    if (!el) return;
    el.innerHTML = html || "<p>暂无内容。</p>";
  }

  function renderPostNavigation(el, payload) {
    if (!el) return;
    var prev = payload.previousPost;
    var next = payload.nextPost;
    if (!prev && !next) {
      el.hidden = true;
      el.innerHTML = "";
      return;
    }

    el.hidden = false;
    el.innerHTML = "";

    if (prev) {
      var prevLink = document.createElement("a");
      prevLink.className = "zr-article-post-link is-prev";
      prevLink.href = prev.href;
      prevLink.innerHTML =
        '<span class="zr-article-post-label">上一篇</span>' +
        '<span class="zr-article-post-title">' +
        prev.title +
        "</span>";
      el.appendChild(prevLink);
    } else {
      var prevEmpty = document.createElement("div");
      prevEmpty.className = "zr-article-post-link is-prev";
      prevEmpty.style.visibility = "hidden";
      el.appendChild(prevEmpty);
    }

    if (next) {
      var nextLink = document.createElement("a");
      nextLink.className = "zr-article-post-link is-next";
      nextLink.href = next.href;
      nextLink.innerHTML =
        '<span class="zr-article-post-label">下一篇</span>' +
        '<span class="zr-article-post-title">' +
        next.title +
        "</span>";
      el.appendChild(nextLink);
    } else {
      var nextEmpty = document.createElement("div");
      nextEmpty.className = "zr-article-post-link is-next";
      nextEmpty.style.visibility = "hidden";
      el.appendChild(nextEmpty);
    }
  }

  function renderRecommendations(sectionEl, gridEl, items, fallbackImage) {
    if (!sectionEl || !gridEl) return;

    if (!Array.isArray(items) || !items.length) {
      sectionEl.hidden = true;
      gridEl.innerHTML = "";
      return;
    }

    sectionEl.hidden = false;
    gridEl.innerHTML = "";

    items.forEach(function (item) {
      var card = document.createElement("a");
      card.className = "zr-article-recommend-card";
      card.href = item.link || "#";
      card.target = "_blank";
      card.rel = "noopener noreferrer";

      var image = document.createElement("img");
      image.className = "zr-article-recommend-image";
      image.loading = "lazy";
      image.src = getFeaturedImage(item, fallbackImage);
      image.alt = item.title && item.title.rendered ? item.title.rendered.replace(/<[^>]+>/g, "") : "推荐产品";

      var body = document.createElement("div");
      body.className = "zr-article-recommend-body";

      var title = document.createElement("div");
      title.className = "zr-article-recommend-title";
      title.innerHTML = item.title && item.title.rendered ? item.title.rendered : "未命名文章";

      body.appendChild(title);
      card.appendChild(image);
      card.appendChild(body);
      gridEl.appendChild(card);
    });
  }

  global.ArticleDetailRender = {
    setText: setText,
    renderCategoryLine: renderCategoryLine,
    renderContent: renderContent,
    renderPostNavigation: renderPostNavigation,
    renderRecommendations: renderRecommendations
  };
})(window);
