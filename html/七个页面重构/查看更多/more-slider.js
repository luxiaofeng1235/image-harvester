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

export function initMoreSlider(root, options) {
  if (!root || !options || !Array.isArray(options.slides) || options.slides.length === 0) {
    return null;
  }

  var slides = options.slides.slice();
  var interval = Number(options.interval) || 3000;
  var currentIndex = 0;
  var timer = null;
  var isAnimating = false;

  root.innerHTML = "";

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

  stage.appendChild(currentLayer);
  stage.appendChild(revealLayer);
  stage.appendChild(piecesLayer);
  stage.appendChild(prevButton);
  stage.appendChild(nextButton);
  root.appendChild(stage);

  function applyBackground(target, slide) {
    if (!target || !slide) return;
    target.style.backgroundImage = 'url("' + slide.imageUrl + '")';
    target.setAttribute("aria-label", slide.alt || "");
  }

  function renderStatic(index) {
    currentIndex = index;
    applyBackground(currentLayer, slides[currentIndex]);
    applyBackground(revealLayer, slides[currentIndex]);
  }

  function chooseEffect() {
    var effect = options.effect || "all";
    var pool = ["slice", "blocks", "blinds", "shuffle", "threed", "fade", "shrink"];
    if (effect === "all") {
      return pool[Math.floor(Math.random() * pool.length)];
    }
    return effect;
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
        3,
        1,
        function (index) {
          return index * 95;
        },
        function () {
          return "scaleX(0.08)";
        }
      );
      return {
        pieces: pieces,
        duration: 900
      };
    }

    if (effect === "blocks") {
      addGrid(
        5,
        5,
        function (index) {
          return index * 28;
        },
        function (index, column, row) {
          var x = (column - 2) * 10;
          var y = (row - 2) * 10;
          return "translate(" + x + "px, " + y + "px) scale(0.72)";
        }
      );
      return {
        pieces: pieces,
        duration: 1150
      };
    }

    if (effect === "shuffle") {
      var order = [];
      for (var i = 0; i < 25; i += 1) {
        order.push(i);
      }
      order.sort(function () {
        return Math.random() - 0.5;
      });
      addGrid(
        5,
        5,
        function (index) {
          return order[index] * 22;
        },
        function (index, column, row) {
          var rotate = (index % 2 === 0 ? 1 : -1) * (6 + ((column + row) % 3) * 2);
          return "translateY(" + (row % 2 === 0 ? -18 : 18) + "px) rotate(" + rotate + "deg) scale(0.84)";
        }
      );
      return {
        pieces: pieces,
        duration: 1150
      };
    }

    if (effect === "threed") {
      addGrid(
        5,
        1,
        function (index) {
          return index * 80;
        },
        function (index) {
          var angle = index % 2 === 0 ? -90 : 90;
          return "perspective(1200px) rotateY(" + angle + "deg)";
        }
      );
      return {
        pieces: pieces,
        duration: 1100
      };
    }

    addGrid(
      10,
      1,
      function (index) {
        return index * 42;
      },
      function (index) {
        return index % 2 === 0
          ? "translateY(-20px) scaleY(0.92)"
          : "translateY(24px) scaleY(0.92)";
      }
    );

    return {
      pieces: pieces,
      duration: 1050
    };
  }

  function animateTo(nextIndex) {
    if (isAnimating || nextIndex === currentIndex) {
      return;
    }

    isAnimating = true;
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
      isAnimating = false;
    }, effectState.duration);
  }

  function go(step) {
    var nextIndex = (currentIndex + step + slides.length) % slides.length;
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
