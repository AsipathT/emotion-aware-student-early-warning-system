import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { adminApi, AdminOverviewResponse } from '../../api/admin';
import { StatCard } from '../../components/admin/StatCard';
import { PageHeader } from '../../components/admin/PageHeader';
import { StatusBadge } from '../../components/admin/StatusBadge';
import {
  Users,
  GraduationCap,
  UserCheck,
  Scale,
  Workflow,
  Server,
  RefreshCw,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

export const AdminOverviewPage: React.FC = () => {
  const {
    data: overview,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery<AdminOverviewResponse>({
    queryKey: ['admin', 'overview'],
    queryFn: adminApi.getAdminOverview,
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin" />
        <p className="text-sm text-slate-500 font-medium">Loading platform metrics...</p>
      </div>
    );
  }

  if (isError || !overview) {
    return (
      <div className="bg-rose-50 border border-rose-200 rounded-xl p-6 text-center max-w-xl mx-auto my-12">
        <AlertCircle className="w-10 h-10 text-rose-500 mx-auto mb-3" />
        <h3 className="text-base font-semibold text-rose-900">Failed to load platform overview</h3>
        <p className="text-sm text-rose-600 mt-1">
          {(error as any)?.response?.data?.detail || 'An unexpected error occurred connecting to admin services.'}
        </p>
        <button
          onClick={() => refetch()}
          className="mt-4 px-4 py-2 bg-rose-600 text-white rounded-lg text-sm font-medium hover:bg-rose-700 transition"
        >
          Try Again
        </button>
      </div>
    );
  }

  // Chart data: User roles
  const roleChartData = Object.entries(overview.users_by_role || {}).map(([role, count]) => ({
    name: role.charAt(0).toUpperCase() + role.slice(1),
    count,
  }));

  // Chart data: Consent
  const consentChartData = [
    { name: 'Accepted', value: overview.consent_coverage.accepted, color: '#10b981' },
    { name: 'Pending', value: overview.consent_coverage.pending, color: '#f59e0b' },
    { name: 'Withdrawn', value: overview.consent_coverage.withdrawn, color: '#ef4444' },
    { name: 'Declined', value: overview.consent_coverage.declined, color: '#64748b' },
  ].filter((item) => item.value > 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Governance & Operations"
        description="Real-time observability of LMS foundation, privacy safeguards, and machine-learning ingestion pipelines."
        actions={
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center space-x-2 px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition shadow-xs"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin text-indigo-600' : ''}`} />
            <span>Refresh Metrics</span>
          </button>
        }
      />

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard
          title="Total Users"
          value={overview.total_users}
          subtitle={`${overview.active_users} active / ${overview.suspended_users} suspended`}
          icon={Users}
          color="indigo"
        />

        <StatCard
          title="Courses"
          value={overview.total_courses}
          subtitle={`${overview.published_courses} published / ${overview.draft_courses} draft`}
          icon={GraduationCap}
          color="purple"
        />

        <StatCard
          title="Total Enrolments"
          value={overview.total_enrolments}
          subtitle="Active academic enrolments"
          icon={UserCheck}
          color="emerald"
        />

        <StatCard
          title="Consent Coverage"
          value={`${overview.consent_coverage.coverage_percentage}%`}
          subtitle={`${overview.consent_coverage.accepted} of ${overview.consent_coverage.total_students} students`}
          icon={Scale}
          color="amber"
          badge={{
            text: overview.consent_coverage.coverage_percentage >= 80 ? 'Optimal' : 'Needs Notice',
            variant: overview.consent_coverage.coverage_percentage >= 80 ? 'positive' : 'neutral',
          }}
        />

        <StatCard
          title="Pipeline Health"
          value={overview.pipeline_summary.latest_run?.overall_status?.toUpperCase() || 'IDLE'}
          subtitle={
            overview.pipeline_summary.latest_run
              ? `Week ${overview.pipeline_summary.latest_run.week_index} (${overview.pipeline_summary.latest_run.current_stage})`
              : 'No active runs'
          }
          icon={Workflow}
          color="sky"
        />

        <StatCard
          title="Database Ping"
          value={`${overview.database_health.ping_ms} ms`}
          subtitle={`Status: ${overview.database_health.status}`}
          icon={Server}
          color={overview.database_health.ping_ms >= 0 ? 'emerald' : 'rose'}
        />
      </div>

      {/* Analytics Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* User Distribution Chart */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <h3 className="text-base font-semibold text-slate-900 mb-1">User Account Distribution</h3>
          <p className="text-xs text-slate-500 mb-4">Total platform accounts categorized by access role.</p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={roleChartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#64748b' }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    borderRadius: '8px',
                    color: '#fff',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Consent Breakdown Chart */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <h3 className="text-base font-semibold text-slate-900 mb-1">Consent Compliance Posture</h3>
          <p className="text-xs text-slate-500 mb-4">Student ethics posture under current active notice.</p>
          <div className="h-64 w-full">
            {consentChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={consentChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {consentChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      borderRadius: '8px',
                      color: '#fff',
                      fontSize: '12px',
                    }}
                  />
                  <Legend
                    verticalAlign="bottom"
                    iconType="circle"
                    wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-sm text-slate-400">
                No consent records recorded yet.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ML Component Ingestion Status Cards */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900">
              ML Pipeline Component Health (C1 - C4)
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Status of downstream machine-learning models submitting outputs via Feature 23 ingestion endpoints.
            </p>
          </div>
          <Link
            to="/admin/ingestion"
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center space-x-1"
          >
            <span>View Ingestion Monitor</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { key: 'c1', label: 'C1: Affective State', desc: 'NLP text analysis vectors' },
            { key: 'c2', label: 'C2: Trajectory Analysis', desc: 'Longitudinal engagement trends' },
            { key: 'c3', label: 'C3: Multimodal Risk', desc: 'BiLSTM early-warning risk scores' },
            { key: 'c4', label: 'C4: Recommendations', desc: 'Personalized action guidance' },
          ].map(({ key, label, desc }) => {
            const compData = overview.ingestion_summary?.[key];
            return (
              <div
                key={key}
                className="p-4 rounded-lg border border-slate-100 bg-slate-50/70 hover:bg-slate-50 transition"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-slate-900">{label}</span>
                  <span
                    className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
                      compData?.configured
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-slate-200 text-slate-600'
                    }`}
                  >
                    {compData?.configured ? 'Key Active' : 'Unset'}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 mb-3">{desc}</p>
                <div className="text-xs flex justify-between text-slate-600">
                  <span>Last status:</span>
                  <span className="font-medium text-slate-900">{compData?.status || 'Never run'}</span>
                </div>
                <div className="text-xs flex justify-between text-slate-600 mt-1">
                  <span>Processed:</span>
                  <span className="font-semibold text-slate-900">
                    {compData?.records_processed || 0} records
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent Security & Compliance Audit Events */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-5 h-5 text-indigo-600" />
            <div>
              <h3 className="text-base font-semibold text-slate-900">Recent Security Audit Trail</h3>
              <p className="text-xs text-slate-500">
                Immutable compliance log entries recording platform access, reveals, and state mutations.
              </p>
            </div>
          </div>
          <Link
            to="/admin/audit"
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center space-x-1"
          >
            <span>Full Audit Log</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-medium">
              <tr>
                <th className="py-2.5 px-3">Timestamp (UTC)</th>
                <th className="py-2.5 px-3">Action</th>
                <th className="py-2.5 px-3">Actor ID</th>
                <th className="py-2.5 px-3">Role</th>
                <th className="py-2.5 px-3">Target</th>
                <th className="py-2.5 px-3">Outcome</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {overview.recent_audit_events?.length > 0 ? (
                overview.recent_audit_events.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/80 transition">
                    <td className="py-2.5 px-3 font-mono text-[11px] text-slate-500 whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-slate-900 whitespace-nowrap">
                      {log.action}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-slate-600 whitespace-nowrap">
                      {log.actor_id}
                    </td>
                    <td className="py-2.5 px-3">
                      <StatusBadge role={log.actor_role} size="sm" />
                    </td>
                    <td className="py-2.5 px-3 font-mono text-slate-600">
                      {log.target_id || log.target_type || '—'}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                          log.outcome === 'success'
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {log.outcome}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="text-center py-6 text-slate-400">
                    No recent audit events found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
