"use client";

import { Card } from "@/components/ui/card";
import type { Snapshot } from "@/lib/types";

interface StatsOverviewProps {
  snapshot: Snapshot | null;
}

export function StatsOverview({ snapshot }: StatsOverviewProps) {
  const stats = snapshot?.stats || { llm_calls: 0, tool_calls: 0 };
  const counts = snapshot?.counts || {
    agents_completed: 0,
    agents_total: 0,
    reports_completed: 0,
    reports_total: 0,
  };
  const eventCount = snapshot?.events?.length || 0;

  const items = [
    { label: "LLM Calls", value: stats.llm_calls },
    { label: "Tool Calls", value: stats.tool_calls },
    {
      label: "Agents",
      value: `${counts.agents_completed} / ${counts.agents_total}`,
    },
    {
      label: "Reports",
      value: `${counts.reports_completed} / ${counts.reports_total}`,
    },
    { label: "Events", value: eventCount },
  ];

  return (
    <div className="grid grid-cols-5 gap-3">
      {items.map((item) => (
        <Card
          key={item.label}
          className="bg-card border-border p-3"
        >
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
            {item.label}
          </div>
          <div className="text-xl font-semibold font-mono tracking-tight">
            {item.value}
          </div>
        </Card>
      ))}
    </div>
  );
}
