import React, { useEffect, useState } from 'react';
import {
  DatabaseZap,
  CheckCircle2,
  AlertCircle,
  Clock,
  KeyRound,
  ShieldCheck,
  RefreshCw,
  FileCheck2,
  FileX2,
} from 'lucide-react';
import { PageHeader } from '../../components/admin/PageHeader';
import {
  adminApi,
  AdminIngestionStatusResponse,
  AdminIngestionRunItem,
} from '../../api/admin';

export const AdminIngestionPage: React.FC = () => {
  const [statusData, setStatusData] = useState<AdminIngestionStatusResponse | null>(null);
  const [runs, setRuns] = useState<AdminIngestionRunItem[]>([]);
  const [totalRuns, setTotalRuns] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [componentFilter, setComponentFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [statusRes, runsRes] = await Promise.all([
        adminApi.getAdminIngestionStatus(),
        adminApi.getAdminIngestionRuns({
          component: componentFilter || undefined,
          status: statusFilter || undefined,
          page,
          page_size: pageSize,
        }),
      ]);
      setStatusData(statusRes);
      setRuns(runsRes.items || []);
      setTotalRuns(runsRes.total || 0);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to fetch ingestion monitor diagnostics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page, componentFilter, statusFilter]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'success':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
            <CheckCircle2 className="w-3.5 h-3.5" /> Success
          </span>
        );
      case 'partial':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
            <AlertCircle className="w-3.5 h-3.5" /> Partial
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-100 text-rose-800">
            <AlertCircle className="w-3.5 h-3.5" /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
            <Clock className="w-3.5 h-3.5" /> {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Ingestion Monitor"
        description="Operational health, contract compatibility, and ingestion throughput for C1-C4 ML components."
        actions={
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium border border-slate-300 rounded-lg text-slate-700 bg-white hover:bg-slate-50 transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        }
      />

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-sm">
          {error}
        </div>
      )}

      {/* C1-C4 Health Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {['c1', 'c2', 'c3', 'c4'].map((prefix) => {
          const comp = statusData?.components?.[prefix];
          const titles: Record<string, string> = {
            c1: 'C1 Affective Weekly',
            c2: 'C2 Engagement Trajectory',
            c3: 'C3 Multimodal Risk',
            c4: 'C4 Intervention Recs',
          };
          const title = comp?.title || titles[prefix];

          return (
            <div
              key={prefix}
              className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                    <DatabaseZap className="w-4 h-4 text-indigo-600" />
                    {title}
                  </span>
                  {getStatusBadge(comp?.status || 'idle')}
                </div>

                {/* API Key Status - NEVER exposes secret */}
                <div className="flex items-center justify-between text-xs py-1.5 border-b border-slate-100">
                  <span className="text-slate-500">API Key Config:</span>
                  {comp?.api_key_configured ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                      <ShieldCheck className="w-3 h-3" /> Configured
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
                      <KeyRound className="w-3 h-3" /> Missing Key
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between text-xs py-1.5 border-b border-slate-100">
                  <span className="text-slate-500">Contract Version:</span>
                  <span className="font-semibold text-slate-700">
                    {comp?.contract_version || '1.0.0'}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 my-3 text-center">
                  <div className="p-2 bg-emerald-50/70 rounded-lg border border-emerald-100">
                    <div className="text-[11px] text-emerald-700 font-medium flex items-center justify-center gap-1">
                      <FileCheck2 className="w-3 h-3" /> Accepted
                    </div>
                    <div className="text-base font-bold text-emerald-900">
                      {comp?.records_accepted_total?.toLocaleString() ?? 0}
                    </div>
                  </div>
                  <div className="p-2 bg-rose-50/70 rounded-lg border border-rose-100">
                    <div className="text-[11px] text-rose-700 font-medium flex items-center justify-center gap-1">
                      <FileX2 className="w-3 h-3" /> Rejected
                    </div>
                    <div className="text-base font-bold text-rose-900">
                      {comp?.records_rejected_total?.toLocaleString() ?? 0}
                    </div>
                  </div>
                </div>

                {comp?.last_error && (
                  <div className="p-2 bg-rose-50 border border-rose-200 rounded text-[11px] text-rose-700 truncate" title={comp.last_error}>
                    <strong>Error:</strong> {comp.last_error}
                  </div>
                )}
              </div>

              <div className="text-[11px] text-slate-400 mt-3 pt-2 border-t border-slate-100">
                Last run: {comp?.last_run_at ? new Date(comp.last_run_at).toLocaleString() : 'Never'}
              </div>
            </div>
          );
        })}
      </div>

      {/* Historical Runs Filter & Table */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-wrap gap-4 items-center justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={componentFilter}
            onChange={(e) => {
              setComponentFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Components</option>
            <option value="c1">C1 Affective</option>
            <option value="c2">C2 Trajectory</option>
            <option value="c3">C3 Risk</option>
            <option value="c4">C4 Intervention</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Statuses</option>
            <option value="success">Success</option>
            <option value="partial">Partial</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        <div className="text-xs text-slate-500 font-medium">
          Total Recorded Runs: {totalRuns}
        </div>
      </div>

      {/* Ingestion Runs Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 text-xs uppercase tracking-wider font-semibold">
                <th className="py-3 px-4">Run ID & Component</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Records Processed</th>
                <th className="py-3 px-4">Accepted / Rejected</th>
                <th className="py-3 px-4">Mode & Version</th>
                <th className="py-3 px-4">Started At</th>
                <th className="py-3 px-4">Error Summary</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && runs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-500 mb-2" />
                    Loading ingestion runs...
                  </td>
                </tr>
              ) : runs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    No ingestion runs recorded yet.
                  </td>
                </tr>
              ) : (
                runs.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50 transition">
                    <td className="py-3 px-4 font-medium text-slate-900">
                      <div className="font-mono text-xs">{r.id}</div>
                      <div className="text-xs text-indigo-600 uppercase font-semibold">{r.component}</div>
                    </td>
                    <td className="py-3 px-4">
                      {getStatusBadge(r.status)}
                    </td>
                    <td className="py-3 px-4 text-slate-700 font-medium">
                      {r.records_processed?.toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-xs">
                      <span className="text-emerald-700 font-semibold">{r.records_accepted?.toLocaleString()}</span>
                      {' / '}
                      <span className={r.records_rejected > 0 ? 'text-rose-600 font-bold' : 'text-slate-400'}>
                        {r.records_rejected?.toLocaleString()}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      <div>{r.dry_run ? 'Dry Run' : 'Commit'}</div>
                      <div className="text-slate-400">{r.contract_version || 'v1.0.0'}</div>
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-xs">
                      {r.started_at ? new Date(r.started_at).toLocaleString() : '—'}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500 max-w-xs truncate" title={r.error_message || ''}>
                      {r.error_message ? (
                        <span className="text-rose-600 font-medium">{r.error_message}</span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
