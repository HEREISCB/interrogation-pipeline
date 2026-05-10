import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import StatsBar from "@/components/StatsBar";
import CaseCard from "@/components/CaseCard";
import RejectedRow from "@/components/RejectedRow";
import { formatLocal } from "@/lib/format";
import { useRunStream } from "@/lib/useRunStream";

const PIPELINES = ["P4", "P1", "P3", "P2", "ALL"];

export default function Today() {
  const qc = useQueryClient();
  const today = useQuery({ queryKey: ["today"], queryFn: api.today });
  const [rejectedOpen, setRejectedOpen] = useState(false);
  const [dupOldOpen, setDupOldOpen] = useState(false);
  const [pipeline, setPipeline] = useState("P4");
  const [streaming, setStreaming] = useState(false);

  const trigger = useMutation({
    mutationFn: () => api.triggerRun(pipeline),
    onSuccess: () => {
      setStreaming(true);
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  const stream = useRunStream(streaming);
  // Refetch the Today snapshot whenever the run finishes a phase.
  useEffect(() => {
    if (stream.payload) {
      qc.invalidateQueries({ queryKey: ["today"] });
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["stats-p4"] });
      if (stream.payload.status !== "running") setStreaming(false);
    }
  }, [stream.payload, qc]);

  const t = today.data;
  const accepted = t?.accepted ?? [];
  const rejected = t?.rejected ?? [];
  const dupOld = t?.duplicate_old ?? [];
  const dupNew = t?.duplicate_new ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">Today</h1>
          <div className="text-sm text-soft">
            {t?.run_id
              ? `Run #${t.run_id} — ${formatLocal(t.date_iso)}`
              : "No runs yet — pick a pipeline and click Run now."}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={pipeline}
            onChange={(e) => setPipeline(e.target.value)}
            className="border border-line rounded-md px-2 py-1.5 text-sm bg-white"
            title="Which pipeline to run"
          >
            {PIPELINES.map((p) => (
              <option key={p} value={p}>
                {p === "ALL" ? "All pipelines" : p}
              </option>
            ))}
          </select>
          <button
            disabled={trigger.isPending || streaming}
            onClick={() => trigger.mutate()}
            className="bg-ink text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-black disabled:opacity-50"
          >
            {streaming ? "Running…" : trigger.isPending ? "Triggering…" : "Run now"}
          </button>
        </div>
      </div>

      {streaming && stream.payload && (
        <div className="mb-4 text-sm border border-blue-200 bg-blue-50 text-blue-900 rounded-md px-3 py-2 flex items-center gap-3">
          <span className="inline-block w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
          <strong>Run #{stream.payload.run_id}</strong>
          <span className="text-soft">phase: {stream.payload.phase || "—"}</span>
          {Object.keys(stream.payload.counts).length > 0 && (
            <span className="text-xs font-mono text-soft">
              {Object.entries(stream.payload.counts)
                .map(([k, v]) => `${k}:${v}`)
                .join(" · ")}
            </span>
          )}
        </div>
      )}

      {trigger.isError && (
        <div className="mb-4 text-sm border border-bad bg-red-50 text-bad rounded-md px-3 py-2">
          Trigger failed: {String(trigger.error)}
        </div>
      )}

      <StatsBar />

      {/* Accepted */}
      <section className="mb-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-2">
          Accepted ({accepted.length})
        </h2>
        {accepted.length === 0 ? (
          <div className="border border-dashed border-line rounded-lg p-8 text-center text-soft text-sm">
            No accepted cases yet. Once a daily run completes,
            confirmed-homicide cases appear here for review.
          </div>
        ) : (
          <div className="grid gap-3">
            {accepted.map((c) => (
              <CaseCard key={c.id} c={c} />
            ))}
          </div>
        )}
      </section>

      {/* Duplicate against new triage board */}
      {dupNew.length > 0 && (
        <section className="mb-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-2">
            Already on triage board ({dupNew.length})
          </h2>
          <div className="grid gap-3 opacity-75">
            {dupNew.map((c) => (
              <CaseCard key={c.id} c={c} />
            ))}
          </div>
        </section>
      )}

      {/* Duplicate against main board (collapsed) */}
      {dupOld.length > 0 && (
        <section className="mb-6">
          <button
            onClick={() => setDupOldOpen((v) => !v)}
            className="w-full text-left flex items-center justify-between border border-line rounded-md px-3 py-2 hover:bg-bg-soft text-sm"
          >
            <span className="font-semibold uppercase tracking-wide text-soft">
              {dupOldOpen ? "▼" : "▶"} Already on main board ({dupOld.length})
            </span>
            <span className="text-xs text-soft">click to expand</span>
          </button>
          {dupOldOpen && (
            <div className="grid gap-3 mt-3 opacity-75">
              {dupOld.map((c) => (
                <CaseCard key={c.id} c={c} />
              ))}
            </div>
          )}
        </section>
      )}

      {/* Rejected (collapsed) */}
      <section className="mb-6">
        <button
          onClick={() => setRejectedOpen((v) => !v)}
          className="w-full text-left flex items-center justify-between border border-line rounded-md px-3 py-2 hover:bg-bg-soft text-sm"
        >
          <span className="font-semibold uppercase tracking-wide text-soft">
            {rejectedOpen ? "▼" : "▶"} Rejected by AI ({rejected.length})
          </span>
          <span className="text-xs text-soft">peace-of-mind check</span>
        </button>
        {rejectedOpen && (
          <div className="grid gap-2 mt-3">
            {rejected.length === 0 ? (
              <div className="text-soft text-sm px-3">Nothing rejected today.</div>
            ) : (
              rejected.map((c) => <RejectedRow key={c.id} c={c} />)
            )}
          </div>
        )}
      </section>

      {today.isError && (
        <div className="text-sm text-bad">
          Failed to load today: {String(today.error)}
        </div>
      )}
    </div>
  );
}
