import { cn } from '../lib/utils';

export function AtivaBrand({
    className,
    textClassName,
    subtitle = 'Ativa Eleitoral',
    detail = 'Inteligência para gestão de campanha',
    compact = false
}) {
    return (
        <div className={cn('flex items-center gap-3', className)}>
            <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl bg-white shadow-[0_18px_38px_rgba(239,68,68,0.18)] ring-1 ring-red-100">
                <svg
                    viewBox="0 0 120 120"
                    className="h-10 w-10"
                    aria-hidden="true"
                >
                    <defs>
                        <linearGradient id="ativaLoop" x1="0%" x2="100%" y1="0%" y2="100%">
                            <stop offset="0%" stopColor="#ff4d4f" />
                            <stop offset="100%" stopColor="#d61f32" />
                        </linearGradient>
                    </defs>
                    <path
                        d="M23 62c0-23 18-41 41-41 15 0 29 8 36 20"
                        fill="none"
                        stroke="url(#ativaLoop)"
                        strokeLinecap="round"
                        strokeWidth="10"
                    />
                    <path d="M92 28l8 17-19-3" fill="url(#ativaLoop)" />
                    <path
                        d="M97 58c0 23-18 41-41 41-15 0-29-8-36-20"
                        fill="none"
                        stroke="url(#ativaLoop)"
                        strokeLinecap="round"
                        strokeWidth="10"
                    />
                    <path d="M28 92l-8-17 19 3" fill="url(#ativaLoop)" />
                    <path
                        d="M60 33 39 78h12l4-10h20l4 10h12L69 33Zm-1 25 6-14 6 14Z"
                        fill="#d61f32"
                    />
                </svg>
            </div>

            <div className={cn('min-w-0', textClassName)}>
                <p className="font-heading text-xl font-extrabold tracking-[-0.04em] text-slate-950">
                    {subtitle}
                </p>
                {!compact && (
                    <p className="text-xs font-medium text-slate-500">
                        {detail}
                    </p>
                )}
            </div>
        </div>
    );
}
