import React, { useEffect, useState } from 'react';
import {
  Activity,
  Database,
  FileCode2,
  GitCommit,
  Terminal,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
} from 'lucide-react';
import { PageHeader } from '../../components/admin/PageHeader';
import {
  adminApi,
  AdminSystemHealthResponse,
} from '../../api/admin';

export const AdminSystemPage: React.FC = () => {
  const [health, setHealth] = useState<AdminSystemHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const fetchHealth = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await adminApi.getAdminSystemHealth();
      setHealth(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to fetch system diagnostics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  const handleCopyCli = () => {
    if (!health?.oulad_status?.cli_command) return;
    navigator.clipboard.writeText(health.oulad_status.cli_command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="System & Platform Health"
        description="Platform infrastructure, database latency, schema migrations, and contract schemas."
        actions={
          <button
            onClick={fetchHealth}
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

      {/* Top Diagnostic KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span>Overall Status</span>
            <Activity className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-xl font-bold text-slate-900 capitalize flex items-center gap-1.5">
            {health?.status === 'healthy' ? (
              <span className="text-emerald-700 flex items-center gap-1">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" /> Healthy
              </span>
            ) : (
              <span className="text-amber-700 flex items-center gap-1">
                <AlertCircle className="w-5 h-5 text-amber-600" /> {health?.status || 'Unknown'}
              </span>
            )}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Platform operational</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span>Database Latency</span>
            <Database className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-xl font-bold text-slate-900 font-mono">
            {health?.db_ping_ms !== undefined ? `${health.db_ping_ms} ms` : '—'}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Round-trip ping time</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span>Contract Version</span>
            <FileCode2 className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-xl font-bold text-slate-900 font-mono">
            v{health?.contract_version || '1.0.0'}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Feature 24 Data Contract</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span>Applied Migrations</span>
            <GitCommit className="w-4 h-4 text-purple-600" />
          </div>
          <div className="text-xl font-bold text-slate-900">
            {health?.total_migrations_applied ?? 0}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">schema_migrations tracked</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Schema Migrations Table */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
              <GitCommit className="w-4 h-4 text-purple-600" /> Applied Schema Migrations
            </h3>
            <span className="text-xs text-slate-400 font-medium">
              {health?.applied_migrations?.length ?? 0} applied
            </span>
          </div>

          <div className="overflow-x-auto max-h-80 overflow-y-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-semibold">
                  <th className="py-2.5 px-4">Migration ID</th>
                  <th className="py-2.5 px-4">Applied At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {health?.applied_migrations?.map((m) => (
                  <tr key={m.migration_id} className="hover:bg-slate-50">
                    <td className="py-2.5 px-4 font-mono font-medium text-slate-800">
                      {m.migration_id}
                    </td>
                    <td className="py-2.5 px-4 text-slate-500">
                      {new Date(m.applied_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Contract Schemas */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
              <FileCode2 className="w-4 h-4 text-blue-600" /> Feature 24 Contract Schemas
            </h3>
            <span className="text-xs text-slate-400 font-medium">Strict JSON Models</span>
          </div>

          <p className="text-xs text-slate-500">
            All data exchanging between LMS and ML components (C1-C4) conforms to these validated schemas:
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
            {health?.contract_schemas?.map((s) => (
              <div
                key={s}
                className="p-2.5 bg-slate-50 rounded-lg border border-slate-200/70 text-xs font-mono font-medium text-slate-800 flex items-center gap-2"
              >
                <div className="w-2 h-2 rounded-full bg-indigo-500" />
                {s}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* OULAD Dataset Import Status */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">OULAD Benchmark Dataset Import Status</h3>
              <p className="text-xs text-slate-500">
                Open University Learning Analytics Dataset (OULAD) integration for model training and benchmark evaluations.
              </p>
            </div>
          </div>
          <span
            className={`inline-flex items-center gap-1 px-3 py-1 text-xs rounded-full font-semibold uppercase tracking-wider ${
              health?.oulad_status?.is_imported
                ? 'bg-emerald-100 text-emerald-800'
                : 'bg-slate-100 text-slate-700'
            }`}
          >
            {health?.oulad_status?.is_imported ? 'Imported' : 'Not Imported'}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-xs text-slate-500">Imported Students</span>
            <div className="text-lg font-bold text-slate-800">
              {health?.oulad_status?.imported_students?.toLocaleString() ?? 0}
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-xs text-slate-500">Imported Courses</span>
            <div className="text-lg font-bold text-slate-800">
              {health?.oulad_status?.imported_courses?.toLocaleString() ?? 0}
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-xs text-slate-500">Imported Enrolments</span>
            <div className="text-lg font-bold text-slate-800">
              {health?.oulad_status?.imported_enrolments?.toLocaleString() ?? 0}
            </div>
          </div>
        </div>

        <div className="space-y-2 pt-2">
          <div className="flex items-center justify-between text-xs text-slate-600">
            <span className="font-semibold">CLI Import Command (Run on Server Console):</span>
            <button
              onClick={handleCopyCli}
              className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 font-medium"
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied' : 'Copy Command'}
            </button>
          </div>
          <pre className="p-3 bg-slate-900 text-emerald-400 rounded-lg text-xs font-mono overflow-x-auto">
            {health?.oulad_status?.cli_command || 'python -m app.importers.oulad.cli --data-dir <path>'}
          </pre>
          <p className="text-[11px] text-slate-400 italic">
            Note: For data safety and memory management, OULAD dataset imports must be executed via the server CLI rather than via the browser UI.
          </p>
        </div>
      </div>
    </div>
  );
};
