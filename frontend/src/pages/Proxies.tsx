import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { formatRelative } from "@/lib/format";

export default function Proxies() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["proxies"], queryFn: () => api.listProxies() });
  const [text, setText] = useState("");
  const [replace, setReplace] = useState(false);

  const importMut = useMutation({
    mutationFn: () => api.importProxies(text, replace),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["proxies"] });
      setText("");
    },
  });

  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      api.toggleProxy(id, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["proxies"] }),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteProxy(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["proxies"] }),
  });

  const items = list.data?.items ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold">Proxy pool</h1>
          <div className="text-sm text-soft">
            {list.data
              ? `${list.data.enabled} of ${list.data.total} enabled`
              : "loading…"}
          </div>
        </div>
      </div>

      <section className="mb-6 border border-line rounded-lg p-4 bg-white">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-2">
          Bulk import
        </h2>
        <p className="text-xs text-soft mb-2">
          Proxies are <strong>optional</strong>. The default proxy mode is{" "}
          <code>auto</code> — the scraper goes direct first and only falls back to
          a proxy if YouTube rate-limits. You only need to fill this pool if you
          want to be ready for that fallback.
        </p>
        <p className="text-xs text-soft mb-2">
          Paste one proxy per line. Accepted formats: <code>host:port:user:pass</code>{" "}
          (Webshare), <code>user:pass@host:port</code>, <code>http://user:pass@host:port</code>.
          Comments (<code>#</code>) and blank lines ignored. Duplicates collapse silently.
        </p>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={10}
          placeholder={"p.webshare.io:80:user-residential-1:abc123\np.webshare.io:80:user-residential-2:abc123\n..."}
          className="w-full border border-line rounded-md px-3 py-2 text-sm font-mono bg-bg-soft mb-2"
        />
        <label className="flex items-center gap-2 text-sm text-soft mb-2">
          <input
            type="checkbox"
            checked={replace}
            onChange={(e) => setReplace(e.target.checked)}
          />
          Replace pool — delete existing proxies first
        </label>
        <button
          onClick={() => importMut.mutate()}
          disabled={!text.trim() || importMut.isPending}
          className="bg-accent text-white px-3 py-1.5 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {importMut.isPending ? "Importing…" : "Import proxies"}
        </button>
        {importMut.isSuccess && importMut.data && (
          <span className="ml-3 text-good text-sm">
            ✓ inserted {importMut.data.inserted}, duplicates {importMut.data.duplicates}
            {importMut.data.rejected_total > 0 &&
              `, rejected ${importMut.data.rejected_total}`}
            {importMut.data.cleared > 0 && `, cleared ${importMut.data.cleared} first`}
          </span>
        )}
        {importMut.isError && (
          <span className="ml-3 text-bad text-sm">{String(importMut.error)}</span>
        )}
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-2">
          Proxies in pool ({items.length} shown)
        </h2>
        <div className="border border-line rounded-lg overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead className="bg-bg-soft text-soft uppercase text-xs">
              <tr>
                <th className="text-left px-3 py-2">Enabled</th>
                <th className="text-left px-3 py-2">Host:Port</th>
                <th className="text-left px-3 py-2">User</th>
                <th className="text-right px-3 py-2">OK</th>
                <th className="text-right px-3 py-2">Fail</th>
                <th className="text-right px-3 py-2">Consec.</th>
                <th className="text-left px-3 py-2">Last ok</th>
                <th className="text-right px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={8} className="text-center text-soft py-6">
                    No proxies yet. Paste lines above and click Import.
                  </td>
                </tr>
              )}
              {items.map((p) => (
                <tr key={p.id} className="border-t border-line">
                  <td className="px-3 py-2">
                    <button
                      onClick={() =>
                        toggle.mutate({ id: p.id, enabled: !p.enabled })
                      }
                      className={`w-10 h-5 rounded-full relative transition-colors ${
                        p.enabled ? "bg-good" : "bg-line"
                      }`}
                      aria-label="toggle enabled"
                    >
                      <span
                        className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${
                          p.enabled ? "right-0.5" : "left-0.5"
                        }`}
                      />
                    </button>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {p.host}:{p.port}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{p.username}</td>
                  <td className="px-3 py-2 text-right">{p.success_count}</td>
                  <td className="px-3 py-2 text-right">{p.failure_count}</td>
                  <td
                    className={`px-3 py-2 text-right ${
                      p.consecutive_failures >= 3 ? "text-bad" : ""
                    }`}
                  >
                    {p.consecutive_failures}
                  </td>
                  <td className="px-3 py-2 text-soft text-xs">
                    {formatRelative(p.last_ok_iso)}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => {
                        if (confirm(`Delete ${p.host}:${p.port} (${p.username})?`))
                          remove.mutate(p.id);
                      }}
                      className="text-bad text-xs hover:underline"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
