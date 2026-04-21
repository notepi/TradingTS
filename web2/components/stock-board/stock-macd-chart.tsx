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
  ReferenceLine,
} from "recharts";
import type { StockMarketData } from "@/lib/types";

interface StockMACDChartProps {
  data: StockMarketData[];
}

export function StockMACDChart({ data }: StockMACDChartProps) {
  const chartData = data.map((item) => ({
    date: item.trade_date.slice(5),
    dif: item.macd_dif ?? 0,
    dea: item.macd_dea ?? 0,
    hist: item.macd_hist ?? 0,
    histPositive: item.macd_hist != null && item.macd_hist >= 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={150}>
      <ComposedChart data={chartData}>
        <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#888" }} axisLine={{ stroke: "#333" }} tickLine={false} />
        <YAxis tick={{ fontSize: 10, fill: "#888" }} orientation="right" tickLine={false} axisLine={false} />
        <Tooltip
          contentStyle={{ background: "#1a1d21", border: "1px solid #333" }}
          labelStyle={{ color: "#888" }}
        />
        <ReferenceLine y={0} stroke="#333" />

        {/* DIF Line */}
        <Line type="monotone" dataKey="dif" stroke="#58a6ff" dot={false} strokeWidth={1} />

        {/* DEA Line */}
        <Line type="monotone" dataKey="dea" stroke="#f85149" dot={false} strokeWidth={1} />

        {/* HIST Bar */}
        <Bar dataKey="hist" strokeWidth={1}>
          {chartData.map((entry, idx) => (
            <Cell
              key={idx}
              fill={entry.histPositive ? "#3fb95033" : "#f8514933"}
              stroke={entry.histPositive ? "#3fb950" : "#f85149"}
            />
          ))}
        </Bar>
      </ComposedChart>
    </ResponsiveContainer>
  );
}