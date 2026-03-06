import { initHeroSlider } from "./modules/hero-slider.js";
import { initLightbox } from "./modules/lightbox.js";
import { initQuickCases } from "./modules/quick-cases.js";
import { initMajorProjects } from "./modules/major-projects.js";
import { initFeaturedCases } from "./modules/featured-cases.js";
import { initAboutSection } from "./modules/about-section.js";
import { initFloatingContactAdapter } from "./modules/floating-contact-adapter.js";

async function loadConfig() {
  const url = new URL("../data/home.config.json", import.meta.url);
  const response = await fetch(url.href, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load config: ${response.status}`);
  }
  return response.json();
}

function initHome(config) {
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
  box.textContent = "首页配置加载失败，请检查 index_new/assets/data/home.config.json";
  shell.prepend(box);
}

(async function bootstrap() {
  try {
    const config = await loadConfig();
    initHome(config);
  } catch (error) {
    renderFatalError(error);
  }
})();
