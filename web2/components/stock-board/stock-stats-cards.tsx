"use client";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";

interface StockStatsCardsProps {
  latest: {
    trade_date: string;
    close: number;
    change_pct: number;
    change_direction: "up" | "down" | "flat";
    vol: number;
    ma5_position: "above" | "below";
    rsi14_zone: "overbought" | "neutral" | "oversold";
    macd_state: string;
    trend_signal: string;
  };
}

export function StockStatsCards({ latest }: StockStatsCardsProps) {
  const cards = [
    {
      label: "最新价",
      value: latest.close.toFixed(2),
      sub: latest.trade_date,
    },
    {
      label: "涨跌幅",
      value: `${latest.change_pct > 0 ? "+" : ""}${latest.change_pct.toFixed(2)}%`,
      sub: latest.change_direction === "up" ? "上涨" : latest.change_direction === "down" ? "下跌" : "持平",
      color: latest.change_direction === "up" ? "text-green-400" : latest.change_direction === "down" ? "text-red-400" : "text-muted-foreground",
    },
    {
      label: "成交量",
      value: formatVolume(latest.vol),
      sub: `${(latest.vol / 1000).toFixed(0)}K`,
    },
    {
      label: "RSI14",
      value: latest.rsi14_zone === "overbought" ? "超买" : latest.rsi14_zone === "oversold" ? "超卖" : "中性",
      sub: latest.rsi14_zone === "overbought" ? ">70" : latest.rsi14_zone === "oversold" ? "<30" : "30-70",
      color: latest.rsi14_zone === "overbought" ? "text-red-400" : latest.rsi14_zone === "oversold" ? "text-green-400" : "text-muted-foreground",
    },
    {
      label: "MA5位置",
      value: latest.ma5_position === "above" ? "上方" : "下方",
      sub: latest.ma5_position === "above" ? "强支撑" : "弱支撑",
      color: latest.ma5_position === "above" ? "text-green-400" : "text-red-400",
    },
    {
      label: "MACD",
      value: latest.macd_state || "N/A",
      sub: "",
    },
    {
      label: "趋势",
      value: latest.trend_signal || "N/A",
      sub: "",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
      {cards.map((card) => (
        <Card key={card.label} className="p-3 space-y-1">
          <div className="text-xs text-muted-foreground uppercase">{card.label}</div>
          <div className={cn("text-lg font-medium", card.color)}>
            {card.value}
          </div>
          {card.sub && (
            <div className="text-xs text-muted-foreground">{card.sub}</div>
          )}
        </Card>
      ))}
    </div>
  );
}

function formatVolume(vol: number): string {
  if (vol >= 10000) {
    return `${(vol / 10000).toFixed(1)}万`;
  }
  return vol.toFixed(0);
}