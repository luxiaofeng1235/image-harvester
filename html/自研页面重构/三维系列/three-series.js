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
  var container = document.getElementById("zr-3dseries-content");
  if (!container || !typeConfig) {
    return;
  }

  container.innerHTML = "";

  container.appendChild(createPageTitle(typeConfig.pageTitle || ""));
  container.appendChild(createItems(typeConfig.cards || []));
}

function createPageTitle(titleText) {
  var title = document.createElement("h1");
  title.className = "zr-3dseries-page-title";
  title.textContent = titleText || "";
  return title;
}

function createItems(cards) {
  var items = document.createElement("div");
  items.className = "zr-3dseries-items";

  cards.forEach(function (cardConfig) {
    items.appendChild(createItem(cardConfig));
  });

  return items;
}

function createItem(cardConfig) {
  var item = document.createElement("article");
  item.className = "zr-3dseries-item";

  var card = document.createElement("div");
  card.className = "zr-3dseries-card";

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
  var title = document.createElement("div");
  title.className = "zr-3dseries-card-title";
  title.textContent = cardConfig.title || "";
  item.appendChild(card);
  item.appendChild(title);
  return item;
}
