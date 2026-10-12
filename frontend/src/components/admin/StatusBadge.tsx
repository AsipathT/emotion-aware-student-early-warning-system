import React from 'react';
import { UserRole } from '../../api/auth';

interface StatusBadgeProps {
  status?: 'active' | 'suspended' | 'published' | 'draft' | boolean;
  role?: UserRole | string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, role, size = 'sm' }) => {
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';

  if (status !== undefined) {
    if (status === 'published' || status === 'draft') {
      const isPub = status === 'published';
      return (
        <span
          className={`inline-flex items-center font-medium rounded-full ${sizeClasses} ${
            isPub
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              : 'bg-amber-50 text-amber-700 border border-amber-200'
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
              isPub ? 'bg-emerald-500' : 'bg-amber-500'
            }`}
          />
          {isPub ? 'Published' : 'Draft'}
        </span>
      );
    }

    const isActive = typeof status === 'boolean' ? status : status === 'active';
    return (
      <span
        className={`inline-flex items-center font-medium rounded-full ${sizeClasses} ${
          isActive
            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
            : 'bg-rose-50 text-rose-700 border border-rose-200'
        }`}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
            isActive ? 'bg-emerald-500' : 'bg-rose-500'
          }`}
        />
        {isActive ? 'Active' : 'Suspended'}
      </span>
    );
  }

  if (role) {
    const roleLower = String(role).toLowerCase();
    let colorClass = 'bg-slate-100 text-slate-700 border-slate-200';

    if (roleLower === 'admin') {
      colorClass = 'bg-purple-50 text-purple-700 border-purple-200';
    } else if (roleLower === 'auditor') {
      colorClass = 'bg-indigo-50 text-indigo-700 border-indigo-200';
    } else if (roleLower === 'lecturer') {
      colorClass = 'bg-blue-50 text-blue-700 border-blue-200';
    } else if (roleLower === 'counsellor') {
      colorClass = 'bg-amber-50 text-amber-700 border-amber-200';
    } else if (roleLower === 'student') {
      colorClass = 'bg-sky-50 text-sky-700 border-sky-200';
    }

    return (
      <span
        className={`inline-flex items-center font-medium uppercase tracking-wider rounded-md border ${sizeClasses} ${colorClass}`}
      >
        {roleLower}
      </span>
    );
  }

  return null;
};
