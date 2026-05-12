import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { SettingsResponse } from "@/api/types";

export default function Settings() {
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const keys = useQuery({ queryKey: ["api-keys"], queryFn: api.apiKeyStatus });

  const [draft, setDraft] = useState<Partial<SettingsResponse>>({});

  useEffect(() => {
    if (settings.data) setDraft(settings.data);
  }, [settings.data]);

  const save = useMutation({
    mutationFn: (body: Partial<SettingsResponse>) => api.patchSettings(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  if (!settings.data) return null;

  const Field = ({
    name,
    label,
    type = "text",
    placeholder,
  }: {
    name: keyof SettingsResponse;
    label: string;
    type?: string;
    placeholder?: string;
  }) => (
    <div className="grid grid-cols-3 gap-3 items-center mb-3">
      <label className="text-sm text-soft text-right">{label}</label>
      <input
        type={type}
        value={String((draft[name] ?? "") as string | number)}
        onChange={(e) =>
          setDraft((d) => ({
            ...d,
            [name]: type === "number" ? Number(e.target.value) : e.target.value,
          }))
        }
        placeholder={placeholder}
        className="col-span-2 border border-line rounded-md px-3 py-1.5 text-sm bg-white"
      />
    </div>
  );

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold mb-4">Settings</h1>

      <section className="mb-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-3">
          Schedule
        </h2>
        <Field name="schedule_cron" label="Cron expression" placeholder="0 20 * * *" />
        <Field name="lookback_hours" label="Lookback hours" type="number" />
      </section>

      <section className="mb-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-3">
          Concurrency &amp; discover limits
        </h2>
        <Field name="scrape_concurrency" label="Scrape (yt-dlp)" type="number" />
        <Field name="scan_concurrency" label="Scan (Haiku)" type="number" />
        <Field name="verify_concurrency" label="Verify (Tavily)" type="number" />
        <Field name="video_max_attempts" label="Max retries per video" type="number" />
        <Field name="discover_per_channel_limit" label="Videos per channel" type="number" />
        <Field name="proxy_blacklist_minutes" label="Proxy blacklist (min)" type="number" />
      </section>

      <section className="mb-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-3">
          Proxy mode
        </h2>
        <div className="grid grid-cols-3 gap-3 items-center mb-3">
          <label className="text-sm text-soft text-right">Mode</label>
          <select
            value={String(draft.proxy_mode ?? "auto")}
            onChange={(e) => setDraft((d) => ({ ...d, proxy_mode: e.target.value as "auto" | "always" | "never" }))}
            className="col-span-2 border border-line rounded-md px-3 py-1.5 text-sm bg-white"
          >
            <option value="auto">Auto — try direct first, fall back to proxy on YT errors</option>
            <option value="always">Always — every yt-dlp call uses a proxy</option>
            <option value="never">Never — direct only, no proxy</option>
          </select>
        </div>
        <Field name="proxy_retry_direct_minutes" label="Retry direct after (min)" type="number" />
        <Field name="proxy_max_failures" label="Disable proxy after N fails" type="number" />
        <div className="text-xs text-soft mt-2 mb-2">
          Edit the proxy pool itself on the <a href="/settings#proxies" className="text-accent hover:underline">Proxy pool</a> section below.
        </div>
      </section>

      <section className="mb-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-3">
          Trello
        </h2>
        <Field name="old_board_id" label="Old (main) board ID" />
        <Field name="new_board_id" label="New (triage) board ID" />
        <Field name="new_list_id" label="New list ID" />
      </section>

      <section className="mb-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-3">
          Display
        </h2>
        <Field name="display_timezone" label="Timezone" placeholder="Asia/Kolkata" />
      </section>

      <section className="mb-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-3">
          FOIA banned states / agencies
        </h2>
        <ListField
          label="Banned states"
          help="Comma-separated 2-letter state codes (CA, AR, etc.). Cases from these states get a yellow badge — they're NOT skipped."
          value={(draft.banned_states as string[] | undefined) ?? []}
          onChange={(v) => setDraft((d) => ({ ...d, banned_states: v }))}
        />
        <ListField
          label="Banned agencies"
          help="Comma-separated agency names. Substring match against the case's arresting_agency."
          value={(draft.banned_agencies as string[] | undefined) ?? []}
          onChange={(v) => setDraft((d) => ({ ...d, banned_agencies: v }))}
        />
      </section>

      <button
        onClick={() => save.mutate(draft)}
        disabled={save.isPending}
        className="bg-accent text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
      >
        {save.isPending ? "Saving…" : "Save"}
      </button>
      {save.isSuccess && (
        <span className="ml-3 text-good text-sm">Saved.</span>
      )}
      {save.isError && (
        <span className="ml-3 text-bad text-sm">{String(save.error)}</span>
      )}

      <hr className="my-8 border-line" />

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-3">
          API key status
        </h2>
        <div className="grid gap-1 text-sm">
          {keys.data &&
            (Object.entries(keys.data) as [string, "configured" | "missing"][]).map(
              ([name, status]) => (
                <div key={name} className="flex items-center justify-between">
                  <span className="font-medium capitalize">{name}</span>
                  <span
                    className={
                      status === "configured" ? "text-good" : "text-warn"
                    }
                  >
                    {status}
                  </span>
                </div>
              )
            )}
        </div>
        <div className="text-xs text-soft mt-3">
          Edit the <code>backend/.env</code> file and restart the server to
          change keys. Keys are never shown in the UI.
        </div>
      </section>
    </div>
  );
}

function ListField({
  label,
  value,
  onChange,
  help,
}: {
  label: string;
  value: string[];
  onChange: (v: string[]) => void;
  help?: string;
}) {
  const [text, setText] = useState(value.join(", "));
  useEffect(() => {
    setText(value.join(", "));
  }, [value.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="grid grid-cols-3 gap-3 items-start mb-3">
      <label className="text-sm text-soft text-right pt-1">{label}</label>
      <div className="col-span-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={() =>
            onChange(
              text
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean)
            )
          }
          className="w-full border border-line rounded-md px-3 py-1.5 text-sm bg-white"
        />
        {help && <div className="text-xs text-soft mt-1">{help}</div>}
      </div>
    </div>
  );
}
