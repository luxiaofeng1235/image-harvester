import { initSharedSlider } from "../plugin/shared-slider.js";

var root = document.getElementById("zr-3dseries-root");

if (root) {
  initStandalonePreview();
  initPage();
}

async function initPage() {
  try {
    var config = await loadConfig(root.getAttribute("data-config"));
    var currentTypeKey = resolveType(config, getTypeParam() || root.getAttribute("data-default-type"));
    var currentType = config.types[currentTypeKey];

    root.dataset.type = currentTypeKey;
    applySliderAssets(config.slider || {});
    renderType(currentType);
    initSharedSlider(document.getElementById("zr-3dseries-slider"), config.slider || {});
  } catch (error) {
    console.error("Failed to render three series page.", error);
  }
}

function initStandalonePreview() {
  if (!document.body || root.parentElement !== document.body) {
    return;
  }

  document.body.style.margin = "0";
  document.body.style.backgroundColor = "#ffffff";
}

async function loadConfig(url) {
  var response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Config request failed: " + response.status);
  }
  return response.json();
}

function getTypeParam() {
  var params = new URLSearchParams(window.location.search);
  return params.get("type");
}

function resolveType(config, rawType) {
  var normalized = String(rawType || "").trim();
  var aliases = config.aliases || {};
  var fallbackType = String(root.getAttribute("data-default-type") || "1").trim();
  return (
    aliases[normalized] ||
    aliases[normalized.toLowerCase()] ||
    aliases[fallbackType] ||
    fallbackType
  );
}

function applySliderAssets(sliderConfig) {
  if (sliderConfig.arrowLeft) {
    root.style.setProperty("--zr-3dseries-arrow-left", 'url("' + sliderConfig.arrowLeft + '")');
  }
  if (sliderConfig.arrowRight) {
    root.style.setProperty("--zr-3dseries-arrow-right", 'url("' + sliderConfig.arrowRight + '")');
  }
}

function renderType(typeConfig) {
  var shell = document.getElementById("zr-3dseries-content-shell");
  var container = document.getElementById("zr-3dseries-content");
  if (!shell || !container || !typeConfig) {
    return;
  }

  shell.style.paddingTop = String(typeConfig.contentOffset || 0) + "px";
  container.style.height = String(typeConfig.contentHeight || 0) + "px";
  container.innerHTML = "";

  container.appendChild(createPageTitle(typeConfig.pageTitle || {}));
  (typeConfig.cards || []).forEach(function (card) {
    container.appendChild(createCard(card));
    container.appendChild(createCardTitle(card, typeConfig.cardTitleAlign || "left"));
  });
}

function createPageTitle(titleConfig) {
  var title = document.createElement("h1");
  title.className = "zr-3dseries-page-title";
  title.textContent = titleConfig.text || "";
  applyBoxStyle(title, titleConfig.box || {});
  return title;
}

function createCard(cardConfig) {
  var card = document.createElement("article");
  card.className = "zr-3dseries-card";
  applyBoxStyle(card, cardConfig.frame || {});

  var iframe = document.createElement("iframe");
  iframe.src = cardConfig.iframeUrl || "";
  iframe.title = cardConfig.title || "";
  iframe.loading = "lazy";
  iframe.setAttribute("frameborder", "0");
  iframe.setAttribute("scrolling", "no");
  iframe.setAttribute("allowtransparency", "true");
  if (cardConfig.allow) {
    iframe.setAttribute("allow", cardConfig.allow);
  }

  card.appendChild(iframe);
  return card;
}

function createCardTitle(cardConfig, defaultAlign) {
  var title = document.createElement("div");
  title.className = "zr-3dseries-card-title";
  title.textContent = cardConfig.title || "";
  title.style.textAlign = cardConfig.titleAlign || defaultAlign || "left";
  applyBoxStyle(title, cardConfig.titleBox || {});
  return title;
}

function applyBoxStyle(node, box) {
  if (!node || !box) {
    return;
  }

  if (box.left !== undefined) {
    node.style.left = String(box.left) + "px";
  }
  if (box.top !== undefined) {
    node.style.top = String(box.top) + "px";
  }
  if (box.width !== undefined) {
    node.style.width = String(box.width) + "px";
  }
  if (box.height !== undefined) {
    node.style.height = String(box.height) + "px";
  }
}
