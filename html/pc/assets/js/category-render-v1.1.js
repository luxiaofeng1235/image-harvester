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

  function renderMainCategoryTabs(container, categories, activeType, onClick) {
    container.innerHTML = "";
    categories.forEach(function (item) {
      var type = String(item.type);
      var btn = makeButton(
        "zr-cat-main-tab",
        item.categoryName,
        type === String(activeType),
        function () {
          onClick(type);
        }
      );
      container.appendChild(btn);
    });
  }

  function renderSubCategoryTabs(container, subCategories, activeSubId, onClick) {
    container.innerHTML = "";
    subCategories.forEach(function (item) {
      var btn = makeButton(
        "zr-cat-sub-tab",
        item.shortName || item.name,
        Number(activeSubId) === Number(item.wpCategoryId),
        function () {
          onClick(item.wpCategoryId);
        }
      );
      container.appendChild(btn);
    });
  }

  function renderHighlight(refs, payload) {
    refs.highlightTitle.textContent = payload.title || "产品系列";
    var brief = payload.brief || "";
    if (refs.highlightContent) {
      refs.highlightContent.classList.toggle("zr-cat-is-category-title", !!payload.isCategoryTitle);
      refs.highlightContent.classList.toggle("zr-cat-has-brief", !!brief);
    }
    if (refs.highlightBrief) {
      refs.highlightBrief.textContent = brief;
      refs.highlightBrief.hidden = !brief;
    }
    refs.highlightCopy.textContent = payload.copy || "";

    if (payload.imageUrl) {
      refs.highlightImage.src = payload.imageUrl;
      refs.highlightImage.alt = payload.title || "分类主图";
    } else {
      refs.highlightImage.removeAttribute("src");
      refs.highlightImage.alt = "";
    }
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

  function renderProductCards(container, list, options) {
    container.innerHTML = "";
    var fallbackImage = options && options.fallbackImage ? options.fallbackImage : "";

    list.forEach(function (item) {
      var article = document.createElement("article");
      article.className = "zr-cat-product-card";

      var link = document.createElement("a");
      link.href = item.link || "#";
      link.target = "_blank";
      link.rel = "noopener noreferrer";

      var img = document.createElement("img");
      img.className = "zr-cat-product-thumb";
      img.loading = "lazy";
      img.src = item.imageUrl || fallbackImage || "";
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
      for (var i = 1; i <= totalPages; i++) items.push(i);
      return items;
    }

    items.push(1);

    var start = Math.max(2, page - 2);
    var end = Math.min(totalPages - 1, page + 2);

    if (start > 2) items.push("...");

    for (var n = start; n <= end; n++) items.push(n);

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

    var pageItems = buildPageItems(page, totalPages);
    pageItems.forEach(function (item) {
      if (item === "...") {
        var dots = document.createElement("span");
        dots.className = "zr-cat-page-dots";
        dots.textContent = "...";
        container.appendChild(dots);
        return;
      }

      var btn = makeButton("zr-cat-page-btn", String(item), Number(item) === Number(page), function () {
        onPageChange(Number(item));
      });
      container.appendChild(btn);
    });

    var next = makeButton("zr-cat-page-btn", "下一页", false, function () {
      if (page < totalPages) onPageChange(page + 1);
    });
    next.disabled = page >= totalPages;
    container.appendChild(next);
  }

  function renderPageMeta(el, payload) {
    var total = payload.total || 0;
    var page = payload.page || 1;
    var totalPages = payload.totalPages || 1;
    el.textContent = "共 " + total + " 条 / 第 " + page + " 页 / 共 " + totalPages + " 页";
  }

  function renderStatus(refs, payload) {
    var loading = !!payload.loading;
    var error = payload.error || "";
    var empty = !!payload.empty;

    refs.loadingState.hidden = !loading;

    if (error) {
      refs.errorState.hidden = false;
      refs.errorState.textContent = error;
    } else {
      refs.errorState.hidden = true;
      refs.errorState.textContent = "";
    }

    refs.emptyState.hidden = !empty;

    var showGrid = !loading && !error && !empty;
    refs.productGrid.hidden = !showGrid;
    if (!showGrid) refs.pagination.hidden = true;
  }

  global.CategoryRender = {
    renderMainCategoryTabs: renderMainCategoryTabs,
    renderSubCategoryTabs: renderSubCategoryTabs,
    renderHighlight: renderHighlight,
    renderSceneImages: renderSceneImages,
    renderProductCards: renderProductCards,
    renderPagination: renderPagination,
    renderPageMeta: renderPageMeta,
    renderStatus: renderStatus
  };
})(window);
