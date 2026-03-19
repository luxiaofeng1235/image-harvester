function createPiece(stageRect, pieceRect, imageUrl, delay, fromTransform) {
  var piece = document.createElement("span");
  piece.className = "zr-more-slider-piece";
  piece.style.left = pieceRect.left + "px";
  piece.style.top = pieceRect.top + "px";
  piece.style.width = pieceRect.width + "px";
  piece.style.height = pieceRect.height + "px";
  piece.style.backgroundImage = 'url("' + imageUrl + '")';
  piece.style.backgroundSize = stageRect.width + "px " + stageRect.height + "px";
  piece.style.backgroundPosition = -pieceRect.left + "px " + -pieceRect.top + "px";
  piece.style.transitionDelay = delay + "ms";
  piece.style.transform = fromTransform;
  piece.style.opacity = "0";
  return piece;
}

export function initSharedSlider(root, options) {
  if (!root || !options || !Array.isArray(options.slides) || options.slides.length === 0) {
    return null;
  }

  var slides = options.slides.slice();
  var interval = Number(options.interval) || 3000;
  var currentIndex = 0;
  var timer = null;
  var isAnimating = false;
  var transitionCount = 0;
  var lastEffect = "";

  root.innerHTML = "";
  root.classList.add("zr-shared-slider");

  var stage = document.createElement("div");
  stage.className = "zr-more-slider-stage";

  var currentLayer = document.createElement("div");
  currentLayer.className = "zr-more-slider-image is-current";

  var revealLayer = document.createElement("div");
  revealLayer.className = "zr-more-slider-image is-reveal";

  var piecesLayer = document.createElement("div");
  piecesLayer.className = "zr-more-slider-pieces";

  var prevButton = document.createElement("button");
  prevButton.className = "zr-more-slider-arrow zr-more-slider-arrow-prev";
  prevButton.type = "button";
  prevButton.setAttribute("aria-label", "上一张");
  prevButton.textContent = "‹";

  var nextButton = document.createElement("button");
  nextButton.className = "zr-more-slider-arrow zr-more-slider-arrow-next";
  nextButton.type = "button";
  nextButton.setAttribute("aria-label", "下一张");
  nextButton.textContent = "›";

  var dots = document.createElement("div");
  dots.className = "zr-more-slider-dots";
  dots.setAttribute("aria-label", "轮播分页");

  var dotButtons = slides.map(function (_, index) {
    var dot = document.createElement("button");
    dot.className = "zr-more-slider-dot";
    dot.type = "button";
    dot.setAttribute("aria-label", "跳转到第" + (index + 1) + "张");
    dot.addEventListener("click", function () {
      goTo(index);
      startAuto();
    });
    dots.appendChild(dot);
    return dot;
  });

  stage.appendChild(currentLayer);
  stage.appendChild(revealLayer);
  stage.appendChild(piecesLayer);
  stage.appendChild(prevButton);
  stage.appendChild(nextButton);
  stage.appendChild(dots);
  root.appendChild(stage);

  if (slides.length <= 1) {
    prevButton.hidden = true;
    nextButton.hidden = true;
    dots.hidden = true;
  }

  function applyBackground(target, slide) {
    if (!target || !slide) return;
    target.style.backgroundImage = 'url("' + slide.imageUrl + '")';
    target.setAttribute("aria-label", slide.alt || "");
  }

  function updateDots(index) {
    dotButtons.forEach(function (dot, dotIndex) {
      var isActive = dotIndex === index;
      dot.classList.toggle("is-active", isActive);
      if (isActive) {
        dot.setAttribute("aria-current", "true");
      } else {
        dot.removeAttribute("aria-current");
      }
    });
  }

  function renderStatic(index) {
    currentIndex = index;
    applyBackground(currentLayer, slides[currentIndex]);
    applyBackground(revealLayer, slides[currentIndex]);
    updateDots(currentIndex);
  }

  function chooseEffect() {
    var effect = options.effect || "all";
    if (effect === "all") {
      if (transitionCount === 0) {
        return "slice";
      }
      return pickRandomEffect([
        "fragments",
        "fragments",
        "shards",
        "shards",
        "blocks",
        "blocks",
        "blinds",
        "shuffle",
        "threed",
        "curtain",
        "slice"
      ]);
    }
    return effect;
  }

  function pickRandomEffect(pool) {
    if (!Array.isArray(pool) || pool.length === 0) {
      return "slice";
    }

    var next = pool[Math.floor(Math.random() * pool.length)];
    var attempts = 0;

    while (pool.length > 1 && next === lastEffect && attempts < 6) {
      next = pool[Math.floor(Math.random() * pool.length)];
      attempts += 1;
    }

    return next;
  }

  function buildEffectPieces(effect, imageUrl) {
    var stageRect = {
      width: stage.clientWidth,
      height: stage.clientHeight
    };
    var pieces = [];

    function addGrid(columns, rows, delayFactory, transformFactory) {
      var width = stageRect.width / columns;
      var height = stageRect.height / rows;

      for (var row = 0; row < rows; row += 1) {
        for (var column = 0; column < columns; column += 1) {
          var index = row * columns + column;
          pieces.push(
            createPiece(
              stageRect,
              {
                left: width * column,
                top: height * row,
                width: width + 1,
                height: height + 1
              },
              imageUrl,
              delayFactory(index, column, row),
              transformFactory(index, column, row)
            )
          );
        }
      }
    }

    if (effect === "fade") {
      addGrid(
        1,
        1,
        function () {
          return 0;
        },
        function () {
          return "scale(1.03)";
        }
      );
      return {
        pieces: pieces,
        duration: 800
      };
    }

    if (effect === "shrink") {
      addGrid(
        1,
        1,
        function () {
          return 0;
        },
        function () {
          return "scale(1.12)";
        }
      );
      return {
        pieces: pieces,
        duration: 1200
      };
    }

    if (effect === "blinds") {
      addGrid(
        5,
        1,
        function (index) {
          return index * 72;
        },
        function (index) {
          return index % 2 === 0
            ? "translateY(-16px) scaleX(0.08)"
            : "translateY(16px) scaleX(0.08)";
        }
      );
      return {
        pieces: pieces,
        duration: 980
      };
    }

    if (effect === "blocks") {
      addGrid(
        6,
        5,
        function (index) {
          return index * 20;
        },
        function (index, column, row) {
          var x = (column - 2.5) * 14;
          var y = (row - 2) * 14;
          var rotate = (index % 2 === 0 ? 1 : -1) * (5 + ((column + row) % 3) * 2);
          return "translate(" + x + "px, " + y + "px) rotate(" + rotate + "deg) scale(0.64)";
        }
      );
      return {
        pieces: pieces,
        duration: 1220
      };
    }

    if (effect === "shuffle") {
      var order = [];
      for (var i = 0; i < 30; i += 1) {
        order.push(i);
      }
      order.sort(function () {
        return Math.random() - 0.5;
      });
      addGrid(
        6,
        5,
        function (index) {
          return order[index] * 16;
        },
        function (index, column, row) {
          var rotate = (index % 2 === 0 ? 1 : -1) * (10 + ((column + row) % 4) * 2);
          var x = column % 2 === 0 ? -14 - row * 2 : 14 + row * 2;
          var y = row % 2 === 0 ? -24 : 24;
          return "translate(" + x + "px, " + y + "px) rotate(" + rotate + "deg) scale(0.78)";
        }
      );
      return {
        pieces: pieces,
        duration: 1240
      };
    }

    if (effect === "threed") {
      addGrid(
        7,
        1,
        function (index) {
          return index * 54;
        },
        function (index) {
          var angle = index % 2 === 0 ? -90 : 90;
          return "perspective(1200px) rotateY(" + angle + "deg)";
        }
      );
      return {
        pieces: pieces,
        duration: 1160
      };
    }

    if (effect === "fragments") {
      var fragmentOrder = [];
      for (var fragmentIndex = 0; fragmentIndex < 48; fragmentIndex += 1) {
        fragmentOrder.push(fragmentIndex);
      }
      fragmentOrder.sort(function () {
        return Math.random() - 0.5;
      });
      addGrid(
        8,
        6,
        function (index, column, row) {
          return fragmentOrder[index] * 14 + ((column + row) % 2) * 12;
        },
        function (index, column, row) {
          var x = (column - 3.5) * 16;
          var y = (row - 2.5) * 16;
          var rotate = (index % 2 === 0 ? 1 : -1) * (8 + ((column + row) % 4) * 3);
          return "translate(" + x + "px, " + y + "px) rotate(" + rotate + "deg) scale(0.54)";
        }
      );
      return {
        pieces: pieces,
        duration: 1360
      };
    }

    if (effect === "shards") {
      addGrid(
        6,
        4,
        function (index, column, row) {
          return column * 46 + row * 30;
        },
        function (index, column, row) {
          var x = row % 2 === 0 ? -28 - column * 2 : 28 + column * 2;
          var y = (row - 1.5) * 20;
          var rotate = row % 2 === 0 ? -12 - column * 2 : 12 + column * 2;
          var skew = row % 2 === 0 ? -10 : 10;
          return "translate(" + x + "px, " + y + "px) rotate(" + rotate + "deg) skewX(" + skew + "deg) scale(0.8)";
        }
      );
      return {
        pieces: pieces,
        duration: 1280
      };
    }

    if (effect === "curtain") {
      addGrid(
        12,
        1,
        function (index) {
          return index * 34;
        },
        function (index) {
          return index % 2 === 0
            ? "translateY(-34px) scaleY(0.1)"
            : "translateY(34px) scaleY(0.1)";
        }
      );
      return {
        pieces: pieces,
        duration: 1040
      };
    }

    addGrid(
      14,
      1,
      function (index) {
        return index * 28;
      },
      function (index) {
        return index % 2 === 0
          ? "translateY(-26px) scaleY(0.84)"
          : "translateY(30px) scaleY(0.84)";
      }
    );

    return {
      pieces: pieces,
      duration: 1120
    };
  }

  function animateTo(nextIndex) {
    if (isAnimating || nextIndex === currentIndex) {
      return;
    }

    isAnimating = true;
    updateDots(nextIndex);
    var targetSlide = slides[nextIndex];
    var effect = chooseEffect();
    var effectState = buildEffectPieces(effect, targetSlide.imageUrl);
    applyBackground(revealLayer, targetSlide);
    piecesLayer.innerHTML = "";
    effectState.pieces.forEach(function (piece) {
      piecesLayer.appendChild(piece);
    });

    root.classList.remove(
      "is-effect-slice",
      "is-effect-blocks",
      "is-effect-blinds",
      "is-effect-shuffle",
      "is-effect-threed",
      "is-effect-fragments",
      "is-effect-shards",
      "is-effect-curtain",
      "is-effect-fade",
      "is-effect-shrink"
    );
    root.classList.add("is-effect-running", "is-effect-" + effect);
    void root.offsetWidth;

    Array.prototype.forEach.call(piecesLayer.children, function (piece) {
      piece.style.transform = "translate3d(0,0,0) scale(1) rotate(0deg)";
      piece.style.opacity = "1";
      piece.style.filter = "blur(0)";
    });

    window.setTimeout(function () {
      applyBackground(currentLayer, targetSlide);
      root.classList.remove("is-effect-running", "is-effect-" + effect);
      piecesLayer.innerHTML = "";
      currentIndex = nextIndex;
      lastEffect = effect;
      transitionCount += 1;
      isAnimating = false;
    }, effectState.duration);
  }

  function go(step) {
    var nextIndex = (currentIndex + step + slides.length) % slides.length;
    animateTo(nextIndex);
  }

  function goTo(index) {
    var nextIndex = ((index % slides.length) + slides.length) % slides.length;
    animateTo(nextIndex);
  }

  function startAuto() {
    stopAuto();
    if (slides.length <= 1) {
      return;
    }
    timer = window.setInterval(function () {
      go(1);
    }, interval);
  }

  function stopAuto() {
    if (timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  prevButton.addEventListener("click", function () {
    go(-1);
    startAuto();
  });

  nextButton.addEventListener("click", function () {
    go(1);
    startAuto();
  });

  root.addEventListener("mouseenter", stopAuto);
  root.addEventListener("mouseleave", startAuto);

  renderStatic(0);
  startAuto();

  return {
    destroy: function () {
      stopAuto();
    }
  };
}
