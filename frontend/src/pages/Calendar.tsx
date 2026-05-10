import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { DayCount } from "@/api/types";

type Day = {
  iso: string;
  inMonth: boolean;
  counts?: DayCount["counts"];
};

function buildMonthGrid(year: number, month0: number): Day[] {
  // Always 6×7 grid, leading/trailing days from sibling months greyed.
  const first = new Date(Date.UTC(year, month0, 1));
  const startWeekday = first.getUTCDay(); // 0=Sun
  const daysInMonth = new Date(Date.UTC(year, month0 + 1, 0)).getUTCDate();
  const cells: Day[] = [];
  // leading
  for (let i = startWeekday - 1; i >= 0; i--) {
    const d = new Date(Date.UTC(year, month0, -i));
    cells.push({ iso: d.toISOString().slice(0, 10), inMonth: false });
  }
  // current month
  for (let d = 1; d <= daysInMonth; d++) {
    const dt = new Date(Date.UTC(year, month0, d));
    cells.push({ iso: dt.toISOString().slice(0, 10), inMonth: true });
  }
  // trailing — fill to 42
  let i = 1;
  while (cells.length < 42) {
    const dt = new Date(Date.UTC(year, month0 + 1, i++));
    cells.push({ iso: dt.toISOString().slice(0, 10), inMonth: false });
  }
  return cells;
}

function colorFor(c?: DayCount["counts"]): string {
  if (!c || c.discovered === 0) return "bg-bg-soft";
  if (c.failed > 0 && c.discovered === 0) return "bg-red-100";
  if (c.accepted >= 5) return "bg-green-200";
  if (c.accepted >= 1) return "bg-green-100";
  return "bg-blue-50";
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export default function Calendar() {
  const today = new Date();
  const [year, setYear] = useState(today.getUTCFullYear());
  const [month0, setMonth0] = useState(today.getUTCMonth());

  const fromIso = useMemo(
    () => new Date(Date.UTC(year, month0, 1)).toISOString().slice(0, 10),
    [year, month0]
  );
  const toIso = useMemo(
    () => new Date(Date.UTC(year, month0 + 1, 0)).toISOString().slice(0, 10),
    [year, month0]
  );

  const { data } = useQuery({
    queryKey: ["days", fromIso, toIso],
    queryFn: () => api.days(fromIso, toIso),
  });

  const cells = buildMonthGrid(year, month0);
  const byDate = new Map<string, DayCount["counts"]>();
  data?.forEach((d) => byDate.set(d.date_iso, d.counts));

  const monthName = new Date(Date.UTC(year, month0, 1)).toLocaleString(
    undefined,
    { month: "long", year: "numeric" }
  );

  const shift = (delta: number) => {
    const d = new Date(Date.UTC(year, month0 + delta, 1));
    setYear(d.getUTCFullYear());
    setMonth0(d.getUTCMonth());
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Calendar</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => shift(-1)}
            className="border border-line rounded-md px-2 py-1 text-sm hover:bg-bg-soft"
          >
            ◀
          </button>
          <div className="font-medium min-w-[10rem] text-center">{monthName}</div>
          <button
            onClick={() => shift(1)}
            className="border border-line rounded-md px-2 py-1 text-sm hover:bg-bg-soft"
          >
            ▶
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1 mb-1 text-xs text-soft text-center uppercase">
        {WEEKDAYS.map((w) => (
          <div key={w}>{w}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((cell) => {
          const counts = byDate.get(cell.iso);
          return (
            <div
              key={cell.iso}
              className={`min-h-[80px] rounded-md border border-line p-2 text-xs ${colorFor(counts)} ${
                cell.inMonth ? "" : "opacity-30"
              }`}
            >
              <div className="text-ink font-medium">
                {Number(cell.iso.slice(-2))}
              </div>
              {counts ? (
                <div className="mt-1 space-y-0.5 leading-tight">
                  <div title="discovered">{counts.discovered} disc.</div>
                  {counts.accepted > 0 && (
                    <div className="text-good">+{counts.accepted} accepted</div>
                  )}
                  {counts.pushed > 0 && (
                    <div className="text-accent">→{counts.pushed} trello</div>
                  )}
                  {counts.failed > 0 && (
                    <div className="text-bad">!{counts.failed} fail</div>
                  )}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="mt-4 text-xs text-soft flex gap-4 flex-wrap">
        <Legend swatch="bg-bg-soft" label="no run / no activity" />
        <Legend swatch="bg-blue-50" label="ran but no homicides found" />
        <Legend swatch="bg-green-100" label="1-4 accepted" />
        <Legend swatch="bg-green-200" label="5+ accepted" />
        <Legend swatch="bg-red-100" label="run failed" />
      </div>
    </div>
  );
}

function Legend({ swatch, label }: { swatch: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`inline-block w-3 h-3 rounded ${swatch} border border-line`} />
      {label}
    </span>
  );
}
