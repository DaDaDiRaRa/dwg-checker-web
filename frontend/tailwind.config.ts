import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        kw:      ["var(--font-primary)"],
        "kw-mono": ["var(--font-mono)"],
      },
      colors: {
        kw: {
          bg:          "var(--color-bg-page)",
          surface:     "var(--color-bg-surface)",
          "surface-alt": "var(--color-bg-surface-alt)",
          input:       "var(--color-bg-input)",
          "input-dis": "var(--color-bg-input-disabled)",
          border:      "var(--color-border)",
          "border-s":  "var(--color-border-strong)",
          text:        "var(--color-text-primary)",
          body:        "var(--color-text-body)",
          muted:       "var(--color-text-muted)",
          faint:       "var(--color-text-faint)",
          subtle:      "var(--color-text-subtle)",
          accent:      "var(--color-accent)",
          "accent-h":  "var(--color-accent-hover)",
          "accent-soft": "var(--color-accent-soft)",
          "accent-bd": "var(--color-accent-border)",
          ok:          "var(--color-success)",
          "ok-bg":     "var(--color-success-bg)",
          "ok-bd":     "var(--color-success-border)",
          warn:        "var(--color-warning)",
          "warn-bg":   "var(--color-warning-bg)",
          "warn-bd":   "var(--color-warning-border)",
          err:         "var(--color-danger)",
          "err-bg":    "var(--color-danger-bg)",
          "err-bd":    "var(--color-danger-border)",
          info:        "var(--color-info)",
          "info-bg":   "var(--color-info-bg)",
          "info-bd":   "var(--color-info-border)",
        },
      },
    },
  },
  plugins: [],
};

export default config;
