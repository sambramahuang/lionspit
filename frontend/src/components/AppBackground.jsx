import React from "react";
import HexagonBackground from "./HexagonBackground.jsx";

// Single shared background -- used identically on the sign-in screen and
// the rest of the app so neither reads as a different screen's background
// swapped in underneath the user.
export default function AppBackground() {
  return <HexagonBackground />;
}
