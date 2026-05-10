import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { CaseRow } from "@/api/types";

export default function CaseCard({ c }: { c: CaseRow }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<"" | "push" | "skip" | "review">("");

  const refresh = () => qc.invalidateQueries({ queryKey: ["today"] });

  const push = useMutation({
    mutationFn: () => api.pushCase(c.id),
    onSuccess: refresh,
    onSettled: () => setBusy(""),
  });
  const skip = useMutation({
    mutationFn: () => api.skipCase(c.id),
    onSuccess: refresh,
    onSettled: () => setBusy(""),
  });
  const review = useMutation({
    mutationFn: () => api.reviewCase(c.id),
    onSuccess: refresh,
    onSettled: () => setBusy(""),
  });

  const dedupBadge = (() => {
    if (c.dedup_status === "exists_old")
      return (
        <span className="text-xs bg-amber-100 text-amber-900 px-2 py-0.5 rounded">
          Already on main board
        </span>
      );
    if (c.dedup_status === "exists_new")
      return (
        <span className="text-xs bg-amber-100 text-amber-900 px-2 py-0.5 rounded">
          Already on triage board
        </span>
      );
    return null;
  })();

  const pushed = c.status === "pushed_to_trello";

  return (
    <div className="border border-line rounded-lg p-4 bg-white hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-base">
              {c.defendant ?? "Unknown defendant"}
            </h3>
            {dedupBadge}
            {c.banned_state && (
              <span
                className="text-xs bg-yellow-100 text-yellow-900 px-2 py-0.5 rounded"
                title="State is on Ayush's FOIA-banned list — usually not worth pursuing"
              >
                FOIA banned (state)
              </span>
            )}
            {c.banned_agency && (
              <span
                className="text-xs bg-yellow-100 text-yellow-900 px-2 py-0.5 rounded"
                title="Agency (LAPD/NYPD) is on the FOIA-banned list"
              >
                FOIA banned (agency)
              </span>
            )}
          </div>
          <div className="text-sm text-soft mt-0.5">
            Victim: {c.victim ?? "—"} · {c.location ?? "—"}
            {c.year ? ` · ${c.year}` : ""}
          </div>
        </div>
        <div className="text-right text-xs text-soft shrink-0">
          {c.verification_status && (
            <div>verify: {c.verification_status}</div>
          )}
        </div>
      </div>

      <div className="mt-2 text-sm">
        <span className="text-soft">Charges:</span> {c.charges ?? "—"}
      </div>
      {c.verdict && (
        <div className="mt-1 text-sm">
          <span className="text-soft">Verdict:</span> {c.verdict}
        </div>
      )}

      {c.articles?.length > 0 && (
        <div className="mt-2 text-sm">
          <span className="text-soft">Sources:</span>{" "}
          {c.articles.map((a, i) => (
            <a
              key={i}
              href={a.url}
              target="_blank"
              rel="noreferrer"
              className="text-accent hover:underline mr-2"
            >
              {a.title || `article ${i + 1}`}
            </a>
          ))}
        </div>
      )}

      <div className="mt-3 flex items-center gap-2">
        {pushed ? (
          <span className="text-good text-sm font-medium">
            ✓ Pushed to Trello
          </span>
        ) : (
          <button
            disabled={!!busy || c.dedup_status !== "unique"}
            onClick={() => {
              setBusy("push");
              push.mutate();
            }}
            className="bg-accent text-white px-3 py-1.5 rounded-md text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:bg-blue-700"
            title={
              c.dedup_status === "unique"
                ? "Push to triage board"
                : "Disabled — already exists on a board"
            }
          >
            {busy === "push" ? "Pushing…" : "Send to Trello"}
          </button>
        )}
        <button
          disabled={!!busy}
          onClick={() => {
            setBusy("review");
            review.mutate();
          }}
          className="border border-line text-ink px-3 py-1.5 rounded-md text-sm hover:bg-bg-soft"
        >
          Mark reviewed
        </button>
        <button
          disabled={!!busy}
          onClick={() => {
            setBusy("skip");
            skip.mutate();
          }}
          className="border border-line text-soft px-3 py-1.5 rounded-md text-sm hover:bg-bg-soft"
        >
          Skip
        </button>
      </div>

      {push.isError && (
        <div className="mt-2 text-sm text-bad">
          Push failed: {String(push.error)}
        </div>
      )}
    </div>
  );
}
