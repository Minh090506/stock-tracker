/** Root layout: sidebar + main content area with Outlet. */

import { Outlet } from "react-router-dom";
import { AppSidebarNavigation } from "./app-sidebar-navigation";

export function AppLayoutShell() {
  return (
    <div className="min-h-screen bg-gray-950 text-white flex">
      <AppSidebarNavigation />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
