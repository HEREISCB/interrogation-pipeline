import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export default function StatsBar() {
  const { data } = useQuery({
    queryKey: ["stats-p4"],
    queryFn: api.statsP4,
    // Live counters during runs: cheap query, refresh every 10s so the
    // stat tiles tick up as discover/scan/verify make progress.
    refetchInterval: 10_000,
  });
  if (!data) return <div className="h-20" />;

  const cells: {
    label: string;
    value: number;
    pct?: string;
    tone?: string;
    hint?: string;
  }[] = [
    {
      label: "YouTube uploads — P4 channels",
      value: data.youtube_total,
      hint: "Sum of every video the 13 P4 channels have ever uploaded on YouTube",
    },
    {
      label: "Discovered by us",
      value: data.in_system,
      pct: pct(data.in_system, data.youtube_total),
      hint: "Videos the pipeline has seen across all runs",
    },
    {
      label: "Captions scanned",
      value: data.scanned,
      pct: pct(data.scanned, data.youtube_total),
      hint: "Transcripts run through Haiku at least once",
    },
    {
      label: "Flagged homicide (all-time)",
      value: data.accepted,
      pct: pct(data.accepted, data.scanned),
      tone: "good",
      hint: "Total scans across every run where the classifier said yes — NOT per-day",
    },
    {
      label: "Pushed to Trello",
      value: data.pushed_to_trello,
      tone: "accent",
      hint: "Cases the user clicked Send to Trello on",
    },
    {
      label: "Failed / stuck",
      value: data.failed_stuck,
      tone: data.failed_stuck > 0 ? "warn" : undefined,
      hint: "Videos that errored — see Runs page for details",
    },
  ];

  return (
    <section className="mb-6">
      <div className="mb-2 flex items-baseline gap-2 flex-wrap">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-soft">
          Pipeline totals — all-time
        </h2>
        <span className="text-xs text-soft">
          (every run since first start; for per-day breakdown see Calendar)
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {cells.map((c) => (
          <div
            key={c.label}
            className="border border-line rounded-lg px-4 py-3 bg-white"
            title={c.hint}
          >
            <div className="text-xs text-soft uppercase tracking-wide leading-tight">
              {c.label}
            </div>
            <div
              className={
                "text-2xl font-semibold mt-1 " +
                (c.tone === "good"
                  ? "text-good"
                  : c.tone === "warn"
                  ? "text-warn"
                  : c.tone === "accent"
                  ? "text-accent"
                  : "text-ink")
              }
            >
              {c.value.toLocaleString()}
              {c.pct ? <span className="text-sm text-soft ml-2">{c.pct}</span> : null}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function pct(num: number, denom: number): string | undefined {
  if (!denom) return undefined;
  return `${Math.round((num / denom) * 100)}%`;
}
