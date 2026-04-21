"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import type { Snapshot, ProcessEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ProcessTreeProps {
  snapshot: Snapshot | null;
}

type EventFilter = "all" | "report" | "tool" | "message";

const EVENT_FILTER_OPTIONS: { value: EventFilter; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "report", label: "Report" },
  { value: "tool", label: "Tool" },
  { value: "message", label: "Message" },
];

const EVENT_TYPE_COLORS: Record<string, string> = {
  message: "bg-blue-600/20 text-blue-400 border-blue-500/30",
  tool: "bg-yellow-600/20 text-yellow-400 border-yellow-500/30",
  report: "bg-green-600/20 text-green-400 border-green-500/30",
  status: "bg-muted text-muted-foreground",
};

const STAGE_STATUS_COLORS: Record<string, string> = {
  pending: "bg-muted text-muted-foreground",
  in_progress: "bg-blue-600/20 text-blue-400",
  completed: "bg-green-600/20 text-green-400",
  error: "bg-red-600/20 text-red-400",
};

export function ProcessTree({ snapshot }: ProcessTreeProps) {
  const [eventFilter, setEventFilter] = useState<EventFilter>("all");

  const processTree = snapshot?.process_tree || [];
  const currentStageId = snapshot?.current_stage_id;
  const currentAgent = snapshot?.current_agent;
  const eventCount = snapshot?.events?.length || 0;

  const filteredTree = processTree
    .map((stage) => ({
      ...stage,
      agents: (stage.agents || [])
        .map((agent) => ({
          ...agent,
          filteredEvents: (agent.events || []).filter((e) =>
            eventFilter === "all" ? true : e.type === eventFilter
          ),
        }))
        .filter((agent) =>
          eventFilter === "all"
            ? true
            : agent.filteredEvents.length > 0 || agent.name === currentAgent
        ),
    }))
    .filter((stage) =>
      eventFilter === "all"
        ? true
        : (stage.agents || []).length > 0 || stage.id === currentStageId
    );

  const totalFilteredEvents = filteredTree.reduce(
    (sum, stage) =>
      sum + stage.agents.reduce((aSum, agent) => aSum + agent.filteredEvents.length, 0),
    0
  );

  return (
    <Card className="bg-card border-border">
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            执行流程
          </h2>
          <div className="flex items-center gap-3">
            <div className="flex gap-1">
              {EVENT_FILTER_OPTIONS.map((opt) => (
                <Button
                  key={opt.value}
                  variant="outline"
                  size="sm"
                  onClick={() => setEventFilter(opt.value)}
                  className={cn(
                    "h-6 text-[10px] px-2",
                    eventFilter === opt.value
                      ? "bg-primary/20 border-primary/50"
                      : "bg-muted/50 border-border"
                  )}
                >
                  {opt.label}
                </Button>
              ))}
            </div>
            <Badge variant="outline" className="text-[10px] font-mono">
              {totalFilteredEvents} 事件
            </Badge>
          </div>
        </div>
      </div>

      <div className="max-h-[500px] overflow-y-auto">
        {filteredTree.length === 0 ? (
          <div className="p-4">
            <p className="text-xs text-muted-foreground italic">
              {eventFilter === "all"
                ? "还没有过程内容，启动分析后这里会逐步展开"
                : "当前过滤条件下还没有可展示的事件"}
            </p>
          </div>
        ) : (
          <Accordion className="w-full">
            {filteredTree.map((stage, stageIndex) => {
              const isCurrentStage = stage.id === currentStageId;
              const stageEvents = stage.agents.reduce(
                (sum, a) => sum + a.filteredEvents.length,
                0
              );

              return (
                <AccordionItem
                  key={stage.id}
                  value={`stage-${stage.id}`}
                  className={cn(
                    "border-b border-border",
                    isCurrentStage && "bg-blue-600/5"
                  )}
                >
                  <AccordionTrigger className="px-4 hover:no-underline">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono text-muted-foreground w-4">
                        {stageIndex + 1}
                      </span>
                      <span className="text-sm font-medium">{stage.title}</span>
                      <span className="text-[10px] text-muted-foreground">
                        {stage.completed_agents}/{stage.total_agents} agents ·{" "}
                        {stageEvents} 事件
                      </span>
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[10px] font-mono ml-auto",
                          STAGE_STATUS_COLORS[stage.status]
                        )}
                      >
                        {stage.status.toUpperCase()}
                      </Badge>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="pl-4 pr-4 pb-2 space-y-2">
                      {stage.agents.map((agent) => {
                        const isCurrentAgent = agent.name === currentAgent;
                        const events = agent.filteredEvents;

                        return (
                          <div
                            key={agent.name}
                            className={cn(
                              "rounded border border-border p-2",
                              isCurrentAgent && "border-blue-500/30 bg-blue-600/5"
                            )}
                          >
                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-xs font-medium">
                                {agent.name}
                              </span>
                              <Badge
                                variant="outline"
                                className={cn(
                                  "text-[10px] font-mono",
                                  STAGE_STATUS_COLORS[agent.status]
                                )}
                              >
                                {agent.status.toUpperCase()}
                              </Badge>
                              {isCurrentAgent && (
                                <Badge
                                  variant="outline"
                                  className="text-[10px] font-mono bg-yellow-600/20 text-yellow-400 border-yellow-500/30"
                                >
                                  CURRENT
                                </Badge>
                              )}
                              <span className="text-[10px] text-muted-foreground ml-auto">
                                {events.length} 事件
                              </span>
                            </div>

                            {events.length > 0 ? (
                              <div className="space-y-1">
                                {events.slice(0, 5).map((event, idx) => (
                                  <EventItem key={event.id || idx} event={event} />
                                ))}
                                {events.length > 5 && (
                                  <p className="text-[10px] text-muted-foreground text-center py-1">
                                    +{events.length - 5} 更多事件
                                  </p>
                                )}
                              </div>
                            ) : (
                              <p className="text-[10px] text-muted-foreground italic">
                                No matching events
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        )}
      </div>
    </Card>
  );
}

function EventItem({ event }: { event: ProcessEvent }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="rounded bg-muted/50 border border-border overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2 px-2 py-1.5 text-left hover:bg-muted/70 transition-colors"
      >
        <Badge
          variant="outline"
          className={cn(
            "text-[9px] font-mono shrink-0",
            EVENT_TYPE_COLORS[event.type]
          )}
        >
          {event.type?.toUpperCase()}
        </Badge>
        <span className="text-[10px] truncate flex-1">{event.label}</span>
        <span className="text-[9px] text-muted-foreground shrink-0">
          {isOpen ? "▲" : "▼"}
        </span>
      </button>
      {isOpen && (
        <div className="px-2 py-1.5 border-t border-border">
          <pre className="text-[10px] font-mono leading-relaxed whitespace-pre-wrap text-muted-foreground">
            {event.content}
          </pre>
        </div>
      )}
    </div>
  );
}
