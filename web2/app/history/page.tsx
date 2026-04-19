"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import type { HistoryRun, DashboardOptions } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  idle: "bg-muted text-muted-foreground",
  running: "bg-blue-600/20 text-blue-400",
  completed: "bg-green-600/20 text-green-400",
  error: "bg-red-600/20 text-red-400",
  stopped: "bg-muted text-muted-foreground",
};

export default function HistoryPage() {
  const [runs, setRuns] = useState<HistoryRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await api.getHistory();
      setRuns(res.runs);
    } catch (err) {
      console.error("Failed to fetch history:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleDelete = async (runId: string) => {
    if (!confirm(`确认删除这条历史分析？\n\n${runId}`)) return;

    setDeletingId(runId);
    try {
      const res = await api.deleteHistoryRun({ run_id: runId });
      setRuns(res.runs);
    } catch (err) {
      console.error("Failed to delete:", err);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="min-h-full bg-background">
      <header className="border-b border-border bg-card">
        <div className="px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
              ← Dashboard
            </Link>
            <h1 className="text-sm font-semibold">历史分析</h1>
          </div>
          <Button onClick={fetchHistory} variant="outline" size="sm" className="h-8">
            刷新
          </Button>
        </div>
      </header>

      <main className="p-6">
        <Card className="bg-card border-border">
          {loading ? (
            <div className="p-6 text-center text-sm text-muted-foreground">
              正在读取历史分析...
            </div>
          ) : runs.length === 0 ? (
            <div className="p-6 text-center text-sm text-muted-foreground italic">
              还没有可加载的历史分析
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="text-xs">Ticker</TableHead>
                  <TableHead className="text-xs">日期</TableHead>
                  <TableHead className="text-xs">状态</TableHead>
                  <TableHead className="text-xs">开始时间</TableHead>
                  <TableHead className="text-xs w-[100px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => (
                  <TableRow key={run.id} className="border-border">
                    <TableCell className="font-mono text-sm font-medium">
                      {run.ticker}
                    </TableCell>
                    <TableCell className="text-sm">
                      {run.analysis_date || "-"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[10px] font-mono",
                          STATUS_COLORS[run.status] || STATUS_COLORS.idle
                        )}
                      >
                        {run.status?.toUpperCase() || "IDLE"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {run.started_at || run.updated_at || "-"}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-[10px]"
                          onClick={() => {
                            window.location.href = `/?run_id=${run.id}`;
                          }}
                        >
                          加载
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-[10px] text-destructive border-destructive/30 hover:bg-destructive/10"
                          disabled={deletingId === run.id}
                          onClick={() => handleDelete(run.id)}
                        >
                          {deletingId === run.id ? "删除中..." : "删除"}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>
      </main>
    </div>
  );
}
