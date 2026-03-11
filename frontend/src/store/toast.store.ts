import { create } from "zustand";

interface ToastItem {
  id: number;
  message: string;
  type: "success" | "error" | "info";
}

interface ToastState {
  toasts: ToastItem[];
  showToast: (message: string, type?: ToastItem["type"], duration?: number) => void;
  dismissToast: (id: number) => void;
}

let toastId = 0;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  showToast: (message, type = "success", duration = 2000) => {
    const id = ++toastId;
    set((state) => ({ toasts: [...state.toasts, { id, message, type }] }));
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    }, duration);
  },
  dismissToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));
