"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  WORKFLOW_BLUEPRINT,
  ANALYST_NAME_MAP,
  type Snapshot,
} from "@/lib/types";
import { cn } from "@/lib/utils";

interface WorkflowOverviewProps {
  snapshot: Snapshot | null;
}

const STAGE_STATUS_COLORS: Record<string, string> = {
  pending: "bg-muted text-muted-foreground",
  in_progress: "bg-blue-600/20 text-blue-400 border-blue-500/30",
  completed: "bg-green-600/20 text-green-400 border-green-500/30",
  error: "bg-red-600/20 text-red-400 border-red-500/30",
};

export function WorkflowOverview({ snapshot }: WorkflowOverviewProps) {
  const workflow = snapshot?.workflow || [];
  const processTree = snapshot?.process_tree || [];
  const agentStatus = snapshot?.agent_status || {};
  const currentStageId = snapshot?.current_stage_id;
  const currentAgent = snapshot?.current_agent;

  const selectedAnalysts = new Set(
    snapshot?.selections?.analysts || ["market", "social", "news", "fundamentals"]
  );

  return (
    <div className="space-y-3">
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        工作流概览
      </h2>

      <div className="grid grid-cols-5 gap-3">
        {WORKFLOW_BLUEPRINT.map((stage, stageIndex) => {
          const runtimeStage = workflow.find((s) => s.id === stage.id);
          const processStage = processTree.find((s) => s.id === stage.id);

          const visibleRoles = stage.roles.filter(
            (role) => stage.id !== "analysts" || selectedAnalysts.has(role)
          );

          const totalAgents = visibleRoles.length;
          const completedAgents = visibleRoles.filter(
            (role) => {
              const name = ANALYST_NAME_MAP[role] || role;
              const status = agentStatus[name] || processStage?.agents?.find(
                (a) => a.name === name
              )?.status;
              return status === "completed";
            }
          ).length;

          const progress = totalAgents > 0 ? (completedAgents / totalAgents) * 100 : 0;
          const isCurrentStage = currentStageId === stage.id;

          return (
            <Card
              key={stage.id}
              className={cn(
                "bg-card border-border p-3 space-y-2",
                isCurrentStage && "border-blue-500/50"
              )}
            >
              <div className="flex items-center justify-between">
                <Badge
                  variant="outline"
                  className={cn(
                    "text-[10px] font-mono tracking-wider px-1.5 py-0",
                    STAGE_STATUS_COLORS[runtimeStage?.status || "pending"]
                  )}
                >
                  {runtimeStage?.status?.toUpperCase() || "PENDING"}
                </Badge>
                <span className="text-[10px] text-muted-foreground font-mono">
                  步骤 {stageIndex + 1}
                </span>
              </div>

              <div>
                <h3 className="text-sm font-medium leading-tight">
                  {stage.title}
                </h3>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  {completedAgents} / {totalAgents} 智能体
                </p>
              </div>

              <div className="h-1 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>

              <div className="space-y-1">
                {visibleRoles.slice(0, 3).map((role) => {
                  const name = ANALYST_NAME_MAP[role] || role;
                  const status = agentStatus[name] || "pending";
                  const isCurrentAgent = currentAgent === name;

                  return (
                    <div
                      key={role}
                      className={cn(
                        "flex items-center justify-between text-[10px] px-1.5 py-0.5 rounded",
                        isCurrentAgent && "bg-blue-600/20 text-blue-400"
                      )}
                    >
                      <span className="truncate">{name}</span>
                      <span
                        className={cn(
                          "text-[9px] font-mono uppercase",
                          status === "completed" && "text-green-400",
                          status === "in_progress" && "text-yellow-400",
                          status === "pending" && "text-muted-foreground",
                          status === "error" && "text-red-400"
                        )}
                      >
                        {status}
                      </span>
                    </div>
                  );
                })}
                {visibleRoles.length > 3 && (
                  <p className="text-[9px] text-muted-foreground text-center">
                    +{visibleRoles.length - 3} 更多
                  </p>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
