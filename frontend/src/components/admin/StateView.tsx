import React from 'react';
import { AlertCircle, FolderOpen, RefreshCw } from 'lucide-react';

interface LoadingStateProps {
  label?: string;
  minHeight?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  label = 'Loading data...',
  minHeight = 'min-h-[240px]',
}) => {
  return (
    <div className={`flex flex-col items-center justify-center ${minHeight} p-8 text-center`}>
      <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mb-3" />
      <span className="text-xs font-medium text-slate-500">{label}</span>
    </div>
  );
};

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  minHeight?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  minHeight = 'min-h-[220px]',
}) => {
  return (
    <div className={`flex flex-col items-center justify-center ${minHeight} p-8 text-center bg-slate-50/50 rounded-xl border border-dashed border-slate-200`}>
      <div className="p-3 bg-white rounded-xl shadow-xs border border-slate-100 text-slate-400 mb-3">
        {icon || <FolderOpen className="w-6 h-6" />}
      </div>
      <h4 className="text-xs font-bold text-slate-800 mb-1">{title}</h4>
      <p className="text-xs text-slate-500 max-w-sm mb-4 leading-relaxed">{description}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="px-3.5 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-xs transition"
        >
          {action.label}
        </button>
      )}
    </div>
  );
};

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Failed to load data',
  message,
  onRetry,
}) => {
  return (
    <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 flex items-start justify-between gap-3 text-xs">
      <div className="flex items-start gap-2.5">
        <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
        <div>
          <h4 className="font-bold text-rose-900">{title}</h4>
          <p className="text-rose-700 mt-0.5">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1 px-3 py-1 bg-white hover:bg-rose-100/50 border border-rose-300 text-rose-700 rounded-lg font-medium transition shrink-0 shadow-xs"
        >
          <RefreshCw className="w-3 h-3" />
          Retry
        </button>
      )}
    </div>
  );
};
