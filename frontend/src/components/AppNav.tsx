"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { IconBall } from "./icons";
import StatusBadge from "./StatusBadge";

const LINKS = [
  { href: "/", label: "Fixtures" },
  { href: "/simulator", label: "Simulator" },
];

export default function AppNav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-line-soft bg-ink/85 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-5 md:px-8 h-14 flex items-center justify-between gap-6">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-accent">
            <IconBall size={20} />
          </span>
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
          <StatusBadge />
        </nav>
      </div>
    </header>
  );
}
