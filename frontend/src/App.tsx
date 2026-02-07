import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Suspense, lazy } from "react";
import { AppLayoutShell } from "./components/layout/app-layout-shell";
import { ErrorBoundary } from "./components/ui/error-boundary";
import { ForeignFlowSkeleton } from "./components/ui/foreign-flow-skeleton";
import { VolumeAnalysisSkeleton } from "./components/ui/volume-analysis-skeleton";
import { SignalsSkeleton } from "./components/ui/signals-skeleton";

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
              <ErrorBoundary>
                <Suspense fallback={<ForeignFlowSkeleton />}>
                  <ForeignFlowPage />
                </Suspense>
              </ErrorBoundary>
            }
          />
          <Route
            path="/volume"
            element={
              <ErrorBoundary>
                <Suspense fallback={<VolumeAnalysisSkeleton />}>
                  <VolumeAnalysisPage />
                </Suspense>
              </ErrorBoundary>
            }
          />
          <Route
            path="/signals"
            element={
              <ErrorBoundary>
                <Suspense fallback={<SignalsSkeleton />}>
                  <SignalsPage />
                </Suspense>
              </ErrorBoundary>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
