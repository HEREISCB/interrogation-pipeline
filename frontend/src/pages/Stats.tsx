import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import StatsBar from "@/components/StatsBar";

export default function Stats() {
  const cost = useQuery({ queryKey: ["stats-cost"], queryFn: api.statsCost });
  const channels = useQuery({
    queryKey: ["stats-channels"],
    queryFn: () => api.channels(),
  });

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Stats</h1>
      <StatsBar />

      <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-2">
        Anthropic spend (Haiku scans)
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <CostCard label="Today" value={cost.data?.anthropic_today_usd} />
        <CostCard label="Last 7 days" value={cost.data?.anthropic_week_usd} />
        <CostCard label="Last 30 days" value={cost.data?.anthropic_month_usd} />
        <CostCard label="Lifetime" value={cost.data?.anthropic_lifetime_usd} />
      </div>
      <div className="text-xs text-soft mb-6">
        Includes scan cost only. Tavily verify (~$0.005/case) + Haiku verify
        (~$0.005/case) are not yet rolled in.
        Total scans: <strong>{cost.data?.scans_total ?? 0}</strong> ·
        Tokens in/out:{" "}
        <strong>
          {(cost.data?.input_tokens_total ?? 0).toLocaleString()} /{" "}
          {(cost.data?.output_tokens_total ?? 0).toLocaleString()}
        </strong>
      </div>

      <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-2">
        Per-channel coverage (P4)
      </h2>
      <div className="border border-line rounded-lg overflow-hidden bg-white">
        <table className="w-full text-sm">
          <thead className="bg-bg-soft text-soft uppercase text-xs">
            <tr>
              <th className="text-left px-3 py-2">Channel</th>
              <th className="text-right px-3 py-2">YT total</th>
              <th className="text-left px-3 py-2">Last seen</th>
            </tr>
          </thead>
          <tbody>
            {(channels.data ?? [])
              .filter((c) => c.pipeline === "P4")
              .map((c) => (
                <tr key={c.id} className="border-t border-line">
                  <td className="px-3 py-2 font-mono text-xs">
                    {c.display_name || c.id}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {c.youtube_total_count ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-soft">
                    {c.last_seen_iso ?? "never"}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CostCard({ label, value }: { label: string; value?: number }) {
  return (
    <div className="border border-line rounded-lg px-4 py-3 bg-white">
      <div className="text-xs text-soft uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold text-accent">
        ${(value ?? 0).toFixed(4)}
      </div>
    </div>
  );
}
