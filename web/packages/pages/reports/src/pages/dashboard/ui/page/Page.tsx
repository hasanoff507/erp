import { useUnit } from "effector-react";
import { useEffect } from "react";

import { pageMounted } from "../../model/index.ts";
import { Header } from "../header/Header.tsx";
import { Main } from "../main/Main.tsx";

/** BO-02 — Dashboard (07, route /app/dashboard). useEffect only fires pageMounted (24 §2). */
function DashboardPage() {
  const mounted = useUnit(pageMounted);
  useEffect(() => {
    mounted();
  }, [mounted]);

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
