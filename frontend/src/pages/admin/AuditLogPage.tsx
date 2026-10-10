import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  auditApi,
  AuditAction,
  AuditOutcome,
  AuditLogEntry,
  AuditFilterParams,
} from '../../api/audit';
import {
  ShieldCheck,
  Search,
  Download,
  Filter,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  X,
  Terminal,
} from 'lucide-react';


const ACTION_OPTIONS: { label: string; value: AuditAction | '' }[] = [
  { label: 'All Actions', value: '' },
  { label: 'LOGIN_SUCCESS', value: 'LOGIN_SUCCESS' },
  { label: 'LOGIN_FAILED', value: 'LOGIN_FAILED' },
  { label: 'ACCESS_DENIED', value: 'ACCESS_DENIED' },
  { label: 'IDENTITY_REVEAL', value: 'IDENTITY_REVEAL' },
  { label: 'CONSENT_ACCEPTED', value: 'CONSENT_ACCEPTED' },
  { label: 'CONSENT_DECLINED', value: 'CONSENT_DECLINED' },
  { label: 'CONSENT_WITHDRAWN', value: 'CONSENT_WITHDRAWN' },
  { label: 'AUDIT_LOG_VIEWED', value: 'AUDIT_LOG_VIEWED' },
  { label: 'EXPORT_GENERATED', value: 'EXPORT_GENERATED' },
];

const OUTCOME_OPTIONS: { label: string; value: AuditOutcome | '' }[] = [
  { label: 'All Outcomes', value: '' },
  { label: 'Success', value: 'success' },
  { label: 'Failed', value: 'failed' },
  { label: 'Denied', value: 'denied' },
];

export const AuditLogPage: React.FC = () => {
  const [page, setPage] = useState(1);
  const limit = 15;

  // Filter states
  const [action, setAction] = useState<AuditAction | ''>('');
  const [outcome, setOutcome] = useState<AuditOutcome | ''>('');
  const [actorId, setActorId] = useState('');
  const [targetId, setTargetId] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // Selected entry for details inspection modal
  const [selectedEntry, setSelectedEntry] = useState<AuditLogEntry | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const queryFilters: AuditFilterParams = {
    action,
    outcome,
    actor_id: actorId,
    target_id: targetId,
    start_date: startDate ? new Date(startDate).toISOString() : undefined,
    end_date: endDate ? new Date(endDate + 'T23:59:59Z').toISOString() : undefined,
    page,
    limit,
  };

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['auditLogs', queryFilters],
    queryFn: () => auditApi.queryAuditLogs(queryFilters),
  });

  const handleClearFilters = () => {
    setAction('');
    setOutcome('');
    setActorId('');
    setTargetId('');
    setStartDate('');
    setEndDate('');
    setPage(1);
  };

  const handleExportCsv = async () => {
    setIsExporting(true);
    setExportError(null);
    try {
      await auditApi.downloadAuditExport({
        action,
        outcome,
        actor_id: actorId,
        target_id: targetId,
        start_date: startDate ? new Date(startDate).toISOString() : undefined,
        end_date: endDate ? new Date(endDate + 'T23:59:59Z').toISOString() : undefined,
      });
    } catch (err: any) {
      setExportError(
        err?.response?.data?.detail || 'Failed to export audit logs. Please try again.'
      );
    } finally {
      setIsExporting(false);
    }
  };

  const getActionBadgeColor = (actionName: AuditAction) => {
    switch (actionName) {
      case 'IDENTITY_REVEAL':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'ACCESS_DENIED':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'LOGIN_FAILED':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'LOGIN_SUCCESS':
      case 'CONSENT_ACCEPTED':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'CONSENT_WITHDRAWN':
        return 'bg-orange-50 text-orange-700 border-orange-200';
      case 'EXPORT_GENERATED':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  const getOutcomeBadge = (outcomeVal: AuditOutcome) => {
    switch (outcomeVal) {
      case 'success':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-600" />
            Success
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle className="w-3 h-3 mr-1 text-rose-600" />
            Failed
          </span>
        );
      case 'denied':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3 h-3 mr-1 text-amber-600" />
            Denied
          </span>
        );
      default:
        return <span>{outcomeVal}</span>;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header Banner */}
      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="p-3 bg-indigo-50 border border-indigo-100/80 rounded-2xl text-indigo-600">
            <ShieldCheck className="w-7 h-7" />
          </div>
          <div>
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Compliance & Security Audit Log
            </h1>
            <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
              Append-only, tamper-resistant trail of sensitive actions, pseudonym reveal events, and access checks.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3 w-full sm:w-auto">
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="p-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl transition focus:outline-none"
            title="Refresh log"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin text-indigo-600' : ''}`} />
          </button>

          <button
            type="button"
            onClick={handleExportCsv}
            disabled={isExporting}
            className="flex-1 sm:flex-initial inline-flex items-center justify-center px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-xl shadow-sm hover:shadow transition disabled:opacity-50 space-x-2"
          >
            {isExporting ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {exportError && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start space-x-3 text-xs">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
          <span>{exportError}</span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-slate-100">
          <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-slate-600">
            <Filter className="w-4 h-4 text-indigo-600" />
            <span>Filter Criteria</span>
          </div>
          <button
            type="button"
            onClick={handleClearFilters}
            className="text-xs font-medium text-indigo-600 hover:text-indigo-800 transition"
          >
            Reset Filters
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
          {/* Action Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Action
            </label>
            <select
              value={action}
              onChange={(e) => {
                setAction(e.target.value as AuditAction | '');
                setPage(1);
              }}
              className="w-full py-2 px-3 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            >
              {ACTION_OPTIONS.map((opt) => (
                <option key={opt.label} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Outcome Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Outcome
            </label>
            <select
              value={outcome}
              onChange={(e) => {
                setOutcome(e.target.value as AuditOutcome | '');
                setPage(1);
              }}
              className="w-full py-2 px-3 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            >
              {OUTCOME_OPTIONS.map((opt) => (
                <option key={opt.label} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Actor ID */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Actor ID
            </label>
            <input
              type="text"
              value={actorId}
              onChange={(e) => {
                setActorId(e.target.value);
                setPage(1);
              }}
              placeholder="e.g. anonymous or UUID"
              className="w-full py-2 px-3 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 font-mono"
            />
          </div>

          {/* Target ID (PID) */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Target ID / PID
            </label>
            <input
              type="text"
              value={targetId}
              onChange={(e) => {
                setTargetId(e.target.value);
                setPage(1);
              }}
              placeholder="e.g. STU_xxxxxxxx"
              className="w-full py-2 px-3 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 font-mono"
            />
          </div>

          {/* Date Range Start */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              From Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(1);
              }}
              className="w-full py-2 px-3 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </div>

          {/* Date Range End */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              To Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setPage(1);
              }}
              className="w-full py-2 px-3 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </div>
        </div>
      </div>

      {/* Main Table Container */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center space-y-3">
            <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-500 font-medium">Retrieving audit events...</p>
          </div>
        ) : isError ? (
          <div className="p-8 text-center space-y-2">
            <AlertCircle className="w-8 h-8 text-rose-500 mx-auto" />
            <h3 className="font-bold text-slate-900 text-sm">Failed to load audit logs</h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              {(error as any)?.response?.data?.detail ||
                'Access denied or unable to reach audit repository.'}
            </p>
          </div>
        ) : !data?.items || data.items.length === 0 ? (
          <div className="py-16 text-center space-y-2">
            <div className="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto text-slate-400">
              <Search className="w-6 h-6" />
            </div>
            <h3 className="font-bold text-slate-900 text-sm">No audit records found</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              No events matched the selected filter parameters. Try broadening your criteria.
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50/80 border-b border-slate-200 text-slate-500 uppercase tracking-wider text-[11px] font-semibold">
                  <tr>
                    <th scope="col" className="px-5 py-3.5">
                      Timestamp (UTC)
                    </th>
                    <th scope="col" className="px-5 py-3.5">
                      Actor
                    </th>
                    <th scope="col" className="px-5 py-3.5">
                      Action
                    </th>
                    <th scope="col" className="px-5 py-3.5">
                      Target
                    </th>
                    <th scope="col" className="px-5 py-3.5">
                      Outcome
                    </th>
                    <th scope="col" className="px-5 py-3.5">
                      Justification Reason
                    </th>
                    <th scope="col" className="px-5 py-3.5 text-right">
                      Details
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map((entry) => (
                    <tr
                      key={entry.id}
                      className="hover:bg-slate-50/60 transition-colors"
                    >
                      {/* Timestamp */}
                      <td className="px-5 py-3.5 whitespace-nowrap text-slate-600 font-mono text-[11px]">
                        {new Date(entry.timestamp).toLocaleString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </td>

                      {/* Actor */}
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <div className="flex flex-col">
                          <span
                            className="font-mono text-slate-800 text-[11px] truncate max-w-[120px]"
                            title={entry.actor_id}
                          >
                            {entry.actor_id}
                          </span>
                          <span className="text-[10px] uppercase font-bold text-slate-400">
                            {entry.actor_role}
                          </span>
                        </div>
                      </td>

                      {/* Action */}
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase border ${getActionBadgeColor(
                            entry.action
                          )}`}
                        >
                          {entry.action}
                        </span>
                      </td>

                      {/* Target */}
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        {entry.target_id ? (
                          <div className="flex flex-col">
                            <span className="font-mono text-[11px] text-purple-700 font-semibold">
                              {entry.target_id}
                            </span>
                            {entry.target_type && (
                              <span className="text-[10px] uppercase text-slate-400 font-medium">
                                {entry.target_type}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-400">&mdash;</span>
                        )}
                      </td>

                      {/* Outcome */}
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        {getOutcomeBadge(entry.outcome)}
                      </td>

                      {/* Reason */}
                      <td className="px-5 py-3.5 max-w-[200px]">
                        {entry.reason ? (
                          <span
                            className="truncate block text-slate-700 text-xs"
                            title={entry.reason}
                          >
                            {entry.reason}
                          </span>
                        ) : (
                          <span className="text-slate-400">&mdash;</span>
                        )}
                      </td>

                      {/* View Details */}
                      <td className="px-5 py-3.5 text-right whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => setSelectedEntry(entry)}
                          className="px-2.5 py-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Bar */}
            <div className="px-5 py-3.5 border-t border-slate-100 bg-slate-50/50 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-600">
              <div>
                Showing{' '}
                <span className="font-semibold text-slate-900">
                  {Math.min((page - 1) * limit + 1, data.total)}
                </span>{' '}
                to{' '}
                <span className="font-semibold text-slate-900">
                  {Math.min(page * limit, data.total)}
                </span>{' '}
                of <span className="font-semibold text-slate-900">{data.total}</span> entries
              </div>

              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(p - 1, 1))}
                  className="p-1.5 rounded-lg border border-slate-300 hover:bg-white text-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="font-mono text-xs px-2">
                  Page {data.page} of {data.pages || 1}
                </span>
                <button
                  type="button"
                  disabled={page >= data.pages}
                  onClick={() => setPage((p) => p + 1)}
                  className="p-1.5 rounded-lg border border-slate-300 hover:bg-white text-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Audit Detail Inspection Drawer / Modal */}
      {selectedEntry && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in"
          onClick={() => setSelectedEntry(null)}
        >
          <div
            className="bg-white w-full max-w-xl rounded-2xl shadow-2xl border border-slate-200 overflow-hidden space-y-4 animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
              <div className="flex items-center space-x-2">
                <Terminal className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900 text-sm">
                  Audit Event Details
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedEntry(null)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="px-6 py-2 space-y-3 max-h-[70vh] overflow-y-auto text-xs text-slate-700">
              <div className="grid grid-cols-2 gap-3 p-3 bg-slate-50 rounded-xl font-mono text-[11px]">
                <div>
                  <span className="text-slate-400 block uppercase text-[10px]">Event ID</span>
                  <span className="text-slate-800 break-all">{selectedEntry.id}</span>
                </div>
                <div>
                  <span className="text-slate-400 block uppercase text-[10px]">Correlation Request ID</span>
                  <span className="text-slate-800 break-all">{selectedEntry.request_id}</span>
                </div>
                <div>
                  <span className="text-slate-400 block uppercase text-[10px]">Client IP</span>
                  <span className="text-slate-800">{selectedEntry.ip_address}</span>
                </div>
                <div>
                  <span className="text-slate-400 block uppercase text-[10px]">Actor & Role</span>
                  <span className="text-slate-800">
                    {selectedEntry.actor_id} ({selectedEntry.actor_role})
                  </span>
                </div>
              </div>

              <div>
                <span className="text-slate-400 block uppercase text-[10px] mb-1 font-semibold">
                  User Agent
                </span>
                <p className="p-2.5 bg-slate-50 rounded-xl text-slate-600 font-mono text-[11px] break-words">
                  {selectedEntry.user_agent}
                </p>
              </div>

              {selectedEntry.reason && (
                <div>
                  <span className="text-slate-400 block uppercase text-[10px] mb-1 font-semibold">
                    Justification Reason
                  </span>
                  <p className="p-2.5 bg-amber-50/70 border border-amber-200/60 rounded-xl text-amber-900 text-xs">
                    {selectedEntry.reason}
                  </p>
                </div>
              )}

              <div>
                <span className="text-slate-400 block uppercase text-[10px] mb-1 font-semibold">
                  Sanitized Metadata (`details`)
                </span>
                <pre className="p-3 bg-slate-900 text-emerald-400 rounded-xl font-mono text-[11px] overflow-x-auto">
                  {JSON.stringify(selectedEntry.details || {}, null, 2)}
                </pre>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-slate-100 bg-slate-50/50 flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedEntry(null)}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 text-xs font-semibold rounded-xl transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AuditLogPage;
