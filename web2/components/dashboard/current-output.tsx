"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { REPORT_TITLES, type Snapshot, type ProcessEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

interface CurrentOutputProps {
  snapshot: Snapshot | null;
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  message: "bg-blue-600/20 text-blue-400 border-blue-500/30",
  tool: "bg-yellow-600/20 text-yellow-400 border-yellow-500/30",
  report: "bg-green-600/20 text-green-400 border-green-500/30",
  status: "bg-muted text-muted-foreground",
};

export function CurrentOutput({ snapshot }: CurrentOutputProps) {
  const [selectedReport, setSelectedReport] = useState<string | null>(null);

  const focusEvent = snapshot?.current_focus_event;
  const events = snapshot?.events || [];
  const reportSections = snapshot?.report_sections || {};
  const currentReport = snapshot?.current_report;
  const decision = snapshot?.decision;

  const timelineEvents = events
    .filter((e) => ["message", "tool", "report"].includes(e.type) && e.agent && e.agent !== "System")
    .sort((a, b) => (b.id || 0) - (a.id || 0))
    .slice(0, 20);

  const reportEntries = Object.entries(reportSections).filter(([, v]) => v);

  return (
    <Card className="bg-card border-border">
      <Tabs defaultValue="timeline" className="w-full">
        <div className="border-b border-border px-4">
          <TabsList className="h-9 bg-transparent -mb-px gap-4">
            <TabsTrigger
              value="current"
              className="text-xs data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:bg-transparent rounded-none h-9 px-2"
            >
              当前发言
            </TabsTrigger>
            <TabsTrigger
              value="timeline"
              className="text-xs data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:bg-transparent rounded-none h-9 px-2"
            >
              发言时间线
            </TabsTrigger>
            <TabsTrigger
              value="report"
              className="text-xs data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:bg-transparent rounded-none h-9 px-2"
            >
              最近报告
            </TabsTrigger>
            <TabsTrigger
              value="decision"
              className="text-xs data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:bg-transparent rounded-none h-9 px-2"
            >
              当前决策
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="current" className="p-4">
          {focusEvent ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Badge
                  variant="outline"
                  className={cn(
                    "text-[10px] font-mono",
                    EVENT_TYPE_COLORS[focusEvent.type]
                  )}
                >
                  {focusEvent.type?.toUpperCase()}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {focusEvent.agent || "-"}
                </span>
                <span className="text-xs text-muted-foreground/60">
                  {focusEvent.timestamp || "-"}
                </span>
              </div>
              <pre className="text-xs font-mono leading-relaxed whitespace-pre-wrap bg-muted/50 p-3 rounded border border-border">
                {focusEvent.content || "(empty)"}
              </pre>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground italic">
              当前还没有可展示的发言内容
            </p>
          )}
        </TabsContent>

        <TabsContent value="timeline" className="p-0">
          <Accordion className="w-full">
            {timelineEvents.length === 0 ? (
              <div className="p-4">
                <p className="text-xs text-muted-foreground italic">
                  等待角色开始发言...
                </p>
              </div>
            ) : (
              timelineEvents.map((event, index) => (
                <AccordionItem
                  key={event.id || index}
                  value={`event-${event.id || index}`}
                  className="border-b border-border px-4"
                >
                  <AccordionTrigger className="py-2 hover:no-underline">
                    <div className="flex items-center gap-2 text-left">
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[10px] font-mono shrink-0",
                          EVENT_TYPE_COLORS[event.type]
                        )}
                      >
                        {event.type?.toUpperCase()}
                      </Badge>
                      <span className="text-xs font-medium truncate">
                        {event.agent || "-"}
                      </span>
                      <span className="text-[10px] text-muted-foreground shrink-0">
                        {event.timestamp || "-"}
                      </span>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <pre className="text-xs font-mono leading-relaxed whitespace-pre-wrap bg-muted/50 p-3 rounded border border-border mb-2">
                      {event.content || "(empty)"}
                    </pre>
                  </AccordionContent>
                </AccordionItem>
              ))
            )}
          </Accordion>
        </TabsContent>

        <TabsContent value="report" className="p-4">
          {currentReport ? (
            <pre className="text-xs font-mono leading-relaxed whitespace-pre-wrap bg-muted/50 p-3 rounded border border-border">
              {currentReport}
            </pre>
          ) : (
            <p className="text-xs text-muted-foreground italic">
              等待新的报告片段...
            </p>
          )}
        </TabsContent>

        <TabsContent value="decision" className="p-4">
          {decision ? (
            <div className="bg-primary/10 border border-primary/30 rounded p-4">
              <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">
                最终评级
              </div>
              <div className="text-lg font-semibold">{decision}</div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground italic">
              分析完成后这里会显示决策结果
            </p>
          )}
        </TabsContent>
      </Tabs>
    </Card>
  );
}
