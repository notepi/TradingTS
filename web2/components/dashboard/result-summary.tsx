"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { REPORT_TITLES, type Snapshot } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ResultSummaryProps {
  snapshot: Snapshot | null;
}

export function ResultSummary({ snapshot }: ResultSummaryProps) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const reportSections = snapshot?.report_sections || {};
  const finalReport = snapshot?.final_report;
  const reportFile = snapshot?.report_file;

  const entries = Object.entries(reportSections).filter(([, v]) => v);
  const selectedSection = selectedKey
    ? reportSections[selectedKey]
    : entries[0]?.[1] || null;
  const selectedTitle = selectedKey
    ? REPORT_TITLES[selectedKey] || selectedKey
    : entries[0]
      ? REPORT_TITLES[entries[0][0]] || entries[0][0]
      : null;

  return (
    <Card className="bg-card border-border">
      <div className="p-4 border-b border-border space-y-3">
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Result Summary
        </h2>

        {entries.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {entries.map(([key]) => (
              <Button
                key={key}
                variant="outline"
                size="sm"
                onClick={() => setSelectedKey(key)}
                className={cn(
                  "h-6 text-[10px] font-medium px-2",
                  selectedKey === key
                    ? "bg-primary/20 border-primary/50 text-primary"
                    : "bg-muted/50 border-border"
                )}
              >
                {REPORT_TITLES[key] || key}
              </Button>
            ))}
          </div>
        )}
      </div>

      <div className="p-4 space-y-3">
        {selectedSection ? (
          <pre className="text-xs font-mono leading-relaxed whitespace-pre-wrap bg-muted/50 p-3 rounded border border-border max-h-80 overflow-y-auto">
            {selectedSection}
          </pre>
        ) : finalReport ? (
          <pre className="text-xs font-mono leading-relaxed whitespace-pre-wrap bg-muted/50 p-3 rounded border border-border max-h-80 overflow-y-auto">
            {finalReport}
          </pre>
        ) : (
          <p className="text-xs text-muted-foreground italic">
            分析完成后，这里会显示整合后的完整报告
          </p>
        )}

        {reportFile && (
          <div className="pt-2 border-t border-border">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
              报告文件
            </p>
            <p className="text-xs font-mono text-muted-foreground truncate">
              {reportFile}
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}
