export function initHeroSlider(root, config) {
  if (!root || !config || !Array.isArray(config.slides)) {
    return;
  }

  const track = root.querySelector("#hero-track");
  const prevBtn = root.querySelector("#hero-prev");
  const nextBtn = root.querySelector("#hero-next");
  const dotsWrap = root.querySelector("#hero-dots");

  if (!track || !prevBtn || !nextBtn || !dotsWrap || !config.slides.length) {
    return;
  }

  const slides = config.slides;
  const transitionMs = Number(config.transitionDuration) || 500;
  const autoplayMs = Number(config.autoplayInterval) || 4000;
  const shouldLoop = Boolean(config.loop && slides.length > 1);
  const pauseOnHover = Boolean(config.pauseOnHover);
  const keyboard = Boolean(config.keyboard);
  const isTypingTarget = (target) => {
    return target instanceof HTMLElement && (
      target.isContentEditable ||
      target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName === "SELECT"
    );
  };

  track.innerHTML = "";
  dotsWrap.innerHTML = "";

  slides.forEach((item, index) => {
    const slide = document.createElement("article");
    slide.className = "hero-slide";
    slide.style.transitionDuration = `${transitionMs}ms`;

    const media = document.createElement("div");
    media.className = "hero-slide-link";
    media.setAttribute("role", "img");

    const img = document.createElement("img");
    img.src = item.image;
    img.alt = item.alt || "轮播图";
    if (index === 0) {
      img.loading = "eager";
      img.fetchPriority = "high";
    } else {
      img.loading = "lazy";
    }

    media.appendChild(img);
    slide.appendChild(media);
    track.appendChild(slide);

    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = "hero-dot";
    dot.setAttribute("aria-label", `跳转到第${index + 1}张`);
    dot.addEventListener("click", () => {
      go(index);
      restartAutoplay();
    });
    dotsWrap.appendChild(dot);
  });

  const slideNodes = Array.from(track.querySelectorAll(".hero-slide"));
  const dotNodes = Array.from(dotsWrap.querySelectorAll(".hero-dot"));

  let current = 0;
  let timer = null;

  function paint() {
    slideNodes.forEach((el, idx) => {
      el.classList.toggle("is-active", idx === current);
      el.setAttribute("aria-hidden", idx === current ? "false" : "true");
    });
    dotNodes.forEach((el, idx) => {
      el.classList.toggle("is-active", idx === current);
    });
  }

  function go(nextIndex) {
    if (!slides.length) return;
    if (shouldLoop) {
      const len = slides.length;
      current = (nextIndex + len) % len;
    } else {
      current = Math.max(0, Math.min(nextIndex, slides.length - 1));
    }
    paint();
  }

  function stopAutoplay() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  function startAutoplay() {
    if (slides.length <= 1) return;
    stopAutoplay();
    timer = setInterval(() => {
      go(current + 1);
    }, autoplayMs);
  }

  function restartAutoplay() {
    if (slides.length <= 1) return;
    startAutoplay();
  }

  prevBtn.addEventListener("click", () => {
    go(current - 1);
    restartAutoplay();
  });

  nextBtn.addEventListener("click", () => {
    go(current + 1);
    restartAutoplay();
  });

  if (pauseOnHover) {
    root.addEventListener("mouseenter", stopAutoplay);
    root.addEventListener("mouseleave", startAutoplay);
  }

  if (keyboard) {
    document.addEventListener("keydown", (event) => {
      if (event.defaultPrevented || isTypingTarget(event.target)) {
        return;
      }
      if (document.querySelector(".lightbox:not([hidden])")) {
        return;
      }
      if (event.key === "ArrowLeft") {
        go(current - 1);
        restartAutoplay();
      }
      if (event.key === "ArrowRight") {
        go(current + 1);
        restartAutoplay();
      }
    });
  }

  if (slides.length <= 1) {
    prevBtn.hidden = true;
    nextBtn.hidden = true;
    dotsWrap.hidden = true;
    stopAutoplay();
  } else {
    prevBtn.hidden = false;
    nextBtn.hidden = false;
    dotsWrap.hidden = false;
    startAutoplay();
  }

  paint();
}
