import axios from "axios";

export type GatewayStatus =
  | { available: true; health: "healthy"; version: string }
  | { available: false; health: "unavailable"; version: null };

const gatewayOrigin = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080/api/v1").replace(
  /\/api\/v1\/?$/,
  "",
);

export async function getGatewayStatus(): Promise<GatewayStatus> {
  try {
    const [health, version] = await Promise.all([
      axios.get<{ status: "healthy" }>(`${gatewayOrigin}/health`, { timeout: 1500 }),
      axios.get<{ version: string }>(`${gatewayOrigin}/version`, { timeout: 1500 }),
    ]);
    return { available: true, health: health.data.status, version: version.data.version };
  } catch {
    return { available: false, health: "unavailable", version: null };
  }
}
