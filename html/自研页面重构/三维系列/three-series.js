import { initSharedSlider } from "https://static.jsss999.com/upload/zrsite/plugin/shared-slider.js?v=20260319-oss-1";

var root = document.getElementById("zr-3dseries-root");

if (root) {
  root.setAttribute("data-zr-3dseries-page", "1");
  initStandalonePreview();
  initPage();
}

async function initPage() {
  try {
    var config = await loadConfig(root.getAttribute("data-config"));
    var currentTypeKey = resolveType(config, getTypeParam() || root.getAttribute("data-default-type"));
    var currentType = config.types[currentTypeKey];
    var sliderConfig = resolveSliderConfig(config, currentType);

    root.dataset.type = currentTypeKey;
    applySliderAssets(sliderConfig);
    renderType(currentType);
    initSharedSlider(document.getElementById("zr-3dseries-slider"), sliderConfig);
  } catch (error) {
    console.error("Failed to render three series page.", error);
  }
}

function initStandalonePreview() {
  if (!document.body || root.parentElement !== document.body) {
    return;
  }

  document.documentElement.style.backgroundColor = "#ffffff";
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

function resolveSliderConfig(config, currentType) {
  var baseSlider = config.slider || {};
  var typeSlider = (currentType && currentType.slider) || {};
  return {
    interval: typeSlider.interval || baseSlider.interval,
    effect: typeSlider.effect || baseSlider.effect,
    arrowLeft: typeSlider.arrowLeft || baseSlider.arrowLeft,
    arrowRight: typeSlider.arrowRight || baseSlider.arrowRight,
    slides: typeSlider.slides || baseSlider.slides || []
  };
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

  container.setAttribute("data-zr-3dseries-content", "1");
  container.innerHTML = "";

  container.appendChild(createPageTitle(typeConfig.pageTitle || ""));
  container.appendChild(createItems(typeConfig.cards || []));
}

function createPageTitle(titleText) {
  var title = document.createElement("h1");
  title.className = "zr-3dseries-page-title";
  title.setAttribute("data-zr-3dseries-title", "1");
  title.textContent = titleText || "";
  return title;
}

function createItems(cards) {
  var items = document.createElement("div");
  items.className = "zr-3dseries-items";
  items.setAttribute("data-zr-3dseries-items", "1");

  cards.forEach(function (cardConfig) {
    items.appendChild(createItem(cardConfig));
  });

  return items;
}

function createItem(cardConfig) {
  var item = document.createElement("article");
  item.className = "zr-3dseries-item";
  item.setAttribute("data-zr-3dseries-item", "1");

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
