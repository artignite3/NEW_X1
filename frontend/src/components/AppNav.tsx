"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { getHealth, rediscoverApiBase } from "@/lib/api";
import StatusBadge, { type BackendAvailability } from "./StatusBadge";

const LINKS = [
  { href: "/", label: "Fixtures" },
  { href: "/simulator", label: "Simulator" },
  { href: "/account", label: "Account" },
  { href: "/settings", label: "Settings" },
];

const REQUEST_START =
  "mailto:riddhu.work@gmail.com?subject=NEW_X1%20backend%20request&body=Please%20start%20the%20NEW_X1%20analysis%20backend.";

export default function AppNav() {
  const pathname = usePathname();
  const [availability, setAvailability] = useState<BackendAvailability>({ state: "checking", ollama: null });

  useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        let health;
        try {
          health = await getHealth();
        } catch {
          // The laptop may have restarted with a new tunnel address.
          rediscoverApiBase();
          health = await getHealth();
        }
        const models = Object.values(health.models ?? {});
        if (active) setAvailability({
          state: models.length > 0 && models.every(Boolean) ? "online" : models.some(Boolean) ? "partial_models" : "no_models",
          ollama: health.ollama,
        });
      } catch {
        if (active) setAvailability({ state: "offline", ollama: null });
      }
    };
    void check();
    const timer = window.setInterval(check, 60_000);
    window.addEventListener("focus", check);
    window.addEventListener("new_x1_api_base_changed", check);
    return () => {
      active = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", check);
      window.removeEventListener("new_x1_api_base_changed", check);
    };
  }, []);

  const offlineReason =
    availability.state === "no_models" ? "The analysis server is up, but its models are still loading"
    : availability.state === "partial_models" ? "Some formats are unavailable while their models load"
    : "Analysis is offline. Fixtures and team picks return when the analysis server is running";

  return (
    <header className="sticky top-0 z-40 border-b border-line-soft bg-ink/95 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="h-14 flex items-center justify-between gap-6">
          <Link href="/" className="flex items-center gap-2 shrink-0 rounded-md">
            <Image src="/brand/new-x1-nav-icon.png" alt="" width={24} height={24} className="shrink-0" unoptimized />
            <span className="text-base font-semibold text-fg">NEW_X1</span>
          </Link>

          <div className="flex items-center gap-4">
            <nav className="hidden md:flex items-center gap-1" aria-label="Main navigation">
              {LINKS.map((l) => {
                const active = pathname === l.href;
                return (
                  <Link
                    key={l.href}
                    href={l.href}
                    aria-current={active ? "page" : undefined}
                    className={`h-8 px-3 inline-flex items-center rounded-md text-sm transition-colors ${
                      active ? "text-fg bg-panel-hi" : "text-fg-dim hover:text-fg"
                    }`}
                  >
                    {l.label}
                  </Link>
                );
              })}
            </nav>
            <StatusBadge availability={availability} />
          </div>
        </div>

        <nav className="md:hidden flex gap-1 pb-2 -mx-1 overflow-x-auto" aria-label="Mobile navigation">
          {LINKS.map((l) => {
            const active = pathname === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`h-11 px-3 inline-flex items-center rounded-md text-sm shrink-0 transition-colors ${
                  active ? "text-fg bg-panel-hi" : "text-fg-dim hover:text-fg"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
      </div>

      {availability.state !== "checking" && availability.state !== "online" && (
        <div role="status" className="border-t border-line-soft">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2 flex items-start gap-3 text-sm text-fg-dim">
            <span className="size-2 mt-1.5 rounded-full bg-warn shrink-0" />
            <p>
              {offlineReason}
              <a className="ml-3 text-fg underline underline-offset-2 decoration-line hover:decoration-fg whitespace-nowrap" href={REQUEST_START}>
                Request a start
              </a>
            </p>
          </div>
        </div>
      )}
    </header>
  );
}
