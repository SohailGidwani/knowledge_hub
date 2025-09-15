import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cn } from '@/components/utils';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
  variant?: 'default' | 'secondary' | 'ghost' | 'destructive' | 'outline';
  size?: 'sm' | 'md' | 'lg';
}

const variantMap: Record<NonNullable<ButtonProps['variant']>, string> = {
  default:
    'bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:pointer-events-none',
  secondary:
    'bg-secondary text-secondary-foreground hover:bg-secondary/80 disabled:opacity-50 disabled:pointer-events-none',
  ghost:
    'bg-transparent hover:bg-accent text-foreground disabled:opacity-50 disabled:pointer-events-none',
  destructive:
    'bg-destructive text-white hover:bg-destructive/90 disabled:opacity-50 disabled:pointer-events-none',
  outline:
    'border border-border hover:bg-accent disabled:opacity-50 disabled:pointer-events-none',
};

const sizeMap: Record<NonNullable<ButtonProps['size']>, string> = {
  sm: 'h-9 px-3 rounded-xl',
  md: 'h-10 px-4 rounded-2xl',
  lg: 'h-11 px-6 rounded-2xl',
};

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'md', asChild, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        className={cn(
          'inline-flex items-center justify-center whitespace-nowrap text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background',
          variantMap[variant],
          sizeMap[size],
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = 'Button';

export { Button };

