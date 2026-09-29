"use client";

import { useState } from "react";
import AnalysisView from "@/components/AnalysisView";
import CreateForm from "@/components/CreateForm";
import Header from "@/components/Header";
import ResultView from "@/components/ResultView";
import ReviewView from "@/components/ReviewView";
import Stepper, { type Step } from "@/components/Stepper";
import {
  analyzePaper,
  generatePaper,
  type AnalyzeResponse,
  type PaperSettingsInput,
} from "@/lib/api";

type Phase = Step | "analyzing" | "generating";

const DEFAULT_SETTINGS: PaperSettingsInput = {
  examination: "Half Yearly Examination",
  session: "2026-27",
  class_name: "IX",
  subject: "Information Technology",
  subject_code: "402",
  max_marks: "50",
  time: "3:00 hours",
};

function stepOf(phase: Phase): Step {
  if (phase === "analyzing") return "create";
  if (phase === "generating") return "review";
  return phase;
}

export default function Home() {
  const [phase, setPhase] = useState<Phase>("create");
  const [settings, setSettings] = useState<PaperSettingsInput>(DEFAULT_SETTINGS);
  const [file, setFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());
  const [spellingDone, setSpellingDone] = useState<Set<number>>(new Set());
  const [spellingChoice, setSpellingChoice] = useState<
    Record<number, "accepted" | "kept">
  >({});
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [downloadName, setDownloadName] = useState<string>("");

  async function handleAnalyze() {
    if (!file) return;
    setError(null);
    setPhase("analyzing");
    try {
      const result = await analyzePaper(file);
      setAnalysis(result);
      setAcknowledged(new Set());
      setSpellingDone(new Set());
      setSpellingChoice({});
      setPhase("analysis");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed. Please try again.");
      setPhase("create");
    }
  }

  async function handleGenerate() {
    if (!file) return;
    setError(null);
    setPhase("generating");
    try {
      const { blob, filename } = await generatePaper(file, settings);
      if (downloadUrl) URL.revokeObjectURL(downloadUrl);
      setDownloadUrl(URL.createObjectURL(blob));
      setDownloadName(filename);
      setPhase("result");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Question paper generation failed.");
      setPhase(analysis ? "review" : "analysis");
    }
  }

  function restart() {
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    setPhase("create");
    setFile(null);
    setAnalysis(null);
    setError(null);
    setDownloadUrl(null);
  }

  const busy = phase === "analyzing" || phase === "generating";

  return (
    <div className="flex min-h-full flex-col">
      <Header />
      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6 sm:px-6">
        <div className="mb-6">
          <Stepper step={stepOf(phase)} />
        </div>

        {error && (
          <p
            role="alert"
            className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-base text-red-800"
          >
            {error}
          </p>
        )}

        {(phase === "create" || phase === "analyzing") && (
          <CreateForm
            settings={settings}
            onChange={setSettings}
            file={file}
            onFile={setFile}
            uploadError={uploadError}
            onUploadError={setUploadError}
            onAnalyze={handleAnalyze}
            busy={busy}
          />
        )}

        {phase === "analysis" && analysis && (
          <AnalysisView
            analysis={analysis}
            settings={settings}
            onReview={() => setPhase("review")}
            onGenerate={handleGenerate}
            onBack={() => setPhase("create")}
            generating={busy}
          />
        )}

        {(phase === "review" || (phase === "generating" && analysis)) &&
          analysis && (
            <ReviewView
              analysis={analysis}
              acknowledged={acknowledged}
              onToggle={(key) =>
                setAcknowledged((prev) => {
                  const next = new Set(prev);
                  if (next.has(key)) next.delete(key);
                  else next.add(key);
                  return next;
                })
              }
              spellingDone={spellingDone}
              spellingChoice={spellingChoice}
              onSpelling={(index, decision) => {
                setSpellingChoice((prev) => ({ ...prev, [index]: decision }));
                setSpellingDone((prev) => new Set(prev).add(index));
              }}
              onGenerate={handleGenerate}
              onBack={() => setPhase("analysis")}
              generating={busy}
            />
          )}

        {phase === "result" && downloadUrl && (
          <ResultView filename={downloadName} downloadUrl={downloadUrl} onRestart={restart} />
        )}
      </main>
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-sm text-slate-500">
        Made with ❤️ by Sandap Software Solution for teachers
      </footer>
    </div>
  );
}
