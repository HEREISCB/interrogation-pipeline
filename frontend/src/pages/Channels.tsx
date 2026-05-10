import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { formatRelative } from "@/lib/format";

const PIPELINES = ["P1", "P2", "P3", "P4"];

export default function Channels() {
  const qc = useQueryClient();
  const channels = useQuery({ queryKey: ["channels"], queryFn: api.channels });
  const [adding, setAdding] = useState(false);
  const [newId, setNewId] = useState("");
  const [newPipeline, setNewPipeline] = useState("P4");

  const refresh = () => qc.invalidateQueries({ queryKey: ["channels"] });

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.patchChannel(id, body),
    onSuccess: refresh,
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteChannel(id),
    onSuccess: refresh,
  });

  const add = useMutation({
    mutationFn: () =>
      api.addChannel({
        id: newId.trim(),
        display_name: newId.trim(),
        pipeline: newPipeline,
      }),
    onSuccess: () => {
      setNewId("");
      setAdding(false);
      refresh();
    },
  });

  const rows = channels.data ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Channels</h1>
        <button
          onClick={() => setAdding((v) => !v)}
          className="bg-ink text-white px-3 py-1.5 rounded-md text-sm font-medium hover:bg-black"
        >
          + Add channel
        </button>
      </div>

      {adding && (
        <div className="border border-line rounded-lg p-4 mb-4 bg-bg-soft">
          <div className="flex items-end gap-3 flex-wrap">
            <div className="flex-1 min-w-[14rem]">
              <label className="block text-xs text-soft mb-1">
                YouTube channel — paste @handle or UC… ID
              </label>
              <input
                value={newId}
                onChange={(e) => setNewId(e.target.value)}
                placeholder="@MidwestSafety"
                className="w-full border border-line rounded-md px-3 py-1.5 text-sm bg-white"
              />
            </div>
            <div>
              <label className="block text-xs text-soft mb-1">Pipeline</label>
              <select
                value={newPipeline}
                onChange={(e) => setNewPipeline(e.target.value)}
                className="border border-line rounded-md px-3 py-1.5 text-sm bg-white"
              >
                {PIPELINES.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </div>
            <button
              disabled={!newId.trim() || add.isPending}
              onClick={() => add.mutate()}
              className="bg-accent text-white px-3 py-1.5 rounded-md text-sm font-medium disabled:opacity-50"
            >
              {add.isPending ? "Adding…" : "Add"}
            </button>
            <button
              onClick={() => setAdding(false)}
              className="text-soft px-2 py-1.5 text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="border border-line rounded-lg overflow-hidden bg-white">
        <table className="w-full text-sm">
          <thead className="bg-bg-soft text-soft uppercase text-xs">
            <tr>
              <th className="text-left px-3 py-2">Pipeline</th>
              <th className="text-left px-3 py-2">Active</th>
              <th className="text-left px-3 py-2">Channel</th>
              <th className="text-right px-3 py-2">YT total</th>
              <th className="text-left px-3 py-2">Last seen</th>
              <th className="text-right px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center text-soft py-6">
                  Loading…
                </td>
              </tr>
            )}
            {rows.map((c) => (
              <tr key={c.id} className="border-t border-line">
                <td className="px-3 py-2">
                  <select
                    value={c.pipeline}
                    onChange={(e) =>
                      patch.mutate({ id: c.id, body: { pipeline: e.target.value } })
                    }
                    className="border border-line rounded px-2 py-1 text-xs bg-white"
                  >
                    {PIPELINES.map((p) => (
                      <option key={p}>{p}</option>
                    ))}
                  </select>
                </td>
                <td className="px-3 py-2">
                  <button
                    onClick={() =>
                      patch.mutate({ id: c.id, body: { active: !c.active } })
                    }
                    className={`w-10 h-5 rounded-full relative transition-colors ${
                      c.active ? "bg-good" : "bg-line"
                    }`}
                    aria-label="toggle active"
                  >
                    <span
                      className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${
                        c.active ? "right-0.5" : "left-0.5"
                      }`}
                    />
                  </button>
                </td>
                <td className="px-3 py-2 font-mono text-xs">
                  <div>{c.display_name || c.id}</div>
                  <div className="text-soft">{c.id}</div>
                </td>
                <td className="px-3 py-2 text-right">
                  {c.youtube_total_count ?? "—"}
                </td>
                <td className="px-3 py-2 text-soft">
                  {formatRelative(c.last_seen_iso)}
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    onClick={() => {
                      if (confirm(`Remove ${c.display_name || c.id}?`))
                        remove.mutate(c.id);
                    }}
                    className="text-bad text-xs hover:underline"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
