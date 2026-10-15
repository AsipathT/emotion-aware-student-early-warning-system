import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import {
  LayoutDashboard,
  Users,
  GraduationCap,
  UserCheck,
  Scale,
  KeyRound,
  ShieldCheck,
  Workflow,
  DatabaseZap,
  Download,
  Server,
  Activity,
  ArrowLeft,
} from 'lucide-react';

interface AdminSidebarProps {
  onCloseMobile?: () => void;
}

export const AdminSidebar: React.FC<AdminSidebarProps> = ({ onCloseMobile }) => {
  const { user } = useAuth();
  const isAuditor = user?.role === 'auditor';

  const navItems = [
    {
      to: '/admin',
      label: 'Overview',
      icon: LayoutDashboard,
      end: true,
      auditorAllowed: true,
    },
    {
      to: '/admin/users',
      label: 'Users',
      icon: Users,
      auditorAllowed: false,
    },
    {
      to: '/admin/courses',
      label: 'Courses',
      icon: GraduationCap,
      auditorAllowed: true,
    },
    {
      to: '/admin/enrolments',
      label: 'Enrolments',
      icon: UserCheck,
      auditorAllowed: true,
    },
    {
      to: '/admin/consent',
      label: 'Consent & Ethics',
      icon: Scale,
      auditorAllowed: true,
    },
    {
      to: '/admin/privacy',
      label: 'Privacy & Identity',
      icon: KeyRound,
      auditorAllowed: true,
    },
    {
      to: '/admin/audit',
      label: 'Audit Log',
      icon: ShieldCheck,
      auditorAllowed: true,
    },
    {
      to: '/admin/pipeline',
      label: 'Pipeline & Scheduler',
      icon: Workflow,
      auditorAllowed: true,
    },
    {
      to: '/admin/ingestion',
      label: 'Ingestion Monitor',
      icon: DatabaseZap,
      auditorAllowed: true,
    },
    {
      to: '/admin/exports',
      label: 'Data Export',
      icon: Download,
      auditorAllowed: true,
    },
    {
      to: '/admin/system',
      label: 'System & Health',
      icon: Server,
      auditorAllowed: true,
    },
  ];

  const visibleItems = isAuditor
    ? navItems.filter((item) => item.auditorAllowed)
    : navItems;

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col h-full border-r border-slate-800">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 bg-indigo-600 rounded-lg text-white">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <span className="text-base font-bold text-white tracking-tight">
              Admin<span className="text-indigo-400">Panel</span>
            </span>
            <p className="text-[11px] text-slate-400 font-mono tracking-wider">
              {isAuditor ? 'AUDITOR CONSOLE' : 'PLATFORM OPS'}
            </p>
          </div>
        </div>
      </div>

      {/* Navigation List */}
      <div className="flex-1 py-4 px-3 overflow-y-auto space-y-1">
        <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Navigation
        </div>
        {visibleItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onCloseMobile}
              className={({ isActive }) =>
                `flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-sm font-semibold'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="truncate">{item.label}</span>
            </NavLink>
          );
        })}
      </div>

      {/* Footer Return Link */}
      <div className="p-4 border-t border-slate-800">
        <NavLink
          to="/"
          className="flex items-center space-x-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Exit to Student/Lecturer LMS</span>
        </NavLink>
      </div>
    </aside>
  );
};
