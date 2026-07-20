export interface ApiMeta {
  page?: number;
  pageSize?: number;
  total?: number;
  requestId: string;
  correlationId?: string;
}
export interface ApiSuccess<T> {
  success: true;
  data: T;
  meta: ApiMeta;
}
export interface ApiFailure {
  success: false;
  error: { code: string; message: string; details?: Record<string, string[]> };
  meta: ApiMeta;
}
export type ApiResponse<T> = ApiSuccess<T> | ApiFailure;
export interface Paginated<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}
export interface ApiErrorShape {
  status: number;
  code: string;
  message: string;
  details?: Record<string, string[]>;
  requestId?: string;
}
export interface Metric {
  label: string;
  value: string;
  change: string;
}
export interface ActivityRow {
  title: string;
  detail: string;
  status: string;
  date?: string;
  amount?: string;
}
export interface ChartPoint {
  day: string;
  tokens: number;
  posts: number;
}
export interface ProductView {
  title: string;
  eyebrow: string;
  description: string;
  action: string;
  metrics?: Metric[];
  rows?: ActivityRow[];
  chart?: ChartPoint[];
}
