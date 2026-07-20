import { request } from "./client";
import type { ProductView, Publication, PublishRequest, SocialConnection } from "@/types";
export const getPublishing = () =>
  request<{ view: ProductView; connections: SocialConnection[] }>({ url: "/publishing", method: "GET" });
export const publishToLinkedIn = (data: PublishRequest) =>
  request<Publication>({ url: "/publishing/linkedin", method: "POST", data });
