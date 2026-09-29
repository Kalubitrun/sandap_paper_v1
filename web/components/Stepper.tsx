export type Step = "create" | "analysis" | "review" | "result";

const STEPS: { id: Step; label: string }[] = [
  { id: "create", label: "Create" },
  { id: "analysis", label: "Analyze" },
  { id: "review", label: "Review" },
  { id: "result", label: "Download" },
];

export default function Stepper({ step }: { step: Step }) {
  const active = STEPS.findIndex((s) => s.id === step);
  return (
    <ol className="flex items-center gap-1 sm:gap-2" aria-label="Progress">
      {STEPS.map((s, i) => (
        <li key={s.id} className="flex flex-1 items-center gap-1 sm:gap-2">
          <span
            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
              i < active
                ? "bg-emerald-600 text-white"
                : i === active
                  ? "bg-blue-800 text-white"
                  : "bg-slate-200 text-slate-500"
            }`}
          >
            {i + 1}
          </span>
          <span
            className={`hidden text-sm font-medium sm:block ${
              i === active ? "text-slate-900" : "text-slate-500"
            }`}
          >
            {s.label}
          </span>
          {i < STEPS.length - 1 && (
            <span className="mx-1 h-px flex-1 bg-slate-300" aria-hidden />
          )}
        </li>
      ))}
    </ol>
  );
}
