"use client";

import { useRef, useState } from "react";

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

interface Props {
  file: File | null;
  onSelect: (file: File | null) => void;
  error: string | null;
  onError: (message: string | null) => void;
}

export default function UploadArea({ file, onSelect, error, onError }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function accept(candidate: File | undefined) {
    if (!candidate) return;
    const okName = candidate.name.toLowerCase().endsWith(".docx");
    const okType =
      candidate.type ===
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
      candidate.type === "";
    if (!okName || !okType) {
      onError("Unsupported file type. Please upload a Word document (.docx).");
      return;
    }
    if (candidate.size > MAX_UPLOAD_BYTES) {
      onError("File is too large. Please upload a file smaller than 10 MB.");
      return;
    }
    onError(null);
    onSelect(candidate);
  }

  return (
    <div>
      <label className="mb-2 block text-sm font-semibold text-slate-700">
        Teacher Question Paper (.docx)
      </label>
      {!file ? (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            accept(e.dataTransfer.files?.[0]);
          }}
          className={`flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-10 text-center transition ${
            dragging
              ? "border-blue-700 bg-blue-50"
              : "border-slate-300 bg-slate-50 hover:border-blue-600 hover:bg-blue-50/50"
          }`}
        >
          <span className="text-3xl" aria-hidden>
            📄
          </span>
          <span className="text-base font-medium text-slate-800">
            Drag and drop your DOCX here, or click to browse
          </span>
          <span className="text-sm text-slate-500">
            Only .docx files, up to 10 MB
          </span>
        </button>
      ) : (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-base font-medium text-slate-900">
              📄 {file.name}
            </p>
            <p className="text-sm text-slate-500">{formatSize(file.size)}</p>
          </div>
          <div className="flex shrink-0 gap-2">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Replace
            </button>
            <button
              type="button"
              onClick={() => onSelect(null)}
              className="rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
            >
              Remove
            </button>
          </div>
        </div>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="hidden"
        onChange={(e) => {
          accept(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      {error && (
        <p role="alert" className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
