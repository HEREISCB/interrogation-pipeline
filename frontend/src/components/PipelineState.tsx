// Plain-language explainer of where every video currently is in the
// pipeline. Solves the "534 in our system but the page is empty —
// where ARE they?" UX hole.
//
// Reads the same /api/stats/p4 endpoint as StatsBar; we don't fetch
// twice because react-query dedupes by queryKey.

import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

interface PipelineStateProps {
  /** Cases visible in the "from this run" section on the Today page.
   * Helps phrase the "nothing in the cases list because…" message. */
  visibleCasesCount: number;
  /** True while the latest run is in flight — suppresses the "Run now"
   * suggestion since one is already running. */
  isRunning: boolean;
}

export default function PipelineState({ visibleCasesCount, isRunning }: PipelineStateProps) {
  const { data } = useQuery({
    queryKey: ["stats-p4"],
    queryFn: api.statsP4,
    refetchInterval: 10_000,
  });
  if (!data) return null;

  const captionsReady = Math.max(0, data.captioned - data.scanned);
  const archived = Math.max(0, data.in_system - data.captioned - data.failed_stuck);

  // Compute the most useful single explanation given the current state.
  const explanation = pickExplanation({
    in_system: data.in_system,
    captionsReady,
    scanned: data.scanned,
    accepted: data.accepted,
    archived,
    failed: data.failed_stuck,
    visibleCasesCount,
    isRunning,
  });

  if (!explanation) return null;

  return (
    <div className="mb-6 border border-line rounded-lg bg-bg-soft p-4">
      <div className="flex items-baseline gap-2 mb-3 flex-wrap">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-soft">
          Pipeline state
        </h2>
        <span className="text-xs text-soft">
          where the {data.in_system.toLocaleString()} discovered videos are right now
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-3">
        <Step label="Discovered" value={data.in_system} tone="ink" />
        <Step
          label="Captions ready to scan"
          value={captionsReady}
          tone={captionsReady > 0 ? "accent" : "ink"}
        />
        <Step
          label="Scanned"
          value={data.scanned}
          tone={data.scanned > 0 ? "good" : "ink"}
        />
        <Step
          label="Flagged homicide"
          value={data.accepted}
          tone={data.accepted > 0 ? "good" : "ink"}
        />
        <Step
          label="Archived / failed"
          value={archived + data.failed_stuck}
          tone={data.failed_stuck > 0 ? "warn" : "ink"}
        />
      </div>

      <div className="text-sm text-ink bg-white border border-line rounded-md px-3 py-2">
        {explanation}
      </div>
    </div>
  );
}

function Step({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "ink" | "accent" | "good" | "warn";
}) {
  const toneClass =
    tone === "good"
      ? "text-good"
      : tone === "warn"
      ? "text-warn"
      : tone === "accent"
      ? "text-accent"
      : "text-ink";
  return (
    <div className="border border-line rounded-md bg-white px-3 py-2">
      <div className="text-[10px] text-soft uppercase tracking-wide leading-tight">
        {label}
      </div>
      <div className={`text-xl font-semibold ${toneClass}`}>
        {value.toLocaleString()}
      </div>
    </div>
  );
}

interface ExplainArgs {
  in_system: number;
  captionsReady: number;
  scanned: number;
  accepted: number;
  archived: number;
  failed: number;
  visibleCasesCount: number;
  isRunning: boolean;
}

function pickExplanation(s: ExplainArgs): React.ReactNode | null {
  if (s.in_system === 0) {
    return (
      <>
        No videos discovered yet. Pick a pipeline (top-right) and click{" "}
        <strong>Run now</strong> to start.
      </>
    );
  }

  if (s.isRunning) {
    return (
      <>
        A run is in progress — counts update live. Cases will appear below as
        the scan + verify phases complete.
      </>
    );
  }

  // After a wipe + before re-scan: lots of captions, no scans, no cases.
  if (s.captionsReady > 0 && s.scanned === 0 && s.accepted === 0) {
    return (
      <>
        <strong>{s.captionsReady.toLocaleString()} captions are downloaded
        and waiting to be scanned.</strong> They sit on disk
        (<code>backend/data/transcripts/</code>) until the next run
        processes them. Click <strong>Run now</strong> to scan them with the
        current prompt — no re-download, just Haiku classification.
      </>
    );
  }

  // Captions waiting alongside some already scanned: partial mid-state.
  if (s.captionsReady > 0 && s.scanned > 0) {
    return (
      <>
        {s.captionsReady.toLocaleString()} captions are still waiting to be
        scanned ({s.scanned.toLocaleString()} already done). Next run will
        finish the rest.
      </>
    );
  }

  // Scanned exists but no accepted cases at all: classifier rejected everything.
  if (s.scanned > 0 && s.accepted === 0) {
    return (
      <>
        All {s.scanned.toLocaleString()} scanned transcripts came back as
        non-homicide. No cases to review.{" "}
        {s.archived + s.failed > 0
          ? `(${s.archived + s.failed} additional videos were archived or failed before scan.)`
          : null}
      </>
    );
  }

  // Cases exist somewhere in DB but none visible on this run's Today view.
  if (s.accepted > 0 && s.visibleCasesCount === 0) {
    return (
      <>
        {s.accepted.toLocaleString()} homicide cases exist in the database
        (all-time). None of them are tagged to this run's "today" view — they
        may have already been pushed to Trello, skipped, or marked reviewed.
        Check the Stats page for the full history.
      </>
    );
  }

  // Everything looks healthy.
  return null;
}
