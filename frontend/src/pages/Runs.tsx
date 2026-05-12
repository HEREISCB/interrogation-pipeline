import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { formatLocal } from "@/lib/format";

export default function Runs() {
  const { data } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.runs(50),
    // Adaptive polling: fast (3s) while anything is running so phase
    // transitions show up live; idle (30s) otherwise to keep traffic low.
    refetchInterval: (query) => {
      const rows = query.state.data ?? [];
      return rows.some((r) => r.status === "running") ? 3_000 : 30_000;
    },
  });
  const rows = data ?? [];

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Runs</h1>
      <div className="border border-line rounded-lg overflow-hidden bg-white">
        <table className="w-full text-sm">
          <thead className="bg-bg-soft text-soft uppercase text-xs">
            <tr>
              <th className="text-left px-3 py-2">#</th>
              <th className="text-left px-3 py-2">Started</th>
              <th className="text-left px-3 py-2">Trigger</th>
              <th className="text-left px-3 py-2">Status</th>
              <th className="text-left px-3 py-2">Phase</th>
              <th className="text-left px-3 py-2">Counts</th>
              <th className="text-left px-3 py-2">Error</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center text-soft py-6">
                  No runs yet.
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-line">
                <td className="px-3 py-2 font-mono text-xs">{r.id}</td>
                <td className="px-3 py-2">{formatLocal(r.started_at)}</td>
                <td className="px-3 py-2 text-xs">{r.trigger}</td>
                <td className="px-3 py-2">
                  <StatusPill status={r.status} />
                </td>
                <td className="px-3 py-2 text-xs text-soft">{r.phase ?? "—"}</td>
                <td className="px-3 py-2 text-xs font-mono">
                  {Object.entries(r.counts ?? {})
                    .map(([k, v]) => `${k}:${v}`)
                    .join(" · ") || "—"}
                </td>
                <td className="px-3 py-2 text-xs text-bad max-w-[20rem] truncate">
                  {r.error ?? ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const tone =
    status === "success"
      ? "bg-green-100 text-good"
      : status === "running"
      ? "bg-blue-100 text-accent"
      : status === "partial"
      ? "bg-amber-100 text-warn"
      : "bg-red-100 text-bad";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${tone}`}>
      {status}
    </span>
  );
}
