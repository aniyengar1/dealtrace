import type { ReactNode } from "react";

export function Container({
  children,
  className = "",
  wide = false,
}: {
  children: ReactNode;
  className?: string;
  wide?: boolean;
}) {
  return (
    <div className={`mx-auto w-full ${wide ? "max-w-6xl" : "max-w-5xl"} px-4 sm:px-6 ${className}`}>{children}</div>
  );
}
