import React, { useEffect, useMemo, useRef, useState } from "react";

/**
 * Ported from a Framer "Code Component" -- stripped of the Framer-only
 * bits (addPropertyControls property panel, useIsStaticRenderer canvas
 * /export detection) since neither applies outside the Framer editor.
 * Everything else -- the seeded blob layout, the rAF-driven CSS-transform
 * animation, the grain texture -- is unchanged. Soft, blurred, animated
 * gradient "blob" backgrounds (aurora / mesh-gradient style): absolutely
 * positioned blurred divs that drift, pulse, rotate, wave, or orbit via
 * CSS transforms driven by requestAnimationFrame -- no animation library.
 */

// Deterministic seeded PRNG (mulberry32) so a given seed always
// reproduces the same starting composition.
function mulberry32(seed) {
  let a = seed;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Builds a tileable film-grain noise texture as an SVG data URI using
// feTurbulence. Generated once per size/seed and reused -- cheap to
// render, no canvas or per-frame pixel work required.
function buildGrainDataUri(tileSize, grainSeed) {
  const freq = 0.9; // fixed fractal frequency; tileSize controls apparent grain scale
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='${tileSize}' height='${tileSize}'>
        <filter id='n'>
            <feTurbulence type='fractalNoise' baseFrequency='${freq}' numOctaves='2' seed='${grainSeed}' stitchTiles='stitch' result='noise'/>
            <feColorMatrix in='noise' type='matrix' values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 1 0'/>
        </filter>
        <rect width='100%' height='100%' filter='url(#n)'/>
    </svg>`;
  return `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}")`;
}

function ease(t, type) {
  if (type === "linear") return t;
  if (type === "sine") return (Math.sin((t - 0.25) * Math.PI * 2) + 1) / 2;
  // ease-in-out (smoothstep-ish, looping)
  const p = (Math.sin((t - 0.25) * Math.PI * 2) + 1) / 2;
  return p * p * (3 - 2 * p);
}

const SHAPE_BORDER_RADIUS = {
  Blob: "50% 45% 55% 50% / 50% 55% 45% 50%",
  "Radial Glow": "50%",
  Wave: "60% 40% 30% 70% / 60% 30% 70% 40%",
  Mesh: "40%",
  "Diagonal Streak": "10% 90% 10% 90% / 90% 10% 90% 10%",
};

const GRAIN_FRAME_COUNT = 6;

export default function GradientMotionBackground({
  // Colors
  colorStops = ["#22c55e", "#16a34a", "#4ade80"],
  baseBackground = "#050805",
  blendMode = "screen",
  opacity = 100,
  contrast = 110,
  // Shape
  shapeStyle = "Blob",
  blobCount = 3,
  blurAmount = 120,
  sizeMin = 60,
  sizeMax = 90,
  sizeRandomness = true,
  // Motion
  animate = true,
  speed = 40,
  motionStyle = "Drift",
  motionRange = 60,
  direction = 45,
  randomDirection = true,
  easeType = "ease-in-out",
  seed = 7,
  // Randomness
  positionJitter = 15,
  sizeVariation = 25,
  randomColorPerShape = false,
  // Grain
  grainEnabled = false,
  grainAmount = 15,
  grainSize = 120,
  grainBlendMode = "overlay",
  grainAnimate = false,
}) {
  const containerRef = useRef(null);
  const [tick, setTick] = useState(0);
  const startTimeRef = useRef(null);
  const rafRef = useRef(null);

  // Build the blob composition deterministically from seed. Regenerates
  // only when seed / count / colors / size / jitter change.
  const blobs = useMemo(() => {
    const rand = mulberry32(Math.floor(seed * 1e5) + 1);
    const colors = colorStops && colorStops.length > 0 ? colorStops : ["#22c55e"];
    const count = Math.max(1, Math.min(10, blobCount));
    const list = [];
    for (let i = 0; i < count; i++) {
      const baseX = ((i + 0.5) / count) * 100;
      const baseY = 30 + rand() * 40;
      const jitterX = (rand() - 0.5) * 2 * positionJitter;
      const jitterY = (rand() - 0.5) * 2 * positionJitter;
      const sizeBase = sizeMin + rand() * (sizeMax - sizeMin);
      const sizeJitter = sizeRandomness
        ? sizeBase * (1 + (rand() - 0.5) * 2 * (sizeVariation / 100))
        : sizeBase;
      const color = randomColorPerShape ? colors[Math.floor(rand() * colors.length)] : colors[i % colors.length];
      const dirAngle = randomDirection ? rand() * Math.PI * 2 : (direction / 180) * Math.PI;
      list.push({
        id: i,
        xPct: Math.min(100, Math.max(0, baseX + jitterX)),
        yPct: Math.min(100, Math.max(0, baseY + jitterY)),
        sizePct: Math.max(10, sizeJitter),
        color,
        rotation: rand() * 360,
        phase: rand(),
        dirX: Math.cos(dirAngle),
        dirY: Math.sin(dirAngle),
      });
    }
    return list;
  }, [
    seed,
    blobCount,
    JSON.stringify(colorStops),
    sizeMin,
    sizeMax,
    sizeRandomness,
    sizeVariation,
    positionJitter,
    randomDirection,
    direction,
    randomColorPerShape,
  ]);

  // Grain texture -- regenerated only when size/seed change. For animated
  // grain we cycle through a handful of pre-seeded tiles rather than
  // rebuilding SVG every frame (keeps it cheap).
  const grainTextures = useMemo(() => {
    if (!grainEnabled) return [];
    const count = grainAnimate ? GRAIN_FRAME_COUNT : 1;
    const arr = [];
    for (let i = 0; i < count; i++) {
      arr.push(buildGrainDataUri(grainSize, seed * 13 + i * 97 + 1));
    }
    return arr;
  }, [grainEnabled, grainSize, grainAnimate, seed]);
  const grainFrameIndex = grainAnimate && grainTextures.length > 1 ? Math.floor(tick * 12) % grainTextures.length : 0;

  // Animation loop (rAF). Uses CSS transforms only -- never touches
  // layout properties -- to stay performant.
  useEffect(() => {
    if (!animate) {
      setTick(0);
      return;
    }
    let mounted = true;
    const loop = (t) => {
      if (!mounted) return;
      if (startTimeRef.current === null) startTimeRef.current = t;
      const elapsed = (t - startTimeRef.current) / 1000;
      setTick(elapsed * (speed / 100));
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => {
      mounted = false;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      startTimeRef.current = null;
    };
  }, [animate, speed]);

  // Per-blob transform for the current motion style/time.
  function getTransform(b) {
    if (!animate) return "translate(-50%, -50%)";
    const loopT = ((tick + b.phase * 6) % 6) / 6; // 6s base loop, phase-offset
    const e = ease(loopT, easeType);
    const swing = Math.sin(e * Math.PI * 2);
    const range = motionRange;
    let tx = 0;
    let ty = 0;
    let rot = 0;
    let scale = 1;
    switch (motionStyle) {
      case "Drift":
        tx = b.dirX * range * swing;
        ty = b.dirY * range * swing;
        break;
      case "Pulse":
        scale = 1 + (range / 100) * (0.5 + 0.5 * swing) * 0.5;
        break;
      case "Rotate":
        rot = e * 360;
        break;
      case "Wave Flow":
        tx = Math.sin(e * Math.PI * 2 + b.id) * range;
        ty = Math.cos(e * Math.PI * 4 + b.id) * (range / 2);
        break;
      case "Orbit":
        tx = Math.cos(e * Math.PI * 2) * range;
        ty = Math.sin(e * Math.PI * 2) * range;
        break;
    }
    return `translate(-50%, -50%) translate(${tx}px, ${ty}px) rotate(${rot}deg) scale(${scale})`;
  }

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        overflow: "hidden",
        background: baseBackground,
        filter: `contrast(${contrast}%)`,
      }}
    >
      <div style={{ position: "absolute", inset: 0, opacity: opacity / 100 }}>
        {blobs.map((b) => {
          const isStreak = shapeStyle === "Diagonal Streak";
          return (
            <div
              key={b.id}
              style={{
                position: "absolute",
                left: `${b.xPct}%`,
                top: `${b.yPct}%`,
                width: isStreak ? `${b.sizePct * 2.2}%` : `${b.sizePct}%`,
                height: isStreak ? `${b.sizePct * 0.6}%` : `${b.sizePct}%`,
                background:
                  shapeStyle === "Radial Glow"
                    ? `radial-gradient(circle, ${b.color} 0%, transparent 70%)`
                    : b.color,
                borderRadius: SHAPE_BORDER_RADIUS[shapeStyle] || "50%",
                filter: `blur(${blurAmount}px)`,
                mixBlendMode: blendMode,
                transform: `${getTransform(b)} rotate(${b.rotation}deg)`,
                transition: animate ? "none" : "transform 0.3s ease",
                willChange: "transform",
              }}
            />
          );
        })}
      </div>
      {grainEnabled && grainTextures.length > 0 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage: grainTextures[grainFrameIndex],
            backgroundRepeat: "repeat",
            backgroundSize: `${grainSize}px ${grainSize}px`,
            opacity: grainAmount / 100,
            mixBlendMode: grainBlendMode,
            pointerEvents: "none",
          }}
        />
      )}
    </div>
  );
}
