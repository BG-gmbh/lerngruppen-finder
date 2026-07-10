(function () {
  // Leichtgewichtiges Konfetti ohne externe Abhaengigkeiten (Canvas).
  function launchConfetti(options) {
    var opts = options || {};
    var durationMs = opts.duration || 2500;
    var count = opts.count || 160;
    var colors = opts.colors || [
      "#ef476f", "#ffd166", "#06d6a0", "#118ab2", "#8338ec", "#ff9f1c",
    ];

    var canvas = document.createElement("canvas");
    canvas.style.position = "fixed";
    canvas.style.inset = "0";
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    canvas.style.pointerEvents = "none";
    canvas.style.zIndex = "9999";
    document.body.appendChild(canvas);

    var ctx = canvas.getContext("2d");
    var dpr = window.devicePixelRatio || 1;
    function resize() {
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener("resize", resize);

    var W = window.innerWidth;
    var pieces = [];
    for (var i = 0; i < count; i++) {
      pieces.push({
        x: Math.random() * W,
        y: -20 - Math.random() * canvas.height,
        r: 5 + Math.random() * 7,
        color: colors[(Math.random() * colors.length) | 0],
        vx: -2 + Math.random() * 4,
        vy: 2 + Math.random() * 4,
        rot: Math.random() * Math.PI,
        vrot: -0.2 + Math.random() * 0.4,
      });
    }

    var start = null;
    function frame(ts) {
      if (start === null) start = ts;
      var elapsed = ts - start;
      var H = window.innerHeight;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (var i = 0; i < pieces.length; i++) {
        var p = pieces[i];
        p.x += p.vx;
        p.y += p.vy;
        p.rot += p.vrot;
        if (p.y > H + 20) {
          p.y = -20;
          p.x = Math.random() * window.innerWidth;
        }
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.r / 2, -p.r / 2, p.r, p.r * 0.6);
        ctx.restore();
      }
      if (elapsed < durationMs) {
        window.requestAnimationFrame(frame);
      } else {
        window.removeEventListener("resize", resize);
        if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
      }
    }
    window.requestAnimationFrame(frame);
  }

  window.launchConfetti = launchConfetti;
})();
