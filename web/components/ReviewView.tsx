"use client";

import type { AnalyzeResponse, ValidationIssue } from "@/lib/api";

function where(issue: ValidationIssue): string | null {
  const parts: string[] = [];
  if (issue.question_number !== null && issue.question_number !== undefined) {
    parts.push(`Q${issue.question_number}`);
  }
  if (issue.section) parts.push(`Section ${issue.section}`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function DetailList({ details }: { details: Record<string, unknown> }) {
  const entries = Object.entries(details).filter(
    ([, v]) => v !== null && v !== undefined && v !== ""
  );
  if (entries.length === 0) return null;
  const pretty = (v: unknown): string =>
    Array.isArray(v) ? v.map((x) => String(x)).join(", ") : String(v);
  return (
    <dl className="mt-2 space-y-1 rounded-lg bg-slate-50 px-3 py-2 text-sm">
      {entries.map(([k, v]) => (
        <div key={k} className="flex gap-2">
          <dt className="font-medium capitalize text-slate-500">{k.replace(/_/g, " ")}</dt>
          <dd className="text-slate-800">{pretty(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

const SEVERITY_STYLE: Record<string, { badge: string; icon: string }> = {
  error: { badge: "bg-red-100 text-red-800", icon: "⛔" },
  warning: { badge: "bg-amber-100 text-amber-900", icon: "⚠" },
  info: { badge: "bg-blue-100 text-blue-900", icon: "ℹ" },
};

interface Props {
  analysis: AnalyzeResponse;
  acknowledged: Set<string>;
  onToggle: (key: string) => void;
  spellingDone: Set<number>;
  onSpelling: (index: number, decision: "accepted" | "kept") => void;
  spellingChoice: Record<number, "accepted" | "kept">;
  onGenerate: () => void;
  onBack: () => void;
  generating: boolean;
}

export default function ReviewView({
  analysis,
  acknowledged,
  onToggle,
  spellingDone,
  onSpelling,
  spellingChoice,
  onGenerate,
  onBack,
  generating,
}: Props) {
  const { validation, spelling } = analysis;
  const actionable = [...validation.errors, ...validation.warnings];
  const allReviewed =
    actionable.every((_, i) => acknowledged.has(`issue-${i}`)) &&
    spelling.suggestions.every((_, i) => spellingDone.has(i));
  const blocked = validation.summary.has_errors;

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <h2 className="text-xl font-bold text-slate-900">Review Issues</h2>
        <p className="mt-1 text-sm text-slate-600">
          Nothing is fixed automatically. Mark each issue as reviewed to continue.
        </p>

        {actionable.length === 0 && (
          <p className="mt-4 rounded-xl bg-emerald-50 px-4 py-3 text-base text-emerald-800">
            ✓ No errors or warnings found.
          </p>
        )}

        <ul className="mt-4 space-y-3">
          {actionable.map((issue, i) => {
            const style = SEVERITY_STYLE[issue.severity];
            const key = `issue-${i}`;
            const done = acknowledged.has(key);
            return (
              <li
                key={key}
                className={`rounded-xl border p-4 ${
                  done ? "border-emerald-200 bg-emerald-50/40" : "border-slate-200 bg-white"
                }`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span aria-hidden>{style.icon}</span>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold uppercase ${style.badge}`}>
                    {issue.severity}
                  </span>
                  <span className="text-sm font-bold text-slate-700">
                    {issue.code.replace(/_/g, " ")}
                  </span>
                  {where(issue) && (
                    <span className="text-sm text-slate-500">{where(issue)}</span>
                  )}
                </div>
                <p className="mt-2 text-base text-slate-900">{issue.message}</p>
                <DetailList details={issue.details} />
                <button
                  type="button"
                  onClick={() => onToggle(key)}
                  className={`mt-3 rounded-lg px-4 py-2 text-sm font-semibold ${
                    done
                      ? "bg-emerald-600 text-white"
                      : "border border-slate-300 text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  {done ? "✓ Reviewed" : "Mark as reviewed"}
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <h2 className="text-xl font-bold text-slate-900">Spelling Suggestions</h2>
        <p className="mt-1 text-sm text-slate-600">
          Suggestions are never applied automatically — your document stays unchanged.
        </p>
        {spelling.suggestions.length === 0 ? (
          <p className="mt-4 rounded-xl bg-emerald-50 px-4 py-3 text-base text-emerald-800">
            ✓ No spelling suggestions.
          </p>
        ) : (
          <ul className="mt-4 space-y-3">
            {spelling.suggestions.map((s, i) => (
              <li key={i} className="rounded-xl border border-slate-200 p-4">
                <p className="text-sm text-slate-500">Possible spelling mistake</p>
                <p className="mt-1 text-lg">
                  <span className="font-semibold text-red-700">{s.original}</span>
                  <span className="mx-2 text-slate-400">→</span>
                  <span className="font-semibold text-emerald-700">{s.suggested}</span>
                </p>
                {s.context && (
                  <p className="mt-1 text-sm italic text-slate-600">“{s.context}”</p>
                )}
                <div className="mt-3 flex gap-2">
                  {(["accepted", "kept"] as const).map((choice) => (
                    <button
                      key={choice}
                      type="button"
                      onClick={() => onSpelling(i, choice)}
                      className={`rounded-lg px-4 py-2 text-sm font-semibold ${
                        spellingChoice[i] === choice
                          ? "bg-blue-800 text-white"
                          : "border border-slate-300 text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      {choice === "accepted" ? "Accept" : "Keep Original"}
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={onBack}
          className="rounded-xl border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 hover:bg-slate-50"
        >
          ← Back
        </button>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating || blocked || !allReviewed}
          className="rounded-xl bg-blue-800 px-6 py-3 text-base font-semibold text-white hover:bg-blue-900 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {generating ? "Generating…" : "Generate Question Paper"}
        </button>
      </div>
      {blocked ? (
        <p className="text-sm text-red-700">
          Generation is blocked by error-level issues. Please fix the teacher document
          and upload it again.
        </p>
      ) : (
        !allReviewed && (
          <p className="text-sm text-slate-500">
            Review every issue and spelling suggestion above to enable generation.
          </p>
        )
      )}
    </div>
  );
}
