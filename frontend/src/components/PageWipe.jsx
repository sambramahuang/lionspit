import React from "react";
import { motion } from "motion/react";

const EASE = [0.76, 0, 0.24, 1];
const DURATION = 0.32;

// Two-phase wipe: the panel covers and reveals in the direction of travel.
export default function PageWipe({
  phase,
  direction = "right",
  axis = "x",
  onCoverComplete,
  onRevealComplete,
}) {
  const movingForward = direction === (axis === "y" ? "down" : "right");
  const scaleAxis = axis === "y" ? "scaleY" : "scaleX";
  const coverOrigin = movingForward
    ? axis === "y" ? "top" : "left"
    : axis === "y" ? "bottom" : "right";
  const revealOrigin = movingForward
    ? axis === "y" ? "bottom" : "right"
    : axis === "y" ? "top" : "left";

  if (phase === "covering") {
    return (
      <motion.div
        className="page-wipe"
        style={{ transformOrigin: coverOrigin }}
        initial={{ [scaleAxis]: 0 }}
        animate={{ [scaleAxis]: 1 }}
        transition={{ duration: DURATION, ease: EASE }}
        onAnimationComplete={onCoverComplete}
      />
    );
  }
  return (
    <motion.div
      className="page-wipe"
        style={{ transformOrigin: revealOrigin }}
      initial={{ [scaleAxis]: 1 }}
      animate={{ [scaleAxis]: 0 }}
      transition={{ duration: DURATION, ease: EASE }}
      onAnimationComplete={onRevealComplete}
    />
  );
}
