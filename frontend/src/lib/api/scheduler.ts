import { request } from "./client";
import type { CreateScheduleRequest, ProductView, Schedule } from "@/types";
export const getSchedules = () =>
  request<{ view: ProductView; items: Schedule[] }>({ url: "/scheduler", method: "GET" });
export const createSchedule = (data: CreateScheduleRequest) =>
  request<Schedule>({ url: "/scheduler", method: "POST", data });
