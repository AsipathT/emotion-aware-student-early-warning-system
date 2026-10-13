import React from 'react';
import { NavLink } from 'react-router-dom';
import { Users, Sparkles, Lightbulb } from 'lucide-react';
import { HeartHandshake } from 'lucide-react';

export interface StaffTabItem {
  label: string;
  to: string;
  icon?: React.ComponentType<{ className?: string }>;
}

export const STAFF_TABS: StaffTabItem[] = [
  { label: 'Students', to: '/staff/students', icon: Users },
  { label: 'Affective', to: '/staff/affective', icon: Sparkles },
  { label: 'Recommendations', to: '/staff/recommendations', icon: Lightbulb },
  { label: 'Interventions', to: '/staff/interventions', icon: HeartHandshake },
  // Dushan: append one entry per staff feature (F31..F38)
];

export const StaffTabs: React.FC = () => {
  return (
    <div className="border-b border-slate-200 mb-6">
      <nav className="flex space-x-2" aria-label="Staff Workspace Tabs">
        {STAFF_TABS.map((tab) => {
          const IconComponent = tab.icon || Sparkles;
          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                `inline-flex items-center gap-2 py-2.5 px-4 text-sm font-medium rounded-t-lg border-b-2 transition ${
                  isActive
                    ? 'border-indigo-600 text-indigo-600 bg-indigo-50/50 font-semibold'
                    : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                }`
              }
            >
              <IconComponent className="w-4 h-4" />
              {tab.label}
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
};
