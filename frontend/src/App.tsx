import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Suspense, lazy } from "react";
import { AppLayoutShell } from "./components/layout/app-layout-shell";
import { PageLoadingSkeleton } from "./components/ui/page-loading-skeleton";

const ForeignFlowPage = lazy(() => import("./pages/foreign-flow-page"));
const VolumeAnalysisPage = lazy(() => import("./pages/volume-analysis-page"));
const SignalsPage = lazy(() => import("./pages/signals-page"));

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayoutShell />}>
          <Route index element={<Navigate to="/foreign-flow" replace />} />
          <Route
            path="/foreign-flow"
            element={
              <Suspense fallback={<PageLoadingSkeleton />}>
                <ForeignFlowPage />
              </Suspense>
            }
          />
          <Route
            path="/volume"
            element={
              <Suspense fallback={<PageLoadingSkeleton />}>
                <VolumeAnalysisPage />
              </Suspense>
            }
          />
          <Route
            path="/signals"
            element={
              <Suspense fallback={<PageLoadingSkeleton />}>
                <SignalsPage />
              </Suspense>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
