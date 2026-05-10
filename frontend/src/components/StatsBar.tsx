import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export default function StatsBar() {
  const { data } = useQuery({ queryKey: ["stats-p4"], queryFn: api.statsP4 });
  if (!data) return <div className="h-20" />;

  const cells: { label: string; value: number; pct?: string; tone?: string }[] = [
    { label: "YouTube total (P4)", value: data.youtube_total },
    {
      label: "In our system",
      value: data.in_system,
      pct: pct(data.in_system, data.youtube_total),
    },
    {
      label: "Captioned & scanned",
      value: data.scanned,
      pct: pct(data.scanned, data.youtube_total),
    },
    {
      label: "Accepted (homicide)",
      value: data.accepted,
      pct: pct(data.accepted, data.scanned),
      tone: "good",
    },
    {
      label: "Pushed to Trello",
      value: data.pushed_to_trello,
      tone: "accent",
    },
    {
      label: "Failed / stuck",
      value: data.failed_stuck,
      tone: data.failed_stuck > 0 ? "warn" : undefined,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
      {cells.map((c) => (
        <div
          key={c.label}
          className="border border-line rounded-lg px-4 py-3 bg-white"
        >
          <div className="text-xs text-soft uppercase tracking-wide">{c.label}</div>
          <div
            className={
              "text-2xl font-semibold " +
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
  );
}

function pct(num: number, denom: number): string | undefined {
  if (!denom) return undefined;
  return `${Math.round((num / denom) * 100)}%`;
}
