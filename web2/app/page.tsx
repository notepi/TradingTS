"use client";

import { useState, useEffect, useCallback } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { StatsOverview } from "@/components/dashboard/stats-overview";
import { WorkflowOverview } from "@/components/dashboard/workflow-overview";
import { CurrentOutput } from "@/components/dashboard/current-output";
import { ResultSummary } from "@/components/dashboard/result-summary";
import { ProcessTree } from "@/components/dashboard/process-tree";
import * as api from "@/lib/api";
import type { DashboardOptions, Snapshot, Selections } from "@/lib/types";

export default function Dashboard() {
  const [options, setOptions] = useState<DashboardOptions | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [selections, setSelections] = useState<Selections | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isRunning = snapshot?.status === "running";
  const isStopping = snapshot?.status === "stopping";

  useEffect(() => {
    api.getOptions().then(setOptions).catch(console.error);
  }, []);

  useEffect(() => {
    if (!options) return;

    api.getState().then((state) => {
      setSnapshot(state);
      setSelections(state.selections ?? null);
      if (state.error) {
        setError(state.error);
      } else {
        setError(null);
      }
    }).catch(console.error);
  }, [options]);

  useEffect(() => {
    if (!isRunning && !isStopping) return;

    const interval = setInterval(async () => {
      try {
        const state = await api.getState();
        setSnapshot(state);
        setSelections(state.selections ?? null);
        if (state.error) {
          setError(state.error);
        } else {
          setError(null);
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [isRunning, isStopping]);

  const handleStart = useCallback(async (payload: unknown) => {
    setError(null);
    try {
      const state = await api.startAnalysis(payload as Parameters<typeof api.startAnalysis>[0]);
      setSnapshot(state);
      setSelections(state.selections ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start analysis");
    }
  }, []);

  const handleStop = useCallback(async () => {
    try {
      const state = await api.stopAnalysis();
      setSnapshot(state);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to stop analysis");
    }
  }, []);

  const handleReset = useCallback(async () => {
    setError(null);
    try {
      const state = await api.resetDashboard();
      setSnapshot(state);
      setSelections(state.selections ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset");
    }
  }, []);

  return (
    <div className="flex flex-col h-full">
      <TopBar snapshot={snapshot} />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          options={options}
          selections={selections}
          onStart={handleStart}
          onStop={handleStop}
          onReset={handleReset}
          isRunning={isRunning}
          isStopping={isStopping}
        />

        <main className="flex-1 overflow-y-auto p-4 space-y-4">
          {error && (
            <div className="bg-destructive/10 border border-destructive/30 text-destructive text-xs p-3 rounded">
              {error}
            </div>
          )}

          <StatsOverview snapshot={snapshot} />

          <WorkflowOverview snapshot={snapshot} />

          <div className="grid grid-cols-2 gap-4">
            <CurrentOutput snapshot={snapshot} />
            <ResultSummary snapshot={snapshot} />
          </div>

          <ProcessTree snapshot={snapshot} />
        </main>
      </div>
    </div>
  );
}
