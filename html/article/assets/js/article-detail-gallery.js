(function (global) {
  "use strict";

  var STYLE_ID = "zr-article-gallery-style";
  var GALLERY_CLASS = "zr-article-gallery";
  var MAX_IMAGE_COUNT = 3;

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }

    var style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent =
      "." + GALLERY_CLASS + "{" +
      "margin:0 0 28px;" +
      "padding:0;" +
      "}" +
      "." + GALLERY_CLASS + "-stage{" +
      "position:relative;" +
      "display:flex;" +
      "align-items:center;" +
      "justify-content:center;" +
      "overflow:hidden;" +
      "border-radius:0;" +
      "background:transparent;" +
      "box-shadow:none;" +
      "}" +
      "." + GALLERY_CLASS + "-main{" +
      "display:block;" +
      "width:100%;" +
      "height:auto;" +
      "max-height:720px;" +
      "object-fit:contain;" +
      "background:#ffffff;" +
      "}" +
      "." + GALLERY_CLASS + "-thumbs{" +
      "display:flex;" +
      "gap:10px;" +
      "align-items:center;" +
      "justify-content:flex-start;" +
      "flex-wrap:wrap;" +
      "margin-top:14px;" +
      "}" +
      "." + GALLERY_CLASS + "-thumb{" +
      "display:inline-flex;" +
      "align-items:center;" +
      "justify-content:center;" +
      "width:50px;" +
      "height:50px;" +
      "padding:0;" +
      "border:2px solid transparent;" +
      "border-radius:10px;" +
      "background:#ffffff;" +
      "box-shadow:0 2px 8px rgba(15,23,42,0.08);" +
      "cursor:pointer;" +
      "overflow:hidden;" +
      "transition:border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;" +
      "}" +
      "." + GALLERY_CLASS + "-thumb:hover{" +
      "transform:translateY(-1px);" +
      "border-color:#e2e8f0;" +
      "}" +
      "." + GALLERY_CLASS + "-thumb.is-active{" +
      "border-color:#d1d5db;" +
      "box-shadow:0 4px 12px rgba(15,23,42,0.08);" +
      "}" +
      "." + GALLERY_CLASS + "-thumb img{" +
      "display:block;" +
      "width:100%;" +
      "height:100%;" +
      "object-fit:cover;" +
      "}" +
      "." + GALLERY_CLASS + "-thumbs[hidden]{" +
      "display:none !important;" +
      "}" +
      "@media (max-width: 768px){" +
      "." + GALLERY_CLASS + "-stage{" +
      "border-radius:0;" +
      "}" +
      "." + GALLERY_CLASS + "-thumbs{" +
      "gap:8px;" +
      "margin-top:12px;" +
      "}" +
      "}";
    document.head.appendChild(style);
  }

  function isNonEmptyText(value) {
    return /\S/.test(String(value || "").replace(/\u00a0/g, " "));
  }

  function normalizeImageSrc(image) {
    if (!image) {
      return "";
    }

    var src = image.getAttribute("src") || image.getAttribute("data-src") || image.currentSrc || "";
    return String(src).trim();
  }

  function isExtractableImage(image) {
    var src = normalizeImageSrc(image);
    return !!src && src.indexOf("data:") !== 0;
  }

  function collectImagesFromElement(element) {
    if (!element || element.nodeType !== Node.ELEMENT_NODE) {
      return [];
    }

    var images = [];
    if (element.tagName === "IMG" && isExtractableImage(element)) {
      images.push(element);
    }

    Array.prototype.forEach.call(element.querySelectorAll("img"), function (image) {
      if (isExtractableImage(image)) {
        images.push(image);
      }
    });

    return images;
  }

  function getElementMeaningfulText(element) {
    if (!element || element.nodeType !== Node.ELEMENT_NODE) {
      return "";
    }

    var clone = element.cloneNode(true);
    Array.prototype.forEach.call(
      clone.querySelectorAll("img,picture,source,video,audio,iframe,svg,canvas,script,style,noscript"),
      function (node) {
        if (node && node.parentNode) {
          node.parentNode.removeChild(node);
        }
      }
    );

    return String(clone.textContent || "").replace(/\s+/g, "").replace(/\u00a0/g, "");
  }

  function isIgnorableLeadingNode(node) {
    if (!node) {
      return true;
    }

    if (node.nodeType === Node.TEXT_NODE) {
      return !isNonEmptyText(node.nodeValue);
    }

    if (node.nodeType !== Node.ELEMENT_NODE) {
      return true;
    }

    if (node.tagName === "BR") {
      return true;
    }

    return !collectImagesFromElement(node).length && !getElementMeaningfulText(node);
  }

  function findLeadingGalleryItems(root, maxCount) {
    var items = [];
    var seen = {};
    var nodes = Array.prototype.slice.call(root.childNodes);

    for (var i = 0; i < nodes.length && items.length < maxCount; i += 1) {
      var node = nodes[i];

      if (isIgnorableLeadingNode(node)) {
        continue;
      }

      if (node.nodeType !== Node.ELEMENT_NODE) {
        break;
      }

      var images = collectImagesFromElement(node);
      var meaningfulText = getElementMeaningfulText(node);

      if (!images.length || meaningfulText) {
        break;
      }

      for (var j = 0; j < images.length && items.length < maxCount; j += 1) {
        var image = images[j];
        var src = normalizeImageSrc(image);

        if (!src || seen[src]) {
          continue;
        }

        seen[src] = true;
        items.push({
          src: src,
          alt: image.getAttribute("alt") || "",
          removableNode: node,
          imageNode: image
        });
      }
    }

    return items;
  }

  function removeExtractedNodes(items) {
    var removedNodes = [];

    items.forEach(function (item) {
      var removableNode = item.removableNode;
      if (
        removableNode &&
        removableNode.parentNode &&
        removedNodes.indexOf(removableNode) === -1
      ) {
        removedNodes.push(removableNode);
        removableNode.parentNode.removeChild(removableNode);
        return;
      }

      if (item.imageNode && item.imageNode.parentNode) {
        item.imageNode.parentNode.removeChild(item.imageNode);
      }
    });
  }

  function pruneLeadingEmptyNodes(root) {
    while (root.firstChild && isIgnorableLeadingNode(root.firstChild)) {
      root.removeChild(root.firstChild);
    }
  }

  function createGallery(root, items) {
    var wrapper = document.createElement("div");
    wrapper.className = GALLERY_CLASS;

    var stage = document.createElement("div");
    stage.className = GALLERY_CLASS + "-stage";

    var mainImage = document.createElement("img");
    mainImage.className = GALLERY_CLASS + "-main";
    mainImage.alt = items[0].alt || "文章图片";
    mainImage.src = items[0].src;
    mainImage.loading = "eager";
    mainImage.decoding = "async";

    stage.appendChild(mainImage);
    wrapper.appendChild(stage);

    var thumbs = document.createElement("div");
    thumbs.className = GALLERY_CLASS + "-thumbs";
    thumbs.setAttribute("aria-label", "文章图片切换");

    if (items.length <= 1) {
      thumbs.hidden = true;
    }

    function select(index) {
      var active = items[index];
      if (!active) {
        return;
      }

      mainImage.src = active.src;
      mainImage.alt = active.alt || "文章图片";

      Array.prototype.forEach.call(thumbs.children, function (button, buttonIndex) {
        var isActive = buttonIndex === index;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      });
    }

    items.forEach(function (item, index) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = GALLERY_CLASS + "-thumb" + (index === 0 ? " is-active" : "");
      button.setAttribute("aria-label", "切换到第" + (index + 1) + "张图片");
      button.setAttribute("aria-pressed", index === 0 ? "true" : "false");

      var thumbImage = document.createElement("img");
      thumbImage.alt = item.alt || "文章缩略图";
      thumbImage.src = item.src;
      thumbImage.loading = index === 0 ? "eager" : "lazy";
      thumbImage.decoding = "async";

      button.appendChild(thumbImage);
      button.addEventListener("click", function () {
        select(index);
      });
      thumbs.appendChild(button);
    });

    wrapper.appendChild(thumbs);
    root.insertBefore(wrapper, root.firstChild || null);
  }

  function removeExistingGallery(root) {
    if (!root || !root.firstElementChild) {
      return;
    }

    if (root.firstElementChild.classList.contains(GALLERY_CLASS)) {
      root.removeChild(root.firstElementChild);
    }
  }

  function enhance(root) {
    if (!root) {
      return;
    }

    injectStyles();
    removeExistingGallery(root);

    var items = findLeadingGalleryItems(root, MAX_IMAGE_COUNT);
    if (!items.length) {
      return;
    }

    removeExtractedNodes(items);
    pruneLeadingEmptyNodes(root);
    createGallery(root, items);
  }

  global.ArticleDetailGallery = {
    enhance: enhance
  };
})(window);
