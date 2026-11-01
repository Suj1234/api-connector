/** Tailwind reads only the DESIGN.md tokens (CSS variables in src/index.css). No raw hex in components. */
const v = (name) => `var(--${name})`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    colors: {
      transparent: "transparent",
      white: "#FFFFFF",
      primary: { DEFAULT: v("primary"), hover: v("primary-hover"), pressed: v("primary-pressed"), subtle: v("primary-subtle"), tint: v("primary-tint"), disabled: v("primary-disabled") },
      link: v("link"),
      navy: v("navy"),
      overlay: v("overlay"),
      focus: v("focus-ring"),
      surface: { DEFAULT: v("surface"), subdued: v("surface-subdued") },
      border: { DEFAULT: v("border"), strong: v("border-strong"), hover: v("border-hover") },
      text: { heading: v("text-heading"), DEFAULT: v("text"), subdued: v("text-subdued"), muted: v("text-muted"), placeholder: v("text-placeholder") },
      success: { DEFAULT: v("success"), bg: v("success-bg"), fg: v("success-fg"), border: v("success-border") },
      danger: { subtle: v("danger-subtle"), bg: v("danger-bg"), fg: v("danger-fg"), DEFAULT: v("danger"), border: v("danger-border") },
      warning: { bg: v("warning-bg"), fg: v("warning-fg"), border: v("warning-border") },
      info: { bg: v("info-bg"), fg: v("info-fg"), border: v("info-border") },
      neutral: { bg: v("neutral-bg"), fg: v("neutral-fg") },
      chart: { left: v("chart-left"), inactive: v("chart-inactive"), never: v("chart-never"), nothr: v("chart-not-in-hr"), active: v("chart-active"), excluded: v("chart-excluded") },
    },
    fontFamily: { sans: v("font-sans"), mono: v("font-mono") },
    borderRadius: { none: "0", badge: "4px", sm: v("radius-sm"), md: v("radius-md"), full: "9999px" },
    boxShadow: { float: v("shadow-float"), modal: v("shadow-modal"), focus: v("shadow-focus"), control: v("shadow-control"), primary: v("shadow-primary"), popover: v("shadow-popover"), none: "none" },
    extend: {},
  },
  plugins: [],
};
