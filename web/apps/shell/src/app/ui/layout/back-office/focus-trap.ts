/** Modal focus trap for the <768px navigation drawer (BackOfficeLayout, 08 §7.4 dialog a11y). */
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Keeps Tab / Shift+Tab inside `container`: returns the element to focus instead of the browser's next
 * one (Tab on the last → first, Shift+Tab on the first → last, focus outside → back in), or `null` when
 * the default Tab move stays inside.
 */
export function trapTab(
  container: HTMLElement,
  event: Pick<KeyboardEvent, "key" | "shiftKey">,
): HTMLElement | null {
  if (event.key !== "Tab") return null;
  const items = Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => !el.hasAttribute("inert") && el.getAttribute("aria-hidden") !== "true",
  );
  const first = items[0];
  const last = items[items.length - 1];
  if (!first || !last) return null;
  const active = document.activeElement;
  const inside = active instanceof HTMLElement && container.contains(active);
  if (event.shiftKey && (!inside || active === first)) return last;
  if (!event.shiftKey && (!inside || active === last)) return first;
  return null;
}
