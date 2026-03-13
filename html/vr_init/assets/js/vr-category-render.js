(function (global) {
  "use strict";

  function makeButton(className, text, active, onClick) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = className + (active ? " zr-cat-active" : "");
    btn.textContent = text;
    if (typeof onClick === "function") {
      btn.addEventListener("click", onClick);
    }
    return btn;
  }

  function renderMainTabs(container, categories, activeId, onClick) {
    if (!container) return;
    container.innerHTML = "";

    (categories || []).forEach(function (item) {
      container.appendChild(
        makeButton(
          "zr-cat-main-tab",
          item.name,
          Number(item.id) === Number(activeId),
          function () {
            onClick(item.id);
          }
        )
      );
    });
  }

  function renderSubTabs(sectionEl, container, items, activeId, onClick) {
    if (!sectionEl || !container) return;

    var hasChildren = Array.isArray(items) && items.length > 0;
    sectionEl.hidden = !hasChildren;
    container.innerHTML = "";

    if (!hasChildren) {
      return;
    }

    items.forEach(function (item) {
      container.appendChild(
        makeButton(
          "zr-cat-sub-tab",
          item.name,
          Number(item.id) === Number(activeId),
          function () {
            onClick(item.id);
          }
        )
      );
    });
  }

  function renderSceneImages(container, scenes, labels) {
    var fallbackLabels = ["化工", "石油", "制药", "食品", "纺织"];
    container.innerHTML = "";

    (scenes || []).forEach(function (scene, index) {
      var url = "";
      var label = "";

      if (typeof scene === "string") {
        url = scene;
      } else if (scene && typeof scene === "object") {
        url = scene.imageUrl || scene.url || scene.src || "";
        label = scene.label || "";
      }

      if (!label && Array.isArray(labels) && labels[index]) {
        label = labels[index];
      }
      if (!label && fallbackLabels[index]) {
        label = fallbackLabels[index];
      }
      if (!url) return;

      var wrap = document.createElement("div");
      wrap.className = "zr-cat-scene-item";

      var img = document.createElement("img");
      img.loading = "lazy";
      img.src = url;
      img.alt = label ? ("应用范围-" + label) : ("应用范围图 " + (index + 1));
      wrap.appendChild(img);

      if (label) {
        var caption = document.createElement("div");
        caption.className = "zr-cat-scene-caption";
        caption.textContent = label;
        wrap.appendChild(caption);
      }

      container.appendChild(wrap);
    });
  }

  function renderProductCards(container, list) {
    container.innerHTML = "";

    (list || []).forEach(function (item) {
      var article = document.createElement("article");
      article.className = "zr-cat-product-card";

      var link = document.createElement("a");
      link.href = item.link || "#";
      link.target = "_blank";
      link.rel = "noopener noreferrer";

      var img = document.createElement("img");
      img.className = "zr-cat-product-thumb";
      img.loading = "lazy";
      img.src = item.imageUrl || "";
      img.alt = item.title || "产品图片";

      var body = document.createElement("div");
      body.className = "zr-cat-product-body";

      var title = document.createElement("h3");
      title.className = "zr-cat-product-title";
      title.textContent = item.title || "未命名文章";

      var summary = document.createElement("p");
      summary.className = "zr-cat-product-summary";
      summary.textContent = item.summary || "";

      body.appendChild(title);
      body.appendChild(summary);
      link.appendChild(img);
      link.appendChild(body);
      article.appendChild(link);
      container.appendChild(article);
    });
  }

  function buildPageItems(page, totalPages) {
    var items = [];

    if (totalPages <= 7) {
      for (var i = 1; i <= totalPages; i += 1) items.push(i);
      return items;
    }

    items.push(1);

    var start = Math.max(2, page - 2);
    var end = Math.min(totalPages - 1, page + 2);

    if (start > 2) items.push("...");
    for (var n = start; n <= end; n += 1) items.push(n);
    if (end < totalPages - 1) items.push("...");

    items.push(totalPages);
    return items;
  }

  function renderPagination(container, payload) {
    container.innerHTML = "";

    var page = payload.page;
    var totalPages = payload.totalPages;
    var onPageChange = payload.onPageChange;

    if (!totalPages || totalPages <= 1) {
      container.hidden = true;
      return;
    }

    container.hidden = false;

    var prev = makeButton("zr-cat-page-btn", "上一页", false, function () {
      if (page > 1) onPageChange(page - 1);
    });
    prev.disabled = page <= 1;
    container.appendChild(prev);

    buildPageItems(page, totalPages).forEach(function (item) {
      if (item === "...") {
        var dots = document.createElement("span");
        dots.className = "zr-cat-page-dots";
        dots.textContent = "...";
        container.appendChild(dots);
        return;
      }

      container.appendChild(
        makeButton("zr-cat-page-btn", String(item), Number(item) === Number(page), function () {
          onPageChange(Number(item));
        })
      );
    });

    var next = makeButton("zr-cat-page-btn", "下一页", false, function () {
      if (page < totalPages) onPageChange(page + 1);
    });
    next.disabled = page >= totalPages;
    container.appendChild(next);
  }

  function renderPageMeta(el, payload) {
    if (!el) return;
    el.textContent =
      "共 " +
      (payload.total || 0) +
      " 条 / 第 " +
      (payload.page || 1) +
      " 页 / 共 " +
      (payload.totalPages || 1) +
      " 页";
  }

  function renderStatus(refs, payload) {
    refs.loadingState.hidden = !payload.loading;

    if (payload.error) {
      refs.errorState.hidden = false;
      refs.errorState.textContent = payload.error;
    } else {
      refs.errorState.hidden = true;
      refs.errorState.textContent = "";
    }

    refs.emptyState.hidden = !payload.empty;
    refs.productGrid.hidden = payload.loading || !!payload.error || payload.empty;
    refs.pagination.hidden = payload.loading || !!payload.error || payload.empty;
  }

  global.VrCategoryRender = {
    renderMainTabs: renderMainTabs,
    renderSubTabs: renderSubTabs,
    renderSceneImages: renderSceneImages,
    renderProductCards: renderProductCards,
    renderPagination: renderPagination,
    renderPageMeta: renderPageMeta,
    renderStatus: renderStatus
  };
})(window);
