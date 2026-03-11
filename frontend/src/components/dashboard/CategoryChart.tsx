import { useMemo } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import type { GmvProduct } from "@/types";

interface CategoryChartProps {
  products: GmvProduct[];
}

const COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
];

export function CategoryChart({ products }: CategoryChartProps) {
  const chartData = useMemo(() => {
    const categoryMap = new Map<string, number>();
    products.forEach((p) => {
      const cat = p.cluster || "Khác";
      categoryMap.set(cat, (categoryMap.get(cat) || 0) + p.revenue);
    });

    return Array.from(categoryMap.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10);
  }, [products]);

  const formatValue = (value: number) => {
    if (value >= 1e9) return (value / 1e9).toFixed(1) + "B đ";
    if (value >= 1e6) return (value / 1e6).toFixed(1) + "M đ";
    if (value >= 1e3) return (value / 1e3).toFixed(0) + "K đ";
    return value.toLocaleString() + " đ";
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-4 text-sm font-semibold text-slate-800">Phân loại danh mục</h3>

      <ResponsiveContainer width="100%" height={250}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={90}
            paddingAngle={2}
            dataKey="value"
          >
            {chartData.map((_, index) => (
              <Cell key={index} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value) => formatValue(Number(value))}
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid #e2e8f0",
              fontSize: "12px",
            }}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="mt-2 flex flex-wrap gap-2">
        {chartData.slice(0, 5).map((item, index) => (
          <div key={item.name} className="flex items-center gap-1.5 text-xs text-slate-600">
            <div
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: COLORS[index % COLORS.length] }}
            />
            <span className="truncate max-w-[100px]">{item.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
