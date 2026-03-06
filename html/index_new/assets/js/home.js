function normalizeBase(input) {
  return String(input || "").replace(/\/+$/, "");
}

function getAssetBase() {
  const customBase = window.__ZR_HOME_ASSET_BASE__;
  if (typeof customBase === "string" && customBase.trim()) {
    return normalizeBase(customBase.trim());
  }
  return normalizeBase(new URL(".", import.meta.url).href);
}

async function importFirst(candidates) {
  let lastError = null;
  for (const url of candidates) {
    try {
      return await import(url);
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error("Failed to import module");
}

async function fetchFirstJson(candidates) {
  let lastStatus = "";
  for (const url of candidates) {
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (response.ok) {
        return response.json();
      }
      lastStatus = `${response.status} (${url})`;
    } catch (error) {
      lastStatus = `${error} (${url})`;
    }
  }
  throw new Error(`Failed to load config: ${lastStatus || "unknown"}`);
}

async function loadDeps(assetBase) {
  const flat = Boolean(window.__ZR_HOME_FLAT_DIR__);
  const dep = (name) => {
    const flatUrl = `${assetBase}/${name}.js`;
    const nestedUrl = `${assetBase}/modules/${name}.js`;
    return flat ? [flatUrl, nestedUrl] : [nestedUrl, flatUrl];
  };

  const [
    { initHeroSlider },
    { initLightbox },
    { initQuickCases },
    { initMajorProjects },
    { initFeaturedCases },
    { initAboutSection },
    { initFloatingContactAdapter }
  ] = await Promise.all([
    importFirst(dep("hero-slider")),
    importFirst(dep("lightbox")),
    importFirst(dep("quick-cases")),
    importFirst(dep("major-projects")),
    importFirst(dep("featured-cases")),
    importFirst(dep("about-section")),
    importFirst(dep("floating-contact-adapter"))
  ]);

  return {
    initHeroSlider,
    initLightbox,
    initQuickCases,
    initMajorProjects,
    initFeaturedCases,
    initAboutSection,
    initFloatingContactAdapter
  };
}

async function loadConfig(assetBase) {
  const flat = Boolean(window.__ZR_HOME_FLAT_DIR__);
  const defaultConfigUrl = new URL("home.config.json", `${assetBase}/`).href;
  const nestedConfigUrl = new URL("../data/home.config.json", `${assetBase}/`).href;
  const configUrl = (typeof window.__ZR_HOME_CONFIG_URL__ === "string" && window.__ZR_HOME_CONFIG_URL__.trim())
    ? window.__ZR_HOME_CONFIG_URL__.trim()
    : defaultConfigUrl;
  const candidates = (typeof window.__ZR_HOME_CONFIG_URL__ === "string" && window.__ZR_HOME_CONFIG_URL__.trim())
    ? [configUrl]
    : (flat ? [defaultConfigUrl] : [nestedConfigUrl, defaultConfigUrl]);
  return fetchFirstJson(candidates);
}

function initHome(config, deps) {
  const {
    initHeroSlider,
    initLightbox,
    initQuickCases,
    initMajorProjects,
    initFeaturedCases,
    initAboutSection,
    initFloatingContactAdapter
  } = deps;

  if (config?.meta?.pageTitle) {
    document.title = config.meta.pageTitle;
  }

  const heroRoot = document.querySelector("#hero-slider");
  const quickCasesRoot = document.querySelector("#quick-cases-grid");
  const majorRoot = document.querySelector("#major-projects-grid");
  const featuredRoot = document.querySelector("#featured-cases-grid");
  const aboutSection = document.querySelector("#home-about");
  const floatingMount = document.querySelector("#floating-contact-mount");

  const lightboxRoot = document.querySelector("#home-lightbox");
  const lightboxApi = initLightbox(lightboxRoot);

  initHeroSlider(heroRoot, config.hero || {});
  initQuickCases(quickCasesRoot, config.quickCases || {}, lightboxApi);

  initMajorProjects(
    majorRoot,
    document.querySelector("#major-title-cn"),
    document.querySelector("#major-title-en"),
    config.majorProjects || {}
  );

  initFeaturedCases(
    featuredRoot,
    document.querySelector("#featured-brand"),
    document.querySelector("#featured-title-cn"),
    document.querySelector("#featured-title-en"),
    config.featuredCases || {}
  );

  const moreBtn = document.querySelector("#home-more-btn");
  if (moreBtn && config.moreCases?.link) {
    moreBtn.href = config.moreCases.link;
    moreBtn.textContent = config.moreCases.text || "更多案例";
  }

  initAboutSection(
    aboutSection,
    {
      brandEl: document.querySelector("#about-brand"),
      titleCnEl: document.querySelector("#about-title-cn"),
      titleEnEl: document.querySelector("#about-title-en"),
      headlineEl: document.querySelector("#about-headline"),
      paragraphsEl: document.querySelector("#about-paragraphs"),
      closingEl: document.querySelector("#about-closing")
    },
    config.about || {}
  );

  initFloatingContactAdapter(floatingMount);
}

function renderFatalError(error) {
  console.error(error);
  const shell = document.querySelector(".home-page");
  if (!shell) return;
  const box = document.createElement("div");
  box.style.padding = "24px";
  box.style.margin = "24px auto";
  box.style.width = "var(--home-page-width)";
  box.style.border = "1px solid #f0caca";
  box.style.background = "#fff7f7";
  box.style.color = "#b42318";
  box.textContent = "首页配置加载失败，请检查远程 home.config.json 路径";
  shell.prepend(box);
}

(async function bootstrap() {
  try {
    const assetBase = getAssetBase();
    const deps = await loadDeps(assetBase);
    const config = await loadConfig(assetBase);
    initHome(config, deps);
  } catch (error) {
    renderFatalError(error);
  }
})();
