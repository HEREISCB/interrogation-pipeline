import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { formatRelative } from "@/lib/format";

const PATH_HELP = (
  <div className="text-xs text-soft mb-4">
    Cookie files live under <code>backend/data/cookies/</code>. Two layouts work
    (you can use either or both):
    <ul className="list-disc pl-6 mt-1">
      <li>
        <strong>Pooled mode</strong> —{" "}
        <code>backend/data/cookies/p4/account_a.txt</code>,{" "}
        <code>account_b.txt</code>, etc. The scraper picks one healthy file at random
        per video. Drop multiple files from different YouTube accounts to spread load.
      </li>
      <li>
        <strong>Single-file mode</strong> —{" "}
        <code>backend/data/cookies/cookies_p4.txt</code>. Still works for backward
        compatibility.
      </li>
    </ul>
    A file is marked <strong>stale</strong> after ~5 consecutive YouTube auth
    failures. The dashboard banner alerts you; the scraper deprioritizes stale
    files but keeps trying until you replace them.
  </div>
);

export default function Cookies() {
  const list = useQuery({ queryKey: ["cookies"], queryFn: api.listCookies });
  const files = list.data ?? [];

  const byPipeline = new Map<string, typeof files>();
  for (const f of files) {
    if (!byPipeline.has(f.pipeline)) byPipeline.set(f.pipeline, []);
    byPipeline.get(f.pipeline)!.push(f);
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Cookies</h1>
      {PATH_HELP}

      {files.length === 0 ? (
        <div className="border border-dashed border-line rounded-lg p-8 text-center text-soft text-sm">
          No cookie files found. Drop YT-exported cookie .txt files into{" "}
          <code>backend/data/cookies/p4/</code> (or the legacy{" "}
          <code>cookies_p4.txt</code> path) and refresh.
        </div>
      ) : (
        [...byPipeline.entries()].map(([pipeline, list]) => (
          <section key={pipeline} className="mb-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-soft mb-2">
              {pipeline} pipeline ({list.length} file{list.length === 1 ? "" : "s"})
            </h2>
            <div className="border border-line rounded-lg overflow-hidden bg-white">
              <table className="w-full text-sm">
                <thead className="bg-bg-soft text-soft uppercase text-xs">
                  <tr>
                    <th className="text-left px-3 py-2">File</th>
                    <th className="text-left px-3 py-2">Health</th>
                    <th className="text-right px-3 py-2">Consecutive auth fails</th>
                    <th className="text-left px-3 py-2">Last OK</th>
                    <th className="text-left px-3 py-2">Last failure</th>
                    <th className="text-right px-3 py-2">Size</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((f) => (
                    <tr key={f.path} className="border-t border-line">
                      <td className="px-3 py-2 font-mono text-xs">
                        <div>{f.name}</div>
                        <div className="text-soft">{f.path}</div>
                      </td>
                      <td className="px-3 py-2">
                        {f.stale ? (
                          <span className="text-xs bg-red-100 text-bad px-2 py-0.5 rounded">
                            stale
                          </span>
                        ) : (
                          <span className="text-xs bg-green-100 text-good px-2 py-0.5 rounded">
                            healthy
                          </span>
                        )}
                      </td>
                      <td
                        className={`px-3 py-2 text-right ${
                          f.consecutive_auth_failures >= 3 ? "text-bad" : ""
                        }`}
                      >
                        {f.consecutive_auth_failures}
                      </td>
                      <td className="px-3 py-2 text-soft text-xs">
                        {formatRelative(f.last_ok_at)}
                      </td>
                      <td className="px-3 py-2 text-soft text-xs">
                        {formatRelative(f.last_failure_at)}
                      </td>
                      <td className="px-3 py-2 text-right text-xs text-soft">
                        {(f.size_bytes / 1024).toFixed(1)} KB
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))
      )}
    </div>
  );
}
