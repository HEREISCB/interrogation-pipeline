// Shared shapes mirroring the FastAPI response models.

export interface CaseRow {
  id: number;
  defendant: string | null;
  victim: string | null;
  charges: string | null;
  location: string | null;
  state: string | null;
  year: number | null;
  verdict: string | null;
  status: string;
  dedup_status: "unique" | "exists_old" | "exists_new" | null;
  trello_card_id: string | null;
  matched_trello_card_id: string | null;
  verification_status: string | null;
  banned_state: boolean;
  banned_agency: boolean;
  articles: { url: string; title?: string; snippet?: string }[];
  created_at: string;
}

export interface TodayResponse {
  run_id: number | null;
  date_iso: string | null;
  counts: Record<string, number>;
  accepted: CaseRow[];
  rejected: CaseRow[];
  duplicate_old: CaseRow[];
  duplicate_new: CaseRow[];
}

export interface DayCount {
  date_iso: string;
  counts: {
    discovered: number;
    accepted: number;
    rejected: number;
    pushed: number;
    failed: number;
  };
}

export interface Channel {
  id: string;
  display_name: string | null;
  pipeline: string;
  rss_url: string;
  since_iso: string | null;
  last_seen_iso: string | null;
  cookies_path: string;
  youtube_total_count: number | null;
  youtube_total_synced_at: string | null;
  active: boolean;
}

export interface Run {
  id: number;
  trigger: string;
  started_at: string;
  completed_at: string | null;
  status: "running" | "success" | "partial" | "failed";
  phase: string | null;
  counts: Record<string, number>;
  error: string | null;
}

export interface RunEvent {
  id: number;
  ts: string;
  phase: string;
  level: "info" | "warn" | "error";
  video_id: string | null;
  message: string;
}

export interface SettingsResponse {
  schedule_cron: string;
  lookback_hours: number;
  scrape_concurrency: number;
  scan_concurrency: number;
  verify_concurrency: number;
  video_max_attempts: number;
  discover_per_channel_limit: number;
  proxy_blacklist_minutes: number;
  proxy_mode: "auto" | "always" | "never";
  proxy_retry_direct_minutes: number;
  proxy_max_failures: number;
  cookie_stale_threshold: number;
  old_board_id: string;
  old_board_name: string;
  new_board_id: string;
  new_board_name: string;
  new_list_id: string;
  new_list_name: string;
  prompt_version: string;
  weekly_reconcile_dow: number;
  display_timezone: string;
  banned_states: string[];
  banned_agencies: string[];
}

export interface ApiKeyStatus {
  anthropic: "configured" | "missing";
  tavily: "configured" | "missing";
  trello: "configured" | "missing";
  webshare: "configured" | "missing";
}

export interface P4Stats {
  youtube_total: number;
  in_system: number;
  captioned: number;
  scanned: number;
  accepted: number;
  pushed_to_trello: number;
  failed_stuck: number;
}

export interface CostStats {
  anthropic_today_usd: number;
  anthropic_week_usd: number;
  anthropic_month_usd: number;
  anthropic_lifetime_usd: number;
  scans_total: number;
  input_tokens_total: number;
  output_tokens_total: number;
}
