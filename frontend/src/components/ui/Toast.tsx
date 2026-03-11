import { cn } from "@/utils/cn";
import { CheckCircle, XCircle, Info, X } from "lucide-react";

interface ToastProps {
  message: string;
  type: "success" | "error" | "info";
  onDismiss: () => void;
}

const iconMap = {
  success: CheckCircle,
  error: XCircle,
  info: Info,
};

const colorMap = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  error: "border-red-200 bg-red-50 text-red-800",
  info: "border-blue-200 bg-blue-50 text-blue-800",
};

export function Toast({ message, type, onDismiss }: ToastProps) {
  const Icon = iconMap[type];

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-lg border px-4 py-3 shadow-lg animate-in slide-in-from-top-2",
        colorMap[type]
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="text-sm font-medium">{message}</span>
      <button onClick={onDismiss} className="ml-2 shrink-0 opacity-60 hover:opacity-100">
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
