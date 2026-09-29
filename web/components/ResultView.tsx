"use client";

interface Props {
  filename: string;
  downloadUrl: string;
  onRestart: () => void;
}

export default function ResultView({ filename, downloadUrl, onRestart }: Props) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 text-center shadow-sm sm:p-10">
      <p className="text-4xl" aria-hidden>
        ✓
      </p>
      <h2 className="mt-3 text-xl font-bold text-slate-900">
        Question paper generated successfully.
      </h2>
      <div className="mx-auto mt-4 max-w-md rounded-xl bg-slate-50 px-4 py-3 text-left">
        <p className="text-sm text-slate-500">File name</p>
        <p className="break-all text-base font-semibold text-slate-900">{filename}</p>
      </div>
      <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
        <a
          href={downloadUrl}
          download={filename}
          className="rounded-xl bg-blue-800 px-8 py-3.5 text-lg font-semibold text-white hover:bg-blue-900"
        >
          Download DOCX
        </a>
        <button
          type="button"
          disabled
          title="Coming soon"
          className="cursor-not-allowed rounded-xl bg-slate-200 px-8 py-3.5 text-lg font-semibold text-slate-400"
        >
          Download PDF
        </button>
      </div>
      <p className="mt-2 text-sm text-slate-500">PDF download is coming soon.</p>
      <button
        type="button"
        onClick={onRestart}
        className="mt-6 text-sm font-medium text-slate-600 underline hover:text-slate-900"
      >
        Format another paper
      </button>
    </div>
  );
}
