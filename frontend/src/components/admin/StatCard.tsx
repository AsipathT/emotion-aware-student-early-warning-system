import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  color?: 'indigo' | 'emerald' | 'amber' | 'purple' | 'rose' | 'sky';
  badge?: {
    text: string;
    variant: 'positive' | 'negative' | 'neutral';
  };
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  color = 'indigo',
  badge,
}) => {
  const colorMap = {
    indigo: {
      bg: 'bg-indigo-50 text-indigo-600',
      border: 'border-slate-200 hover:border-indigo-200',
    },
    emerald: {
      bg: 'bg-emerald-50 text-emerald-600',
      border: 'border-slate-200 hover:border-emerald-200',
    },
    amber: {
      bg: 'bg-amber-50 text-amber-600',
      border: 'border-slate-200 hover:border-amber-200',
    },
    purple: {
      bg: 'bg-purple-50 text-purple-600',
      border: 'border-slate-200 hover:border-purple-200',
    },
    rose: {
      bg: 'bg-rose-50 text-rose-600',
      border: 'border-slate-200 hover:border-rose-200',
    },
    sky: {
      bg: 'bg-sky-50 text-sky-600',
      border: 'border-slate-200 hover:border-sky-200',
    },
  };

  const badgeColors = {
    positive: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    negative: 'bg-rose-50 text-rose-700 border-rose-200',
    neutral: 'bg-slate-100 text-slate-700 border-slate-200',
  };

  return (
    <div
      className={`bg-white rounded-xl p-5 border shadow-sm transition-all duration-150 ${colorMap[color].border}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-500">{title}</span>
        <div className={`p-2 rounded-lg ${colorMap[color].bg}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>

      <div className="mt-3 flex items-baseline justify-between">
        <span className="text-2xl font-bold tracking-tight text-slate-900">{value}</span>
        {badge && (
          <span
            className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
              badgeColors[badge.variant]
            }`}
          >
            {badge.text}
          </span>
        )}
      </div>

      {subtitle && <p className="mt-1 text-xs text-slate-400">{subtitle}</p>}
    </div>
  );
};
