/**
 * Toasts — the ONE notification mechanism (08 §7.1 Toast, §10 band 4, §12 standard messages).
 * Radix Toast (no runtime <style> injection — sonner injects an un-nonced <style>, blocked by the
 * strict CSP, 24 §4.4). Imperative API usable from effects/connections:
 *
 *   toast({ tone: "success", title: t("common:messages.saved") });
 *   toast.error(translateMessageKey(error.messageKey, error.params));
 *
 * Mount <Toaster /> once in the app shell. success/info = polite; destructive/warning = assertive.
 * Hotkey Alt+T focuses the region (F8 is a POS shortcut, 08 §9).
 */
import * as ToastPrimitive from "@radix-ui/react-toast";
import { CircleCheck, CircleX, Info, TriangleAlert, X } from "lucide-react";
import { useSyncExternalStore } from "react";

import { useTranslation } from "@shared/i18n";

import { Icon, type LucideIcon } from "#/icon/Icon.tsx";
import { cn } from "#/lib/cn.ts";
import { SOFT_TONE } from "#/composites/tone.ts";

export type ToastTone = "success" | "info" | "warning" | "destructive";

export interface ToastOptions {
  title: string;
  description?: string;
  tone?: ToastTone;
  /** ms; default 5000 (errors 8000). */
  duration?: number;
}

interface ToastItem extends Required<Pick<ToastOptions, "title" | "tone" | "duration">> {
  id: number;
  description?: string;
  open: boolean;
}

const MAX_VISIBLE = 3;
let items: ToastItem[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit(): void {
  for (const l of listeners) l();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): ToastItem[] {
  return items;
}

function dismiss(id: number): void {
  items = items.map((t) => (t.id === id ? { ...t, open: false } : t));
  emit();
  // Remove after the close animation.
  setTimeout(() => {
    items = items.filter((t) => t.id !== id);
    emit();
  }, 200);
}

function show(options: ToastOptions): number {
  const tone = options.tone ?? "info";
  const id = nextId;
  nextId += 1;
  const item: ToastItem = {
    id,
    title: options.title,
    description: options.description,
    tone,
    duration: options.duration ?? (tone === "destructive" ? 8000 : 5000),
    open: true,
  };
  items = [...items, item].slice(-MAX_VISIBLE);
  emit();
  return id;
}

type ToastFn = ((options: ToastOptions) => number) & {
  success: (title: string, description?: string) => number;
  error: (title: string, description?: string) => number;
  warning: (title: string, description?: string) => number;
  info: (title: string, description?: string) => number;
  dismiss: (id: number) => void;
  /** Test helper: drop every toast. */
  clear: () => void;
};

export const toast: ToastFn = Object.assign((options: ToastOptions) => show(options), {
  success: (title: string, description?: string) => show({ title, description, tone: "success" }),
  error: (title: string, description?: string) => show({ title, description, tone: "destructive" }),
  warning: (title: string, description?: string) => show({ title, description, tone: "warning" }),
  info: (title: string, description?: string) => show({ title, description, tone: "info" }),
  dismiss,
  clear: () => {
    items = [];
    emit();
  },
});

const TONE_ICON: Record<ToastTone, LucideIcon> = {
  success: CircleCheck,
  info: Info,
  warning: TriangleAlert,
  destructive: CircleX,
};

export function Toaster() {
  const { t } = useTranslation("common");
  const list = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  return (
    <ToastPrimitive.Provider swipeDirection="right" label={t("ui.toast.region")}>
      {list.map((item) => (
        <ToastPrimitive.Root
          key={item.id}
          open={item.open}
          duration={item.duration}
          type={item.tone === "destructive" || item.tone === "warning" ? "foreground" : "background"}
          onOpenChange={(open) => {
            if (!open) dismiss(item.id);
          }}
          className={cn(
            "pointer-events-auto flex w-full items-start gap-2.5 rounded-lg border border-border px-4 py-3 shadow-popover",
            "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:slide-in-from-right",
            "data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)] data-[swipe=end]:animate-out",
            SOFT_TONE[item.tone],
          )}
        >
          <Icon as={TONE_ICON[item.tone]} size="md" className="mt-px shrink-0" />
          <div className="min-w-0 flex-1">
            <ToastPrimitive.Title className="text-[14px] font-bold">{item.title}</ToastPrimitive.Title>
            {item.description ? (
              <ToastPrimitive.Description className="mt-0.5 text-small">
                {item.description}
              </ToastPrimitive.Description>
            ) : null}
          </div>
          <ToastPrimitive.Close
            aria-label={t("ui.toast.close")}
            className="-m-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-md hover:bg-card/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Icon as={X} size="sm" />
          </ToastPrimitive.Close>
        </ToastPrimitive.Root>
      ))}
      <ToastPrimitive.Viewport
        hotkey={["altKey", "KeyT"]}
        className="fixed bottom-0 right-0 z-toast flex max-h-screen w-full flex-col gap-2 p-4 outline-none sm:max-w-[420px]"
      />
    </ToastPrimitive.Provider>
  );
}
