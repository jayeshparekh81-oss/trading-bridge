import Image from "next/image";

type LogoVariant = "icon" | "hero" | "wordmark";

interface LogoProps {
  variant?: LogoVariant;
  width?: number;
  height?: number;
  className?: string;
  priority?: boolean;
}

const VARIANTS: Record<LogoVariant, { src: string; w: number; h: number; alt: string }> = {
  icon:     { src: "/tradetri-icon.svg",     w: 64,  h: 64,  alt: "TRADETRI" },
  hero:     { src: "/tradetri-hero.svg",     w: 500, h: 690, alt: "TRADETRI \u2014 India\u2019s Algorithmic Trading Platform" },
  wordmark: { src: "/tradetri-wordmark.svg", w: 290, h: 80,  alt: "TRADETRI" },
};

export function Logo({
  variant = "icon",
  width,
  height,
  className,
  priority = false,
}: LogoProps) {
  const v = VARIANTS[variant];
  let w: number;
  let h: number;
  if (width !== undefined && height !== undefined) {
    w = width; h = height;
  } else if (width !== undefined) {
    w = width;
    h = Math.round((width / v.w) * v.h);
  } else if (height !== undefined) {
    h = height;
    w = Math.round((height / v.h) * v.w);
  } else {
    w = v.w; h = v.h;
  }

  return (
    <Image
      src={v.src}
      alt={v.alt}
      width={w}
      height={h}
      priority={priority}
      unoptimized
      className={className}
    />
  );
}
