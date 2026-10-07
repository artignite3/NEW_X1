// NEW_X1 — Line icon set (1.5px stroke, 24px grid, currentColor)

interface IconProps {
  className?: string;
  size?: number;
}

function base(className?: string, size: number = 16) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className,
    "aria-hidden": true,
  };
}

export function IconBall({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M8.2 4.6c2.4 4.6 2.4 10.2 0 14.8" />
      <path d="M15.8 4.6c-2.4 4.6-2.4 10.2 0 14.8" strokeDasharray="1.5 2.2" />
    </svg>
  );
}

export function IconPin({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <path d="M12 21s-6.5-5.3-6.5-10a6.5 6.5 0 1 1 13 0c0 4.7-6.5 10-6.5 10Z" />
      <circle cx="12" cy="10.6" r="2.3" />
    </svg>
  );
}

export function IconCalendar({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <rect x="4" y="5.5" width="16" height="15" rx="2" />
      <path d="M4 10h16M8.5 3.5v4M15.5 3.5v4" />
    </svg>
  );
}

export function IconCloud({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <path d="M7 18.5a4.5 4.5 0 0 1-.6-8.96 6 6 0 0 1 11.5 1.6 3.7 3.7 0 0 1-.7 7.36H7Z" />
    </svg>
  );
}

export function IconWind({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <path d="M3.5 8.5h10a2.6 2.6 0 1 0-2.6-2.6" />
      <path d="M3.5 12.5h15.2a2.9 2.9 0 1 1-2.9 2.9" />
      <path d="M3.5 16.5h7" />
    </svg>
  );
}

export function IconDroplet({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <path d="M12 3.5s6 6.2 6 10.2a6 6 0 0 1-12 0c0-4 6-10.2 6-10.2Z" />
    </svg>
  );
}

export function IconLayers({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <path d="m12 3.5 8.5 4.7L12 12.9 3.5 8.2 12 3.5Z" />
      <path d="m3.5 12.4 8.5 4.7 8.5-4.7" />
      <path d="m3.5 16.6 8.5 4.7 8.5-4.7" />
    </svg>
  );
}

export function IconChip({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <rect x="6.5" y="6.5" width="11" height="11" rx="1.5" />
      <rect x="10" y="10" width="4" height="4" />
      <path d="M9 2.5v4M15 2.5v4M9 17.5v4M15 17.5v4M2.5 9h4M2.5 15h4M17.5 9h4M17.5 15h4" />
    </svg>
  );
}

export function IconPulse({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <path d="M3 12h4l2.5-6.5L14 18l2.5-6H21" />
    </svg>
  );
}

export function IconUsers({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <circle cx="9" cy="8.5" r="3.2" />
      <path d="M3.5 20c.6-3.6 2.9-5.5 5.5-5.5s4.9 1.9 5.5 5.5" />
      <path d="M15.5 5.6a3.2 3.2 0 0 1 0 5.8" />
      <path d="M17.5 14.9c1.7.7 2.7 2.4 3 5.1" />
    </svg>
  );
}

export function IconShield({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <path d="M12 3 5 5.8v5.4c0 4.5 2.9 7.6 7 9.3 4.1-1.7 7-4.8 7-9.3V5.8L12 3Z" />
      <path d="m9.2 11.8 2 2 3.6-3.9" />
    </svg>
  );
}

export function IconTerminal({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <rect x="3" y="4.5" width="18" height="15" rx="2" />
      <path d="m7 9.5 3 2.5-3 2.5M12.5 15H17" />
    </svg>
  );
}

export function IconArrowRight({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <path d="M4 12h15M13.5 6.5 19 12l-5.5 5.5" />
    </svg>
  );
}

export function IconAlert({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <path d="M12 4 2.8 20h18.4L12 4Z" />
      <path d="M12 10v4.5M12 17.4v.2" />
    </svg>
  );
}

export function IconCheck({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <path d="m4.5 12.5 5 5 10-11" />
    </svg>
  );
}

export function IconCross({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

export function IconTarget({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.5" strokeDasharray="2 2.4" />
      <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconGauge({ className, size }: IconProps) {
  return (
    <svg {...base(className, size)}>
      <path d="M4.5 17.5a8.5 8.5 0 1 1 15 0" />
      <path d="M12 13.5 16 9" />
      <circle cx="12" cy="14" r="1.4" />
    </svg>
  );
}
