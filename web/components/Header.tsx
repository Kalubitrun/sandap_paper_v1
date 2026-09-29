export function BrandHeart({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className={`inline-block text-rose-500 heartbeat ${className}`}
    >
      <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
    </svg>
  );
}

export default function Header() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-4xl px-4 py-4 sm:px-6">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-slate-500 sm:text-sm">
          Sandap Software Solution
          <BrandHeart />
        </p>
        <h1 className="mt-0.5 text-lg font-bold text-slate-900 sm:text-xl">
          Question Paper Studio
        </h1>
      </div>
    </header>
  );
}
