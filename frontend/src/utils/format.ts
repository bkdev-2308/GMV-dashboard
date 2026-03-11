/**
 * Format a number as Vietnamese currency (đ).
 * Uses B (tỷ), M (triệu), K (nghìn) suffixes for readability.
 */
export function formatCurrency(value: number): string {
  if (value == null || isNaN(value)) return "0đ";

  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";

  if (abs >= 1_000_000_000) {
    return `${sign}${(abs / 1_000_000_000).toFixed(2)}B đ`;
  }
  if (abs >= 1_000_000) {
    return `${sign}${(abs / 1_000_000).toFixed(2)}M đ`;
  }
  if (abs >= 1_000) {
    return `${sign}${(abs / 1_000).toFixed(1)}K đ`;
  }
  return `${sign}${abs.toLocaleString("vi-VN")}đ`;
}

/**
 * Format a number with comma separators.
 */
export function formatNumber(value: number): string {
  if (value == null || isNaN(value)) return "0";
  return value.toLocaleString("vi-VN");
}

/**
 * Format a date string or Date object as a Vietnamese locale date.
 * Example output: "11/03/2026"
 */
export function formatDate(date: string | Date): string {
  if (!date) return "";
  const d = typeof date === "string" ? new Date(date) : date;
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/**
 * Format a date string or Date object as a Vietnamese locale datetime.
 * Example output: "11/03/2026 14:30"
 */
export function formatDateTime(date: string | Date): string {
  if (!date) return "";
  const d = typeof date === "string" ? new Date(date) : date;
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}
