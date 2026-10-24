import type { ReactNode } from "react";
import Image from "next/image";

// The hero's collage, with the worked example pasted on top of it like a
// clipping. The collage pans slowly unless the visitor asked for less motion.
export function HeroMedia({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="relative">
      <div data-collage className="relative aspect-[16/10] overflow-hidden rounded-2xl border bg-paper">
        <Image
          src="/media/hero-keyframe.webp"
          alt="Collage de papel: una burbuja de chat separada en tres tiras, con una lupa sobre la del medio."
          fill
          loading="eager"
          fetchPriority="high"
          sizes="(min-width: 1152px) 620px, (min-width: 1024px) 55vw, 100vw"
          className="hero-pan object-cover object-right"
        />
      </div>
      <div data-enter="card" className="relative -mt-16 mr-4 sm:-mt-24 sm:mr-12 lg:-ml-8">{children}</div>
    </div>
  );
}
