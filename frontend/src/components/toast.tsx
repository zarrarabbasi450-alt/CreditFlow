"use client";
import { createContext, useContext, useState } from "react";
import { CheckCircle2, X } from "lucide-react";
const Context = createContext<{ notify: (message: string) => void }>({ notify: () => undefined });
export const useToast = () => useContext(Context);
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [message, setMessage] = useState("");
  const notify = (text: string) => {
    setMessage(text);
    setTimeout(() => setMessage(""), 3500);
  };
  return (
    <Context.Provider value={{ notify }}>
      {children}
      {message && (
        <div
          role="status"
          className="fixed right-5 bottom-5 z-50 flex items-center gap-3 rounded-2xl border border-emerald-400/30 bg-slate-950 px-4 py-3 text-sm text-white shadow-2xl"
        >
          <CheckCircle2 className="size-4 text-emerald-400" />
          {message}
          <button aria-label="Dismiss" onClick={() => setMessage("")}>
            <X className="size-4" />
          </button>
        </div>
      )}
    </Context.Provider>
  );
}
