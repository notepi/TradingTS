"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  ReferenceLine,
} from "recharts";
import type { StockMarketData } from "@/lib/types";

interface StockRSIChartProps {
  data: StockMarketData[];
}

export function StockRSIChart({ data }: StockRSIChartProps) {
  const chartData = data.map((item) => ({
    date: item.trade_date.slice(5),
    rsi6: item.rsi6 ?? 50,
    rsi14: item.rsi14 ?? 50,
  }));

  return (
    <ResponsiveContainer width="100%" height={150}>
      <LineChart data={chartData}>
        <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#888" }} axisLine={{ stroke: "#333" }} tickLine={false} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#888" }} orientation="right" tickLine={false} axisLine={false} />
        <Tooltip
          contentStyle={{ background: "#1a1d21", border: "1px solid #333" }}
          labelStyle={{ color: "#888" }}
        />

        {/* Reference Lines */}
        <ReferenceLine y={70} stroke="#f85149" strokeDasharray="3 3" />
        <ReferenceLine y={30} stroke="#3fb950" strokeDasharray="3 3" />
        <ReferenceLine y={50} stroke="#333" />

        {/* RSI6 */}
        <Line type="monotone" dataKey="rsi6" stroke="#d29922" dot={false} strokeWidth={1} />

        {/* RSI14 */}
        <Line type="monotone" dataKey="rsi14" stroke="#58a6ff" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}