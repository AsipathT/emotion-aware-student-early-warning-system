import React, { useEffect, useState } from 'react';
import {
  Play,
  RotateCw,
  CheckCircle2,
  AlertCircle,
  PauseCircle,
  Eye,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';
import { PageHeader } from '../../components/admin/PageHeader';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import { useAuth } from '../../hooks/useAuth';
import {
  adminApi,
  PipelineRunStorage,
  PipelineTriggerPayload,
} from '../../api/admin';

export const AdminPipelinePage: React.FC = () => {
  const { user } = useAuth();
  const isAuditor = user?.role === 'auditor';

  const [runs, setRuns] = useState<PipelineRunStorage[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [courseFilter, setCourseFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [weekFilter, setWeekFilter] = useState<string>('');

  // Modals & Dialogs
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);
  const [triggerPayload, setTriggerPayload] = useState<PipelineTriggerPayload>({
    course_id: '',
    week_index: 0,
    force: false,
  });
  const [triggerConfirmOpen, setTriggerConfirmOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Run detail modal
  const [selectedRun, setSelectedRun] = useState<PipelineRunStorage | null>(null);

  // Advance confirm
  const [advanceConfirmOpen, setAdvanceConfirmOpen] = useState(false);
  const [runToAdvance, setRunToAdvance] = useState<PipelineRunStorage | null>(null);

  const fetchRuns = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await adminApi.getPipelineRuns({
        course_id: courseFilter.trim() || undefined,
        week_index: weekFilter ? parseInt(weekFilter, 10) : undefined,
        status: statusFilter || undefined,
        page,
        page_size: pageSize,
      });
      setRuns(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to fetch pipeline execution runs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, [page, courseFilter, statusFilter, weekFilter]);

  const handleTriggerSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!triggerPayload.course_id.trim()) return;
    setTriggerConfirmOpen(true);
  };

  const executeTrigger = async () => {
    try {
      setActionLoading(true);
      await adminApi.triggerPipelineRun({
        course_id: triggerPayload.course_id.trim(),
        week_index: Number(triggerPayload.week_index),
        force: triggerPayload.force,
      });
      setTriggerConfirmOpen(false);
      setTriggerModalOpen(false);
      setTriggerPayload({ course_id: '', week_index: 0, force: false });
      await fetchRuns();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to trigger pipeline run.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleAdvanceClick = (run: PipelineRunStorage) => {
    setRunToAdvance(run);
    setAdvanceConfirmOpen(true);
  };

  const executeAdvance = async () => {
    if (!runToAdvance) return;
    try {
      setActionLoading(true);
      await adminApi.advancePipelineRun(runToAdvance.course_id, runToAdvance.week_index);
      setAdvanceConfirmOpen(false);
      setRunToAdvance(null);
      await fetchRuns();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to advance pipeline run.');
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'complete':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
            <CheckCircle2 className="w-3.5 h-3.5" /> Complete
          </span>
        );
      case 'running':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 animate-pulse">
            <RotateCw className="w-3.5 h-3.5 animate-spin" /> Running
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
            <PauseCircle className="w-3.5 h-3.5" /> {status}
          </span>
        );
    }
  };

  const getStageIndicator = (name: string, stageInfo?: { status: string }) => {
    const s = stageInfo?.status || 'pending';
    let colorClass = 'bg-slate-200 text-slate-600 border-slate-300';
    if (s === 'complete') colorClass = 'bg-emerald-100 text-emerald-800 border-emerald-300 font-semibold';
    else if (s === 'running') colorClass = 'bg-blue-100 text-blue-800 border-blue-400 font-semibold animate-pulse';
    else if (s === 'failed') colorClass = 'bg-rose-100 text-rose-800 border-rose-300 font-semibold';

    return (
      <span
        title={`${name}: ${s}`}
        className={`px-2 py-0.5 text-[11px] rounded border ${colorClass}`}
      >
        {name}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pipeline & Orchestrator"
        description="Manage longitudinal weekly aggregation and stage progression across C1-C4 ML components."
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={fetchRuns}
              disabled={loading}
              className="p-2 text-slate-600 hover:text-slate-900 border border-slate-300 rounded-lg hover:bg-slate-50 transition"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={() => setTriggerModalOpen(true)}
              disabled={isAuditor}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg text-white transition ${
                isAuditor
                  ? 'bg-slate-400 cursor-not-allowed opacity-60'
                  : 'bg-indigo-600 hover:bg-indigo-700 shadow-sm'
              }`}
              title={isAuditor ? 'Auditor role is strictly read-only' : 'Trigger pipeline run'}
            >
              <Play className="w-4 h-4" />
              Trigger Run
            </button>
          </div>
        }
      />

      {isAuditor && (
        <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-sm">
          <ShieldAlert className="w-5 h-5 flex-shrink-0 text-amber-600" />
          <span>
            <strong>Auditor Mode (Read-Only):</strong> You can monitor stage progression and pipeline run diagnostics. Manual trigger and advance actions are restricted to Platform Administrators.
          </span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-wrap gap-4 items-center justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <input
              type="text"
              placeholder="Filter by Course ID..."
              value={courseFilter}
              onChange={(e) => {
                setCourseFilter(e.target.value);
                setPage(1);
              }}
              className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 w-44"
            />
          </div>
          <div className="relative">
            <input
              type="number"
              min="0"
              placeholder="Week Index..."
              value={weekFilter}
              onChange={(e) => {
                setWeekFilter(e.target.value);
                setPage(1);
              }}
              className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 w-32"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="running">Running</option>
            <option value="complete">Complete</option>
            <option value="failed">Failed</option>
            <option value="partial">Partial</option>
          </select>
        </div>

        <div className="text-xs text-slate-500 font-medium">
          Total Runs: {total}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-sm">
          {error}
        </div>
      )}

      {/* Runs Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 text-xs uppercase tracking-wider font-semibold">
                <th className="py-3 px-4">Course & Week</th>
                <th className="py-3 px-4">Trigger</th>
                <th className="py-3 px-4">Overall Status</th>
                <th className="py-3 px-4">Stage Breakdown</th>
                <th className="py-3 px-4">Started At</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && runs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">
                    <RotateCw className="w-6 h-6 animate-spin mx-auto text-indigo-500 mb-2" />
                    Loading pipeline runs...
                  </td>
                </tr>
              ) : runs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">
                    No pipeline runs found matching criteria.
                  </td>
                </tr>
              ) : (
                runs.map((run) => (
                  <tr key={`${run.course_id}_w${run.week_index}`} className="hover:bg-slate-50 transition">
                    <td className="py-3 px-4 font-medium text-slate-900">
                      <div>{run.course_id}</div>
                      <div className="text-xs text-slate-500">Week {run.week_index}</div>
                    </td>
                    <td className="py-3 px-4 text-slate-600 text-xs">
                      <span className="capitalize font-medium">{run.trigger}</span>
                      <div className="text-slate-400 truncate max-w-[120px]" title={run.triggered_by}>
                        {run.triggered_by}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      {getStatusBadge(run.status)}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {getStageIndicator('LMS', run.stages?.lms_aggregation)}
                        {getStageIndicator('C1', run.stages?.c1_affective)}
                        {getStageIndicator('C2', run.stages?.c2_trajectory)}
                        {getStageIndicator('C3', run.stages?.c3_risk)}
                        {getStageIndicator('C4', run.stages?.c4_intervention)}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-xs">
                      {run.started_at ? new Date(run.started_at).toLocaleString() : '—'}
                    </td>
                    <td className="py-3 px-4 text-right space-x-2">
                      <button
                        onClick={() => setSelectedRun(run)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 rounded transition border border-slate-200"
                        title="View stage details"
                      >
                        <Eye className="w-3.5 h-3.5" /> Details
                      </button>
                      <button
                        onClick={() => handleAdvanceClick(run)}
                        disabled={isAuditor || run.status === 'complete'}
                        className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded transition border ${
                          isAuditor || run.status === 'complete'
                            ? 'text-slate-300 border-slate-200 cursor-not-allowed bg-slate-50'
                            : 'text-indigo-700 bg-indigo-50 border-indigo-200 hover:bg-indigo-100'
                        }`}
                        title={
                          isAuditor
                            ? 'Auditor read-only'
                            : run.status === 'complete'
                            ? 'Run already complete'
                            : 'Advance to next stage'
                        }
                      >
                        <RotateCw className="w-3.5 h-3.5" /> Advance
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Run Detail Modal */}
      {selectedRun && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full border border-slate-200 max-h-[90vh] flex flex-col overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  Pipeline Run: {selectedRun.course_id} (Week {selectedRun.week_index})
                </h3>
                <p className="text-xs text-slate-500">
                  Triggered by {selectedRun.triggered_by} ({selectedRun.trigger})
                </p>
              </div>
              <button
                onClick={() => setSelectedRun(null)}
                className="text-slate-400 hover:text-slate-600 text-sm font-semibold p-1"
              >
                ✕
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-4 bg-slate-50 p-3 rounded-lg border border-slate-100 text-xs">
                <div>
                  <span className="text-slate-400 block">Overall Status:</span>
                  <span className="font-semibold text-slate-800 uppercase">{selectedRun.status}</span>
                </div>
                <div>
                  <span className="text-slate-400 block">Current Stage:</span>
                  <span className="font-semibold text-slate-800">{selectedRun.current_stage || 'None'}</span>
                </div>
                <div>
                  <span className="text-slate-400 block">Started:</span>
                  <span className="text-slate-700">{new Date(selectedRun.started_at).toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-slate-400 block">Finished:</span>
                  <span className="text-slate-700">
                    {selectedRun.finished_at ? new Date(selectedRun.finished_at).toLocaleString() : 'In progress'}
                  </span>
                </div>
              </div>

              {selectedRun.error_message && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 text-xs">
                  <strong>Run Error:</strong> {selectedRun.error_message}
                </div>
              )}

              <h4 className="font-bold text-slate-800 text-sm pt-2">Stage Details</h4>
              <div className="space-y-3">
                {Object.entries(selectedRun.stages || {}).map(([stageName, stage]: [string, any]) => (
                  <div key={stageName} className="p-3 border border-slate-200 rounded-lg bg-white">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-slate-800 uppercase text-xs">
                        {stageName.replace('_', ' ')}
                      </span>
                      {getStatusBadge(stage?.status || 'pending')}
                    </div>
                    {stage?.error && (
                      <div className="text-xs text-rose-600 mt-1">Error: {stage.error}</div>
                    )}
                    {stage?.started_at && (
                      <div className="text-[11px] text-slate-400 mt-1">
                        Started: {new Date(stage.started_at).toLocaleTimeString()}
                        {stage.finished_at && ` • Finished: ${new Date(stage.finished_at).toLocaleTimeString()}`}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="px-6 py-3 bg-slate-50 border-t border-slate-100 flex justify-end">
              <button
                onClick={() => setSelectedRun(null)}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Trigger Modal */}
      {triggerModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full border border-slate-200 p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Trigger Pipeline Run</h3>
            <p className="text-xs text-slate-500">
              Initiates LMS weekly aggregation and triggers downstream ML components for a specific course week.
            </p>

            <form onSubmit={handleTriggerSubmit} className="space-y-3 text-sm">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Course ID *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. CS101"
                  value={triggerPayload.course_id}
                  onChange={(e) => setTriggerPayload({ ...triggerPayload, course_id: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Week Index *</label>
                <input
                  type="number"
                  min="0"
                  required
                  value={triggerPayload.week_index}
                  onChange={(e) => setTriggerPayload({ ...triggerPayload, week_index: parseInt(e.target.value, 10) || 0 })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="forceRerun"
                  checked={triggerPayload.force}
                  onChange={(e) => setTriggerPayload({ ...triggerPayload, force: e.target.checked })}
                  className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                <label htmlFor="forceRerun" className="text-xs text-slate-700">
                  Force re-run (overwrites existing run if already completed)
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-4">
                <button
                  type="button"
                  onClick={() => setTriggerModalOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm"
                >
                  Continue
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Trigger Confirmation */}
      <ConfirmDialog
        isOpen={triggerConfirmOpen}
        title="Confirm Pipeline Run Trigger"
        message={`Are you sure you want to trigger the weekly pipeline for Course ${triggerPayload.course_id} Week ${triggerPayload.week_index}? This action is audited under your identity.`}
        confirmLabel={actionLoading ? 'Triggering...' : 'Yes, Trigger Run'}
        variant="primary"
        isLoading={actionLoading}
        onConfirm={executeTrigger}
        onCancel={() => setTriggerConfirmOpen(false)}
      />

      {/* Advance Confirmation */}
      <ConfirmDialog
        isOpen={advanceConfirmOpen}
        title="Advance Pipeline Stage"
        message={`Advance pipeline progression for Course ${runToAdvance?.course_id} Week ${runToAdvance?.week_index}? The orchestrator will evaluate ready component outputs and proceed to the next stage.`}
        confirmLabel={actionLoading ? 'Advancing...' : 'Advance Stage'}
        variant="primary"
        isLoading={actionLoading}
        onConfirm={executeAdvance}
        onCancel={() => setAdvanceConfirmOpen(false)}
      />
    </div>
  );
};
