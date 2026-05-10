// Tiny typed fetch wrapper. No axios — keeps deps lean.

import type {
  ApiKeyStatus,
  CaseRow,
  Channel,
  CostStats,
  DayCount,
  P4Stats,
  Run,
  RunEvent,
  SettingsResponse,
  TodayResponse,
} from "@/api/types";

const BASE = "/api";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`${r.status} ${r.statusText}: ${text || path}`);
  }
  return (await r.json()) as T;
}

export const api = {
  health: () => jsonFetch<{ status: string; version: string }>("/health"),

  today: () => jsonFetch<TodayResponse>("/today"),
  days: (from: string, to: string) =>
    jsonFetch<DayCount[]>(`/days?from_=${from}&to=${to}`),

  case: (id: number) => jsonFetch<CaseRow>(`/cases/${id}`),
  pushCase: (id: number, list_id?: string) =>
    jsonFetch<{ trello_card_id: string }>(`/cases/${id}/push-to-trello`, {
      method: "POST",
      body: JSON.stringify({ list_id }),
    }),
  skipCase: (id: number) =>
    jsonFetch<{ status: string }>(`/cases/${id}/skip`, { method: "POST" }),
  reviewCase: (id: number) =>
    jsonFetch<{ status: string }>(`/cases/${id}/mark-reviewed`, { method: "POST" }),

  channels: () => jsonFetch<Channel[]>("/channels"),
  addChannel: (body: Partial<Channel>) =>
    jsonFetch<{ id: string; ok: boolean }>("/channels", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  patchChannel: (id: string, body: Partial<Channel>) =>
    jsonFetch<{ ok: string }>(`/channels/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteChannel: (id: string) =>
    jsonFetch<{ ok: string }>(`/channels/${id}`, { method: "DELETE" }),

  runs: (limit = 50) => jsonFetch<Run[]>(`/runs?limit=${limit}`),
  runEvents: (id: number, level?: string) =>
    jsonFetch<RunEvent[]>(`/runs/${id}/events${level ? `?level=${level}` : ""}`),
  triggerRun: (pipeline?: string) =>
    jsonFetch<{ status: string; pipeline: string }>(
      `/runs/trigger${pipeline ? `?pipeline=${encodeURIComponent(pipeline)}` : ""}`,
      { method: "POST" }
    ),
  schedulerInfo: () =>
    jsonFetch<{ running: boolean; jobs: { id: string; next_fire: string | null; trigger: string }[] }>(
      "/runs/scheduler/info"
    ),
  reschedule: (cron: string) =>
    jsonFetch<unknown>("/runs/scheduler/reschedule", {
      method: "POST",
      body: JSON.stringify({ cron }),
    }),

  settings: () => jsonFetch<SettingsResponse>("/settings"),
  patchSettings: (body: Partial<SettingsResponse>) =>
    jsonFetch<SettingsResponse>("/settings", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  apiKeyStatus: () => jsonFetch<ApiKeyStatus>("/settings/api-keys/status"),
  systemHealth: () =>
    jsonFetch<{ missing_keys: string[]; stale_cookies: string[] }>(
      "/settings/health"
    ),

  statsP4: () => jsonFetch<P4Stats>("/stats/p4"),
  statsCost: () => jsonFetch<CostStats>("/stats/cost"),
};
