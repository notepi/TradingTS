"use client";

import {
  ComposedChart,
  Line,
  Bar,
  Cell,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { StockMarketData } from "@/lib/types";

interface StockPriceChartProps {
  data: StockMarketData[];
  showMA?: boolean;
}

export function StockPriceChart({ data, showMA = true }: StockPriceChartProps) {
  const chartData = data.map((item) => ({
    date: item.trade_date.slice(5), // MM-DD
    close: item.close,
    ma5: item.ma5,
    ma10: item.ma10,
    ma20: item.ma20,
    ma50: item.ma50,
    vol: item.vol,
    change_pct: item.change_pct ?? 0,
    isUp: item.change_pct != null && item.change_pct >= 0,
  }));

  const minPrice = Math.min(...data.map((d) => d.low || d.close));
  const maxPrice = Math.max(...data.map((d) => d.high || d.close));
  const priceRange = maxPrice - minPrice;

  return (
    <div className="space-y-2">
      {/* Price Chart */}
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart data={chartData}>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: "#888" }}
            axisLine={{ stroke: "#333" }}
            tickLine={false}
          />
          <YAxis
            yAxisId="price"
            domain={[minPrice - priceRange * 0.1, maxPrice + priceRange * 0.1]}
            tick={{ fontSize: 10, fill: "#888" }}
            axisLine={{ stroke: "#333" }}
            tickLine={false}
            orientation="right"
          />
          <Tooltip
            contentStyle={{
              background: "#1a1d21",
              border: "1px solid #333",
              borderRadius: "4px",
            }}
            labelStyle={{ color: "#888" }}
          />

          {/* Close Price Line */}
          <Line
            yAxisId="price"
            type="monotone"
            dataKey="close"
            stroke="#58a6ff"
            dot={false}
            strokeWidth={2}
          />

          {/* MA Lines */}
          {showMA && (
            <>
              <Line yAxisId="price" type="monotone" dataKey="ma5" stroke="#3fb950" dot={false} strokeWidth={1} />
              <Line yAxisId="price" type="monotone" dataKey="ma10" stroke="#d29922" dot={false} strokeWidth={1} />
              <Line yAxisId="price" type="monotone" dataKey="ma20" stroke="#f85149" dot={false} strokeWidth={1} />
              <Line yAxisId="price" type="monotone" dataKey="ma50" stroke="#a371f7" dot={false} strokeWidth={1} strokeDasharray="3 3" />
            </>
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Volume Chart */}
      <ResponsiveContainer width="100%" height={80}>
        <ComposedChart data={chartData}>
          <XAxis dataKey="date" tick={false} axisLine={{ stroke: "#333" }} />
          <YAxis yAxisId="vol" tick={{ fontSize: 10, fill: "#888" }} orientation="right" tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{ background: "#1a1d21", border: "1px solid #333" }}
            labelStyle={{ color: "#888" }}
          />
          <Bar yAxisId="vol" dataKey="vol" strokeWidth={1}>
            {chartData.map((entry, idx) => (
              <Cell
                key={idx}
                fill={entry.isUp ? "#3fb95033" : "#f8514933"}
                stroke={entry.isUp ? "#3fb950" : "#f85149"}
              />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}