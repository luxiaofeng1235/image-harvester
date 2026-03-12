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

  function buildDetailPageUrl(item) {
    var id = item && item.id;
    if (!id) {
      return (item && item.link) || "#";
    }

    var detailUrl = new URL("detail.html", window.location.href);
    detailUrl.searchParams.set("article", String(id));
    return detailUrl.href;
  }

  function renderCategoryLine(el, payload) {
    if (!el) return;
    el.innerHTML = "";

    var prefix = document.createElement("span");
    prefix.className = "zr-article-category-label";
    prefix.textContent = "分类";
    el.appendChild(prefix);

    var trail = document.createElement("span");
    trail.className = "zr-article-category-trail";
    el.appendChild(trail);

    function appendSeparator() {
      var separator = document.createElement("span");
      separator.className = "zr-article-category-separator";
      separator.setAttribute("aria-hidden", "true");
      separator.textContent = ">";
      trail.appendChild(separator);
    }

    function appendLink(name, href, isCurrent) {
      if (!name) return;
      var link = document.createElement("a");
      link.className = "zr-article-category-link" + (isCurrent ? " is-current" : "");
      link.href = href || "#";
      link.textContent = name;
      trail.appendChild(link);
    }

    var hasParent = payload.parentCategory && payload.parentCategory.name;
    var hasChild = payload.childCategory && payload.childCategory.name;

    if (payload.parentCategory && payload.parentCategory.name) {
      appendLink(payload.parentCategory.name, payload.parentCategoryUrl, !hasChild);
    }

    if (payload.childCategory && payload.childCategory.name) {
      if (trail.childNodes.length > 0) {
        appendSeparator();
      }
      appendLink(payload.childCategory.name, payload.childCategoryUrl, true);
    }

    if (!hasParent && !hasChild && payload.firstCategory && payload.firstCategory.name) {
      appendLink(payload.firstCategory.name, payload.firstCategoryUrl || "", true);
    }
  }

  function findFirstMeaningfulTextNode(root) {
    if (!root) return null;

    for (var i = 0; i < root.childNodes.length; i++) {
      var node = root.childNodes[i];
      if (node.nodeType === Node.TEXT_NODE && /\S/.test(node.nodeValue || "")) {
        return node;
      }
      if (node.nodeType === Node.ELEMENT_NODE) {
        var textNode = findFirstMeaningfulTextNode(node);
        if (textNode) {
          return textNode;
        }
      }
    }

    return null;
  }

  function sanitizeLeadingQuestionMarks(html) {
    if (!html) {
      return "<p>暂无内容。</p>";
    }

    var container = document.createElement("div");
    container.innerHTML = html;

    var firstTextNode = findFirstMeaningfulTextNode(container);
    if (firstTextNode) {
      firstTextNode.nodeValue = (firstTextNode.nodeValue || "").replace(
        /^[\s\u00a0\uFEFF]*(?:[?？]\s*){1,2}/,
        ""
      );
    }

    return container.innerHTML;
  }

  function renderContent(el, html) {
    if (!el) return;
    el.innerHTML = sanitizeLeadingQuestionMarks(html);
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
      card.href = buildDetailPageUrl(item);

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
