// Ícone de chapéu de cowboy no mesmo estilo dos ícones Lucide (traço 2px, 24x24).
import { forwardRef } from 'react'
import type { LucideProps } from 'lucide-react'

export const CowboyHat = forwardRef<SVGSVGElement, LucideProps>(function CowboyHat(
  { size = 24, color = 'currentColor', strokeWidth = 2, ...props },
  ref,
) {
  return (
    <svg
      ref={ref}
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M2 14c2.5 3 17.5 3 20 0" />
      <path d="M5.5 15.5 7 8c.3-1.6 1.6-2.4 3-1.7l2 1 2-1c1.4-.7 2.7.1 3 1.7l1.5 7.5" />
      <path d="M6.6 11.5c3.4 1.2 7.4 1.2 10.8 0" />
    </svg>
  )
})
