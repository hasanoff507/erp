import { useUnit } from "effector-react";
import { useEffect } from "react";

import { dayjs } from "@shared/lib/date";

import { pageMounted, pageUnmounted } from "../../model/index.ts";
import { Header } from "../header/Header.tsx";
import { Main } from "../main/Main.tsx";

/**
 * BO-02 — Dashboard (07, route /app/dashboard). The branch is the topbar choice («Barcha filiallar» =
 * consolidated, US-M14-01). useEffect only fires the mount / unmount events (24 §2).
 */
function DashboardPage() {
  const [mounted, unmounted] = useUnit([pageMounted, pageUnmounted]);
  useEffect(() => {
    mounted({ today: dayjs().format("YYYY-MM-DD") });
    return () => unmounted();
  }, [mounted, unmounted]);

  return (
    <div className="flex flex-col gap-[18px]">
      <Header />
      <Main />
    </div>
  );
}

export const Dashboard = {
  route: "dashboard",
  titleKey: "reports:dashboard.title",
  Page: DashboardPage,
} as const;
