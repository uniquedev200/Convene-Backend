import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-custom font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
          {
            "bg-accent border border-border-color text-black hover:bg-accent-hover hover:scale-[1.02] active:scale-[0.98] shadow-sm hover:shadow-[0_0_15px_rgba(255,255,255,0.15)] transition-all duration-300": variant === "primary",
            "border border-border-color bg-card-bg text-primary-text hover:bg-accent-muted hover:scale-[1.01] active:scale-[0.99] transition-all duration-200": variant === "secondary",
            "border border-border-color bg-transparent hover:bg-accent-muted hover:border-foreground text-foreground hover:scale-[1.01] transition-all duration-200": variant === "outline",
            "bg-transparent hover:bg-accent-muted text-foreground transition-all duration-150": variant === "ghost",
            "bg-rose-950/10 text-rose-500 border border-rose-500/30 hover:bg-rose-950/20 hover:scale-[1.02] active:scale-[0.98] transition-all duration-300": variant === "danger",
          },
          {
            "h-8 px-3 text-xs": size === "sm",
            "h-10 px-4 py-2 text-sm": size === "md",
            "h-12 px-6 text-base": size === "lg",
          },
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
