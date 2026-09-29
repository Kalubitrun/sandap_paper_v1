"use client";

import type { AnalyzeResponse, PaperSettingsInput } from "@/lib/api";

interface Props {
  analysis: AnalyzeResponse;
  settings: PaperSettingsInput;
  onReview: () => void;
  onGenerate: () => void;
  onBack: () => void;
  generating: boolean;
}

function Check({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2 text-base text-slate-800">
      <span className="mt-0.5 font-bold text-emerald-600" aria-hidden>
        ✓
      </span>
      <span>{children}</span>
    </li>
  );
}

export default function AnalysisView({
  analysis,
  settings,
  onReview,
  onGenerate,
  onBack,
  generating,
}: Props) {
  const { summary, validation } = analysis;
  const warnings = validation.warnings;

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <h2 className="text-xl font-bold text-slate-900">Paper Analysis</h2>
        <ul className="mt-4 space-y-2">
          <Check>Document read successfully</Check>
          <Check>
            {summary.sections} section{summary.sections === 1 ? "" : "s"} detected
          </Check>
          <Check>
            {summary.questions} question{summary.questions === 1 ? "" : "s"} detected
          </Check>
          {summary.has_instructions ? (
            <Check>General instructions detected</Check>
          ) : (
            <li className="text-base text-slate-500">No general instructions found</li>
          )}
        </ul>

        {warnings.length > 0 && (
          <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
            <h3 className="text-base font-bold text-amber-900">Warnings</h3>
            <ul className="mt-2 space-y-1.5">
              {warnings.slice(0, 5).map((w, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-amber-900">
                  <span aria-hidden>⚠</span>
                  <span>{w.message}</span>
                </li>
              ))}
            </ul>
            {warnings.length > 5 && (
              <p className="mt-2 text-sm text-amber-800">
                + {warnings.length - 5} more — review all issues before generating.
              </p>
            )}
          </div>
        )}

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={onReview}
            className="rounded-xl border-2 border-blue-800 px-6 py-3 text-base font-semibold text-blue-800 hover:bg-blue-50"
          >
            Review Issues ({warnings.length + validation.errors.length})
          </button>
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating || validation.summary.has_errors}
            className="rounded-xl bg-blue-800 px-6 py-3 text-base font-semibold text-white hover:bg-blue-900 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {generating ? "Generating…" : "Generate Paper"}
          </button>
        </div>
        {validation.summary.has_errors && (
          <p className="mt-2 text-sm text-red-700">
            Generation is blocked until the error issues below are resolved in the
            teacher document.
          </p>
        )}
        <button
          type="button"
          onClick={onBack}
          className="mt-4 text-sm font-medium text-slate-600 underline hover:text-slate-900"
        >
          ← Back to settings
        </button>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <h3 className="text-base font-bold text-slate-900">Paper Settings</h3>
        <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-base sm:grid-cols-2">
          {[
            ["Exam", settings.examination],
            ["Session", settings.session],
            ["Class", settings.class_name],
            ["Subject", settings.subject],
            ["Subject Code", settings.subject_code],
            ["Maximum Marks", settings.max_marks],
            ["Time", settings.time],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between gap-4 border-b border-slate-100 py-1.5">
              <dt className="text-slate-500">{k}</dt>
              <dd className="font-medium text-slate-900">{v}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
