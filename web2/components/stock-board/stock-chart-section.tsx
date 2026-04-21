"use client";

import type { StockMarketData, IndicatorSettings } from "@/lib/types";
import { StockPriceChart } from "./stock-price-chart";
import { StockMACDChart } from "./stock-macd-chart";
import { StockRSIChart } from "./stock-rsi-chart";

interface StockChartSectionProps {
  data: StockMarketData[];
  indicators: IndicatorSettings;
}

export function StockChartSection({ data, indicators }: StockChartSectionProps) {
  if (!data.length) {
    return (
      <div className="border border-border rounded-lg p-4 text-center text-muted-foreground">
        无数据
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Price + Volume Chart */}
      <div className="border border-border rounded-lg p-4">
        <div className="text-xs text-muted-foreground uppercase mb-2">价格走势</div>
        <StockPriceChart data={data} showMA={indicators.showMA} />
      </div>

      {/* Technical Indicators Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {indicators.showMACD && (
          <div className="border border-border rounded-lg p-4">
            <div className="text-xs text-muted-foreground uppercase mb-2">MACD</div>
            <StockMACDChart data={data} />
          </div>
        )}

        {indicators.showRSI && (
          <div className="border border-border rounded-lg p-4">
            <div className="text-xs text-muted-foreground uppercase mb-2">RSI</div>
            <StockRSIChart data={data} />
          </div>
        )}
      </div>
    </div>
  );
}