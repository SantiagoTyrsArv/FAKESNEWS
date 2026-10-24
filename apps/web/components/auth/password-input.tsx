"use client";

import type { FocusEvent } from "react";
import { Input } from "@/components/ui/input";

/**
 * A password field with a "Mostrar"/"Ocultar" toggle. The toggle never takes
 * focus from the field on click (mousedown is cancelled) and tells assistive
 * tech its state (aria-pressed) and what it controls. onFocus/onBlur fire for
 * the field and its toggle together: tabbing from one to the other is still
 * "in the password".
 */
export function PasswordInput({
  id,
  value,
  onChange,
  autoComplete,
  visible,
  onVisibleChange,
  onFocus,
  onBlur,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: "current-password" | "new-password";
  visible: boolean;
  onVisibleChange: (visible: boolean) => void;
  onFocus?: () => void;
  onBlur?: () => void;
}) {
  const within = (e: FocusEvent<HTMLDivElement>) =>
    e.relatedTarget instanceof Node && e.currentTarget.contains(e.relatedTarget);

  return (
    <div
      className="relative"
      onFocus={(e) => {
        if (!within(e)) onFocus?.();
      }}
      onBlur={(e) => {
        if (!within(e)) onBlur?.();
      }}
    >
      <Input
        id={id}
        type={visible ? "text" : "password"}
        autoComplete={autoComplete}
        required
        className="h-10 pr-20"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <button
        type="button"
        aria-controls={id}
        aria-pressed={visible}
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => onVisibleChange(!visible)}
        className="absolute inset-y-1 right-1 rounded-md px-2.5 text-sm font-medium text-primary underline-offset-4 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        {visible ? "Ocultar" : "Mostrar"}
      </button>
    </div>
  );
}
