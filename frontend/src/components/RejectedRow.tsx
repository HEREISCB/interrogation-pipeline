import type { CaseRow } from "@/api/types";

export default function RejectedRow({ c }: { c: CaseRow }) {
  return (
    <div className="border border-line rounded-md px-3 py-2 bg-bg-soft text-sm flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="font-medium truncate">
          {c.defendant ?? "—"}{" "}
          <span className="text-soft font-normal">
            · {c.location ?? "no location"}
          </span>
        </div>
        <div className="text-xs text-soft mt-0.5">
          {c.charges ?? "(no charges extracted)"}
        </div>
      </div>
      <div className="text-xs text-soft shrink-0">verify: {c.verification_status ?? "—"}</div>
    </div>
  );
}
