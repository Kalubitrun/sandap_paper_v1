"use client";

import { CLASSES, EXAMINATIONS, type PaperSettingsInput } from "@/lib/api";
import UploadArea from "./UploadArea";

interface Props {
  settings: PaperSettingsInput;
  onChange: (settings: PaperSettingsInput) => void;
  file: File | null;
  onFile: (file: File | null) => void;
  uploadError: string | null;
  onUploadError: (message: string | null) => void;
  onAnalyze: () => void;
  busy: boolean;
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-semibold text-slate-700">{label}</span>
      {children}
    </label>
  );
}

const inputClass =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900 focus:border-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-100";

export default function CreateForm({
  settings,
  onChange,
  file,
  onFile,
  uploadError,
  onUploadError,
  onAnalyze,
  busy,
}: Props) {
  const set = (key: keyof PaperSettingsInput) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => onChange({ ...settings, [key]: e.target.value });

  const ready =
    !busy &&
    file !== null &&
    settings.session.trim() !== "" &&
    settings.class_name.trim() !== "" &&
    settings.subject.trim() !== "" &&
    settings.subject_code.trim() !== "" &&
    settings.max_marks.trim() !== "" &&
    settings.time.trim() !== "";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
      <h2 className="text-xl font-bold text-slate-900">Create Question Paper</h2>
      <p className="mt-1 text-sm text-slate-600">
        Create a professional question paper from your teacher&apos;s DOCX in a few simple steps.
      </p>

      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Examination">
          <select value={settings.examination} onChange={set("examination")} className={inputClass}>
            {EXAMINATIONS.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Session">
          <input
            value={settings.session}
            onChange={set("session")}
            placeholder="2026-27"
            className={inputClass}
          />
        </Field>
        <Field label="Class">
          <select value={settings.class_name} onChange={set("class_name")} className={inputClass}>
            {CLASSES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Subject">
          <input
            value={settings.subject}
            onChange={set("subject")}
            placeholder="Information Technology"
            className={inputClass}
          />
        </Field>
        <Field label="Subject Code">
          <input
            value={settings.subject_code}
            onChange={set("subject_code")}
            placeholder="402"
            className={inputClass}
          />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Maximum Marks">
            <input
              value={settings.max_marks}
              onChange={set("max_marks")}
              inputMode="numeric"
              placeholder="50"
              className={inputClass}
            />
          </Field>
          <Field label="Time">
            <input
              value={settings.time}
              onChange={set("time")}
              placeholder="3:00 hours"
              className={inputClass}
            />
          </Field>
        </div>
      </div>

      <div className="mt-5">
        <UploadArea file={file} onSelect={onFile} error={uploadError} onError={onUploadError} />
      </div>

      <button
        type="button"
        onClick={onAnalyze}
        disabled={!ready}
        className="mt-6 w-full rounded-xl bg-blue-800 px-4 py-3.5 text-lg font-semibold text-white transition hover:bg-blue-900 disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-auto sm:px-10"
      >
        {busy ? "Analyzing…" : "Analyze Paper"}
      </button>
      {!ready && !busy && (
        <p className="mt-2 text-sm text-slate-500">
          Fill all fields and upload a DOCX file to continue.
        </p>
      )}
    </div>
  );
}
