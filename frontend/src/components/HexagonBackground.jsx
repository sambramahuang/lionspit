import React, { useEffect, useRef, useState } from "react";

// Interactive hexagon-grid background in the app's neutral and navy palette:
// a flat-top hex tiling drawn once per size change, each cell lighting up
// with a unified navy or neutral glow the closer the pointer sits to its center. No canvas --
// plain absolutely-positioned clip-path divs, since the grid is static
// geometry and only the per-cell glow needs to update on pointer move.
const HEX_SIZE = 46; // center-to-corner radius, px
const HEX_MARGIN = 4; // gap between cells, px
const GLOW_RADIUS = 220; // px, how far a cell "feels" the pointer
const HEX_OPACITY_SCALE = 0.7; // make the grid 30% more transparent
const HEX_DEFAULT_COLOR = "#b9bec3";
const HEX_BASE_OPACITY = 0.07;
const HEX_GLOW_OPACITY = 0.32;

function buildHexagons(width, height) {
  const w = HEX_SIZE * 2;
  const h = Math.sqrt(3) * HEX_SIZE;
  const stepX = (w * 0.75) + HEX_MARGIN;
  const stepY = h + HEX_MARGIN;

  const hexes = [];
  const cols = Math.ceil(width / stepX) + 2;
  const rows = Math.ceil(height / stepY) + 2;

  for (let col = -1; col < cols; col++) {
    for (let row = -1; row < rows; row++) {
      const x = col * stepX;
      const y = row * stepY + (col % 2 !== 0 ? stepY / 2 : 0);
      hexes.push({ id: `${col}-${row}`, x, y });
    }
  }
  return hexes;
}

export default function HexagonBackground({ hexagonSize = HEX_SIZE, hexagonMargin = HEX_MARGIN }) {
  const containerRef = useRef(null);
  const [hexes, setHexes] = useState([]);
  const [pointer, setPointer] = useState(null); // {x, y} in container-local px, or null

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const rebuild = () => {
      const rect = el.getBoundingClientRect();
      setHexes(buildHexagons(rect.width, rect.height));
    };
    rebuild();

    const ro = new ResizeObserver(rebuild);
    ro.observe(el);

    const trackPointer = (event) => {
      const rect = el.getBoundingClientRect();
      setPointer({ x: event.clientX - rect.left, y: event.clientY - rect.top });
    };
    const resetPointer = (event) => {
      if (!event.relatedTarget) setPointer(null);
    };
    window.addEventListener("pointermove", trackPointer, { passive: true });
    window.addEventListener("pointerout", resetPointer, { passive: true });

    return () => {
      ro.disconnect();
      window.removeEventListener("pointermove", trackPointer);
      window.removeEventListener("pointerout", resetPointer);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="hexagon-bg"
    >
      {hexes.map((hex) => {
        let glow = 0;
        if (pointer) {
          const dx = pointer.x - (hex.x + hexagonSize);
          const dy = pointer.y - (hex.y + hexagonSize);
          const dist = Math.sqrt(dx * dx + dy * dy);
          glow = Math.max(0, 1 - dist / GLOW_RADIUS);
        }
        return (
          <div
            key={hex.id}
            className="hexagon-cell"
            style={{
              left: hex.x,
              top: hex.y,
              width: hexagonSize * 2,
              height: Math.sqrt(3) * hexagonSize,
              margin: hexagonMargin,
              background: HEX_DEFAULT_COLOR,
              opacity: (HEX_BASE_OPACITY + glow * HEX_GLOW_OPACITY) * HEX_OPACITY_SCALE,
              transform: `scale(${1 + glow * 0.06})`,
            }}
          />
        );
      })}
    </div>
  );
}
