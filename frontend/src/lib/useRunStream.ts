// Subscribe to /api/runs/current/stream via Server-Sent Events.
// Returns the latest payload + a connect/disconnect indicator.

import { useEffect, useState } from "react";

export interface RunStreamPayload {
  run_id: number;
  status: string;
  phase: string | null;
  started_at: string;
  completed_at: string | null;
  counts: Record<string, number>;
  error: string | null;
}

export function useRunStream(active: boolean): {
  payload: RunStreamPayload | null;
  connected: boolean;
} {
  const [payload, setPayload] = useState<RunStreamPayload | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!active) return;
    const es = new EventSource("/api/runs/current/stream");
    setConnected(true);
    es.addEventListener("phase", (e) => {
      try {
        setPayload(JSON.parse((e as MessageEvent).data));
      } catch {
        // ignore
      }
    });
    es.addEventListener("done", () => {
      setConnected(false);
      es.close();
    });
    es.onerror = () => {
      setConnected(false);
      es.close();
    };
    return () => {
      es.close();
      setConnected(false);
    };
  }, [active]);

  return { payload, connected };
}
