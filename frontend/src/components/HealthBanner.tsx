import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export default function HealthBanner() {
  const health = useQuery({
    queryKey: ["system-health"],
    queryFn: api.systemHealth,
    refetchInterval: 60_000,
  });

  if (!health.data) return null;
  const { missing_keys, stale_cookies } = health.data;

  if (missing_keys.length === 0 && stale_cookies.length === 0) return null;

  return (
    <div>
      {missing_keys.length > 0 && (
        <div className="bg-amber-50 border-b border-amber-200 text-amber-900 text-sm px-5 py-2">
          <div className="max-w-6xl mx-auto">
            <strong>Setup needed:</strong> missing API keys —{" "}
            <span className="font-mono">{missing_keys.join(", ")}</span>. Add
            them to <code className="mx-1 px-1 bg-amber-100 rounded">backend/.env</code>
            and restart.
          </div>
        </div>
      )}
      {stale_cookies.length > 0 && (
        <div className="bg-red-50 border-b border-red-200 text-red-900 text-sm px-5 py-2">
          <div className="max-w-6xl mx-auto">
            <strong>Cookies expired:</strong>{" "}
            <span className="font-mono">{stale_cookies.join(", ")}</span> — YouTube
            keeps returning auth-required errors. Re-export the file(s) from a
            logged-in Chrome tab using "Get cookies.txt LOCALLY", then drop the
            new file into <code className="mx-1 px-1 bg-red-100 rounded">backend/data/cookies/</code>.
          </div>
        </div>
      )}
    </div>
  );
}
