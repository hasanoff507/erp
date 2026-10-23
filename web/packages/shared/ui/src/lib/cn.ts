import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * Tailwind class merge aware of the project's custom font-size tokens (preset §4.3), so that
 * `text-h1` and `text-foreground` are not treated as conflicting classes.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [
        {
          text: [
            "display",
            "h1",
            "h2",
            "kpi",
            "money",
            "body",
            "body-pos",
            "label",
            "small",
            "caption",
            "overline",
            "kbd",
          ],
        },
      ],
    },
  },
});

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
