"use client";

import { Badge } from "@/components/ui/badge";
import type { Snapshot } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TopBarProps {
  snapshot: Snapshot | null;
}

const STATUS_LABELS: Record<string, string> = {
  idle: "IDLE",
  running: "RUNNING",
  stopping: "STOPPING",
  completed: "COMPLETED",
  stopped: "STOPPED",
  error: "ERROR",
};

const STATUS_COLORS: Record<string, string> = {
  idle: "bg-muted text-muted-foreground",
  running: "bg-blue-600/20 text-blue-400 border-blue-500/30",
  stopping: "bg-yellow-600/20 text-yellow-400 border-yellow-500/30",
  completed: "bg-green-600/20 text-green-400 border-green-500/30",
  stopped: "bg-muted text-muted-foreground",
  error: "bg-red-600/20 text-red-400 border-red-500/30",
};

export function TopBar({ snapshot }: TopBarProps) {
  const status = snapshot?.status || "idle";
  const currentStage = snapshot?.current_stage_title || "-";
  const currentAgent = snapshot?.current_agent || "-";
  const elapsed = snapshot?.elapsed_seconds;
  const resultsPath = snapshot?.results_path || "--";

  return (
    <header className="h-12 border-b border-border bg-card px-4 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <h1 className="text-sm font-semibold tracking-tight">
          TradingAgents
        </h1>

        <div className="flex items-center gap-3">
          <Badge
            variant="outline"
            className={cn(
              "text-[10px] font-mono font-semibold tracking-wider px-2 py-0.5 border",
              STATUS_COLORS[status]
            )}
          >
            {STATUS_LABELS[status]}
          </Badge>

          <span className="text-xs text-muted-foreground">
            <span className="text-muted-foreground/60">Stage:</span>{" "}
            <span className="text-foreground">{currentStage}</span>
          </span>

          <span className="text-xs text-muted-foreground">
            <span className="text-muted-foreground/60">Agent:</span>{" "}
            <span className="text-foreground">{currentAgent}</span>
          </span>

          <span className="text-xs text-muted-foreground">
            <span className="text-muted-foreground/60">Elapsed:</span>{" "}
            <span className="text-foreground font-mono">
              {elapsed != null ? `${elapsed}s` : "--"}
            </span>
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <span className="text-xs text-muted-foreground font-mono truncate max-w-[300px]">
          {resultsPath}
        </span>
      </div>
    </header>
  );
}
