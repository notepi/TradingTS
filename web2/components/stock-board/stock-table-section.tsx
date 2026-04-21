"use client";

import type { StockMarketData } from "@/lib/types";

interface StockTableSectionProps {
  data: StockMarketData[];
}

export function StockTableSection({ data }: StockTableSectionProps) {
  if (!data.length) {
    return (
      <div className="border border-border rounded-lg p-4 text-center text-muted-foreground">
        无数据
      </div>
    );
  }

  // 只显示最近 20 条数据
  const displayData = data.slice(-20).reverse();

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <div className="text-xs text-muted-foreground uppercase p-3 border-b border-border">
        最近交易明细
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border bg-muted/20">
              <th className="h-8 px-3 text-left text-muted-foreground">日期</th>
              <th className="h-8 px-3 text-right text-muted-foreground">收盘价</th>
              <th className="h-8 px-3 text-right text-muted-foreground">涨跌幅</th>
              <th className="h-8 px-3 text-right text-muted-foreground">成交量</th>
              <th className="h-8 px-3 text-right text-muted-foreground">MA5</th>
              <th className="h-8 px-3 text-right text-muted-foreground">MA10</th>
              <th className="h-8 px-3 text-right text-muted-foreground">RSI14</th>
              <th className="h-8 px-3 text-right text-muted-foreground">MACD</th>
              <th className="h-8 px-3 text-left text-muted-foreground">趋势</th>
            </tr>
          </thead>
          <tbody>
            {displayData.map((row) => (
              <tr key={row.trade_date} className="border-b border-border hover:bg-muted/10">
                <td className="px-3 py-2">{row.trade_date}</td>
                <td className="px-3 py-2 text-right">{row.close?.toFixed(2)}</td>
                <td className="px-3 py-2 text-right">
                  <span
                    className={
                      row.change_pct > 0
                        ? "text-green-400"
                        : row.change_pct < 0
                        ? "text-red-400"
                        : "text-muted-foreground"
                    }
                  >
                    {row.change_pct ? `${row.change_pct > 0 ? "+" : ""}${row.change_pct.toFixed(2)}%` : "-"}
                  </span>
                </td>
                <td className="px-3 py-2 text-right">{formatVol(row.vol)}</td>
                <td className="px-3 py-2 text-right">{row.ma5?.toFixed(2) || "-"}</td>
                <td className="px-3 py-2 text-right">{row.ma10?.toFixed(2) || "-"}</td>
                <td className="px-3 py-2 text-right">
                  <span
                    className={
                      row.rsi14 > 70
                        ? "text-red-400"
                        : row.rsi14 < 30
                        ? "text-green-400"
                        : "text-muted-foreground"
                    }
                  >
                    {row.rsi14?.toFixed(1) || "-"}
                  </span>
                </td>
                <td className="px-3 py-2 text-right">
                  <span
                    className={
                      row.macd_hist > 0
                        ? "text-green-400"
                        : row.macd_hist < 0
                        ? "text-red-400"
                        : "text-muted-foreground"
                    }
                  >
                    {row.macd_hist?.toFixed(2) || "-"}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <span className="text-muted-foreground">{row.short_trend || "-"}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatVol(vol: number): string {
  if (!vol) return "-";
  if (vol >= 10000) {
    return `${(vol / 10000).toFixed(1)}万`;
  }
  return `${(vol / 1000).toFixed(0)}K`;
}