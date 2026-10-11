"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { getHealth } from "@/lib/api";
import StatusBadge, { type BackendAvailability } from "./StatusBadge";

const LINKS = [
  { href: "/", label: "Fixtures" },
  { href: "/simulator", label: "Simulator" },
  { href: "/account", label: "Account" },
  { href: "/settings", label: "Settings" },
];

export default function AppNav() {
  const pathname = usePathname();
  const [availability, setAvailability] = useState<BackendAvailability>({ state: "checking", ollama: null });

  useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        const health = await getHealth();
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

  return (
    <header className="sticky top-0 z-40 border-b border-line-soft bg-ink/85 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-5 md:px-8 h-14 flex items-center justify-between gap-6">
        <div className="flex items-center gap-3 min-w-0">
          <Image
            src="/brand/new-x1-nav-icon.png"
            alt=""
            width={32}
            height={32}
            className="shrink-0 rounded-md"
            unoptimized
          />
          <span className="font-bold tracking-[0.08em] text-[15px] text-fg">NEW_X1</span>
          <span className="hidden md:block w-px h-4 bg-line" />
          <span className="hidden md:block mono-label text-fg-mute !tracking-[0.22em]">
            Cricket Performance Intelligence
          </span>
        </div>

        <nav className="flex items-center gap-1">
          {LINKS.map((l) => {
            const active = pathname === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`relative mono-label px-3 py-2 transition-colors ${
                  active ? "text-fg" : "text-fg-mute hover:text-fg-dim"
                }`}
              >
                {l.label}
                {active && (
                  <span className="absolute left-3 right-3 -bottom-[13px] h-[2px] bg-accent" />
                )}
              </Link>
            );
          })}
          <span className="w-px h-4 bg-line mx-2" />
          <StatusBadge availability={availability} />
        </nav>
      </div>
      {availability.state !== "checking" && availability.state !== "online" && (
        <div role="status" className="border-t border-warn/30 bg-[#241b10] px-5 py-3 text-sm text-fg-dim">
          <div className="max-w-7xl mx-auto flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-semibold text-warn">Analysis temporarily unavailable.</span>
            <span>{availability.state === "no_models" ? "The backend is online, but its ML models are not ready." : availability.state === "partial_models" ? "The backend is online, but some ML formats are unavailable." : "The website is online, but the laptop backend is offline or disconnected."}</span>
            <span>To request that we start the backend and ML engine,</span>
            <a className="text-fg underline underline-offset-2 hover:text-accent" href="mailto:riddhu.work@gmail.com?subject=NEW_X1%20backend%20request">email riddhu.work@gmail.com</a>
            <span>or</span>
            <a className="text-fg underline underline-offset-2 hover:text-accent" href="https://wa.me/918982094147?text=Please%20start%20the%20NEW_X1%20backend%20and%20ML%20engine" target="_blank" rel="noopener noreferrer">message +91 8982094147</a>.
          </div>
        </div>
      )}
    </header>
  );
}
