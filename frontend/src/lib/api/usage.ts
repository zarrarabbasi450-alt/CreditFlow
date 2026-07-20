import { request } from "./client";
import type { UsageSummary } from "@/types";
export const getUsage = () => request<UsageSummary>({ url: "/usage/summary", method: "GET" });
