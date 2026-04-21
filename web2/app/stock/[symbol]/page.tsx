"use client";

import { useState, useEffect, useMemo } from "react";
import { useParams } from "next/navigation";
import { cn } from "@/lib/utils";
import { getStockInfo, getStockMarketData, getStockStats, getTimeRangeDates } from "@/lib/stock-api";
import type { StockInfo, StockMarketData, StockStats, TimeRange, IndicatorSettings } from "@/lib/types";
import { TIME_RANGE_OPTIONS } from "@/lib/types";
import { StockStatsCards } from "@/components/stock-board/stock-stats-cards";
import { StockChartSection } from "@/components/stock-board/stock-chart-section";
import { StockTableSection } from "@/components/stock-board/stock-table-section";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function StockPage() {
  const params = useParams();
  const symbol = params.symbol as string;

  const [info, setInfo] = useState<StockInfo | null>(null);
  const [data, setData] = useState<StockMarketData[]>([]);
  const [stats, setStats] = useState<StockStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [timeRange, setTimeRange] = useState<TimeRange>("1m");
  const [indicators, setIndicators] = useState<IndicatorSettings>({
    showMA: true,
    showRSI: true,
    showMACD: true,
    showATR: false,
  });

  // 初始化：获取股票信息
  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const stockInfo = await getStockInfo(symbol);
        setInfo(stockInfo);
      } catch {
        // API 失败时使用 symbol 作为 fallback
        setInfo({ code: symbol, name: symbol, market: symbol.endsWith(".SH") ? "SH" : "SZ" });
      }
    };
    fetchInfo();
  }, [symbol]);

  // 获取行情数据
  useEffect(() => {
    if (!info) return;

    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const today = new Date().toISOString().split("T")[0];
        const { startDate, endDate } = getTimeRangeDates(timeRange, today);

        const marketRes = await getStockMarketData(symbol, startDate, endDate);
        setData(marketRes.data);

        const statsRes = await getStockStats(symbol);
        setStats(statsRes.stats);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [symbol, timeRange, info]);

  const handleRefresh = () => {
    const today = new Date().toISOString().split("T")[0];
    const { startDate, endDate } = getTimeRangeDates(timeRange, today);
    setLoading(true);
    getStockMarketData(symbol, startDate, endDate)
      .then((res) => setData(res.data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  if (loading && !data.length) {
    return (
      <div className="flex flex-col h-full">
        <div className="h-12 border-b border-border flex items-center px-4">
          <Badge variant="outline">{symbol}</Badge>
          <span className="ml-2 text-sm text-muted-foreground">加载中...</span>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-muted-foreground">加载行情数据...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col h-full">
        <div className="h-12 border-b border-border flex items-center px-4">
          <Badge variant="outline">{symbol}</Badge>
          <Badge variant="destructive" className="ml-2">错误</Badge>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-destructive">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Top Bar */}
      <div className="h-12 border-b border-border flex items-center px-4 gap-4">
        <span className="font-medium">行情看板</span>
        <Badge variant="outline">{symbol}</Badge>
        <span className="text-sm">{info?.name}</span>
        {stats?.latest && (
          <Badge
            variant={stats.latest.change_direction === "up" ? "default" : stats.latest.change_direction === "down" ? "destructive" : "secondary"}
            className={cn(
              stats.latest.change_direction === "up" && "bg-green-500/20 text-green-400 border-green-500/30",
              stats.latest.change_direction === "down" && "bg-red-500/20 text-red-400 border-red-500/30"
            )}
          >
            {stats.latest.change_pct > 0 ? "+" : ""}{stats.latest.change_pct?.toFixed(2)}%
          </Badge>
        )}
        <div className="flex-1" />
        <Button variant="ghost" size="sm" onClick={handleRefresh} disabled={loading}>
          刷新
        </Button>
      </div>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 border-r border-border p-4 space-y-4 hidden lg:block">
          <div className="space-y-2">
            <div className="text-xs text-muted-foreground uppercase">时间范围</div>
            <div className="flex flex-wrap gap-2">
              {TIME_RANGE_OPTIONS.map((opt) => (
                <Button
                  key={opt.value}
                  variant={timeRange === opt.value ? "default" : "outline"}
                  size="sm"
                  onClick={() => setTimeRange(opt.value)}
                >
                  {opt.label}
                </Button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <div className="text-xs text-muted-foreground uppercase">指标开关</div>
            <div className="space-y-1">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={indicators.showMA}
                  onChange={(e) => setIndicators({ ...indicators, showMA: e.target.checked })}
                  className="rounded border-border"
                />
                均线
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={indicators.showRSI}
                  onChange={(e) => setIndicators({ ...indicators, showRSI: e.target.checked })}
                  className="rounded border-border"
                />
                RSI
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={indicators.showMACD}
                  onChange={(e) => setIndicators({ ...indicators, showMACD: e.target.checked })}
                  className="rounded border-border"
                />
                MACD
              </label>
            </div>
          </div>

          {stats?.range_stats && (
            <div className="space-y-2">
              <div className="text-xs text-muted-foreground uppercase">区间统计</div>
              <div className="text-xs space-y-1 text-muted-foreground">
                <div>区间天数: {stats.range_stats.period_days}</div>
                <div>最高: {stats.range_stats.high}</div>
                <div>最低: {stats.range_stats.low}</div>
                <div>振幅: {stats.range_stats.amplitude}%</div>
                <div>均量: {(stats.range_stats.avg_vol / 1000).toFixed(0)}K</div>
              </div>
            </div>
          )}
        </aside>

        {/* Main Area */}
        <main className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Stats Cards */}
          {stats?.latest && <StockStatsCards latest={stats.latest} />}

          {/* Charts */}
          <StockChartSection data={data} indicators={indicators} />

          {/* Table */}
          <StockTableSection data={data} />
        </main>
      </div>
    </div>
  );
}