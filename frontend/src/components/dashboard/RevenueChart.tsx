import { useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { GmvProduct } from "@/types";
import { cn } from "@/utils/cn";

type Metric = "revenue" | "clicks" | "add_to_cart" | "orders";

interface RevenueChartProps {
  products: GmvProduct[];
}

const metricConfig: Record<Metric, { label: string; color: string }> = {
  revenue: { label: "GMV", color: "#3b82f6" },
  clicks: { label: "Clicks", color: "#8b5cf6" },
  add_to_cart: { label: "ATC", color: "#f59e0b" },
  orders: { label: "Orders", color: "#10b981" },
};

export function RevenueChart({ products }: RevenueChartProps) {
  const [metric, setMetric] = useState<Metric>("revenue");

  const chartData = useMemo(() => {
    return [...products]
      .sort((a, b) => (b[metric] as number) - (a[metric] as number))
      .slice(0, 10)
      .map((p) => ({
        name: p.item_name.length > 20 ? p.item_name.slice(0, 20) + "..." : p.item_name,
        value: p[metric],
      }));
  }, [products, metric]);

  const formatValue = (value: number) => {
    if (metric === "revenue") {
      if (value >= 1e9) return (value / 1e9).toFixed(1) + "B";
      if (value >= 1e6) return (value / 1e6).toFixed(1) + "M";
      if (value >= 1e3) return (value / 1e3).toFixed(0) + "K";
    }
    return value.toLocaleString();
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-800">Top 10 Sản phẩm</h3>
        <div className="flex gap-1 rounded-lg bg-slate-100 p-0.5">
          {(Object.keys(metricConfig) as Metric[]).map((m) => (
            <button
              key={m}
              onClick={() => setMetric(m)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                metric === m
                  ? "bg-white text-slate-800 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              {metricConfig[m].label}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 80, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis type="number" tickFormatter={formatValue} tick={{ fontSize: 11 }} />
          <YAxis
            type="category"
            dataKey="name"
            width={80}
            tick={{ fontSize: 11 }}
          />
          <Tooltip
            formatter={(value) => [formatValue(Number(value)), metricConfig[metric].label]}
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid #e2e8f0",
              fontSize: "12px",
            }}
          />
          <Bar dataKey="value" fill={metricConfig[metric].color} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
