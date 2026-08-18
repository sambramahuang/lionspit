import React from "react";
import { motion } from "motion/react";

const EASE = [0.76, 0, 0.24, 1];
const DURATION = 0.32;

// Two-phase wipe: a solid panel grows from the left edge to fully cover
// the screen ("covering"), the caller swaps the actual page content while
// it's hidden underneath, then the panel shrinks away toward the right
// edge ("revealing") -- same leading edge moving left-to-right the whole
// time, reading as one continuous sweep rather than two separate moves.
export default function PageWipe({ phase, onCoverComplete, onRevealComplete }) {
  if (phase === "covering") {
    return (
      <motion.div
        className="page-wipe"
        style={{ transformOrigin: "left" }}
        initial={{ scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ duration: DURATION, ease: EASE }}
        onAnimationComplete={onCoverComplete}
      />
    );
  }
  return (
    <motion.div
      className="page-wipe"
      style={{ transformOrigin: "right" }}
      initial={{ scaleX: 1 }}
      animate={{ scaleX: 0 }}
      transition={{ duration: DURATION, ease: EASE }}
      onAnimationComplete={onRevealComplete}
    />
  );
}
