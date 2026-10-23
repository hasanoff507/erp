import { useEffect } from "react";

/**
 * Sets <html data-density> (08 §5) and, for the POS kiosk, locks data-theme="light" (08 §1).
 * Back-office passes `theme: null` and follows the OS / user preference.
 */
export function useDocumentAttributes({
  density,
  theme,
}: {
  density: "touch" | "compact";
  theme: "light" | null;
}) {
  useEffect(() => {
    const root = document.documentElement;
    const previousTheme = root.getAttribute("data-theme");
    root.setAttribute("data-density", density);
    if (theme) root.setAttribute("data-theme", theme);
    return () => {
      root.removeAttribute("data-density");
      if (theme) {
        if (previousTheme) root.setAttribute("data-theme", previousTheme);
        else root.removeAttribute("data-theme");
      }
    };
  }, [density, theme]);
}
