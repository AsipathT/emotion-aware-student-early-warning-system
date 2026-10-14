import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  adminApi,
  AdminConsentCoverageResponse,
} from '../../api/admin';
import { useAuth } from '../../hooks/useAuth';
import { PageHeader } from '../../components/admin/PageHeader';
import {
  Scale,
  AlertTriangle,
  CheckCircle2,
  Clock,
  UserX,
  FileText,
  PlusCircle,
  RefreshCw,
  X,
  History,
  BookOpen,
  Info,
} from 'lucide-react';

export const AdminConsentPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();
  const isAuditor = currentUser?.role === 'auditor';

  // Modal State
  const [isPublishModalOpen, setIsPublishModalOpen] = useState(false);
  const [newNoticeText, setNewNoticeText] = useState('');

  // Query: Consent Coverage & History
  const {
    data: consentData,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery<AdminConsentCoverageResponse>({
    queryKey: ['adminConsentCoverage'],
    queryFn: () => adminApi.getAdminConsentCoverage(),
  });

  // Mutation: Publish New Notice
  const publishNoticeMutation = useMutation({
    mutationFn: (text: string) => adminApi.publishAdminConsentNotice({ text }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConsentCoverage'] });
      queryClient.invalidateQueries({ queryKey: ['adminOverview'] });
      setIsPublishModalOpen(false);
      setNewNoticeText('');
    },
  });

  const handlePublishSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNoticeText.trim()) return;
    publishNoticeMutation.mutate(newNoticeText.trim());
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader
          title="Consent & Ethics Governance"
          description="Active ethics notice compliance, student consent coverage, and revision audit history."
          actions={
            isAuditor ? (
              <span className="px-2.5 py-1 bg-indigo-50 text-indigo-700 text-xs font-semibold rounded-full border border-indigo-200">
                Read-Only Auditor View
              </span>
            ) : undefined
          }
        />

        {!isAuditor && (
          <button
            onClick={() => setIsPublishModalOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors self-start sm:self-auto"
          >
            <PlusCircle className="w-4 h-4" />
            Publish New Notice Version
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="bg-white p-12 rounded-xl shadow-sm border border-slate-200 text-center text-slate-500">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-indigo-500" />
          Loading consent compliance metrics...
        </div>
      ) : error ? (
        <div className="bg-rose-50 border border-rose-200 p-6 rounded-xl text-rose-700 text-center">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-rose-600" />
          <p className="font-semibold">Failed to load consent coverage statistics.</p>
        </div>
      ) : (
        <>
          {/* Top KPI Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {/* Active Notice Version */}
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Active Notice
                </span>
                <p className="text-2xl font-bold text-slate-900 mt-1">
                  {consentData?.active_version ? `v${consentData.active_version}` : 'None'}
                </p>
              </div>
              <div className="mt-3 flex items-center gap-1.5 text-xs text-slate-500">
                <Clock className="w-3.5 h-3.5" />
                {consentData?.active_notice?.effective_from
                  ? `Since ${new Date(consentData.active_notice.effective_from).toLocaleDateString()}`
                  : 'No active notice'}
              </div>
            </div>

            {/* Coverage Percentage */}
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Active Coverage
                </span>
                <div className="flex items-baseline gap-2 mt-1">
                  <p className="text-2xl font-bold text-indigo-600">
                    {consentData?.coverage_percentage ?? 0}%
                  </p>
                  <span className="text-xs text-slate-500">
                    ({consentData?.accepted ?? 0} / {consentData?.total_students ?? 0})
                  </span>
                </div>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-1.5 mt-3 overflow-hidden">
                <div
                  className="bg-indigo-600 h-1.5 rounded-full"
                  style={{ width: `${Math.min(100, consentData?.coverage_percentage || 0)}%` }}
                />
              </div>
            </div>

            {/* Consented / Accepted */}
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Consented
                </span>
                <p className="text-2xl font-bold text-emerald-600 mt-1">
                  {consentData?.accepted ?? 0}
                </p>
              </div>
              <div className="mt-3 flex items-center gap-1.5 text-xs text-emerald-600 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Eligible for ML analysis
              </div>
            </div>

            {/* Pending */}
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Pending Decision
                </span>
                <p className="text-2xl font-bold text-amber-600 mt-1">
                  {consentData?.pending ?? 0}
                </p>
              </div>
              <div className="mt-3 flex items-center gap-1.5 text-xs text-amber-600 font-medium">
                <Clock className="w-3.5 h-3.5" />
                Awaiting student review
              </div>
            </div>

            {/* Withdrawn (Excluded) */}
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
              <div>
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Withdrawn / Opted-Out
                </span>
                <p className="text-2xl font-bold text-rose-600 mt-1">
                  {consentData?.withdrawn ?? 0}
                </p>
              </div>
              <div className="mt-3 flex items-center gap-1.5 text-xs text-rose-600 font-medium">
                <UserX className="w-3.5 h-3.5" />
                Excluded from export pipelines
              </div>
            </div>
          </div>

          {/* Active Notice Body Card */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-600" />
                <h3 className="text-base font-semibold text-slate-900">
                  Currently Active Ethics & Data Usage Notice
                </h3>
              </div>
              {consentData?.active_notice && (
                <span className="px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-semibold rounded-full">
                  Active (Version {consentData.active_version})
                </span>
              )}
            </div>

            {consentData?.active_notice ? (
              <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed">
                {consentData.active_notice.text}
              </div>
            ) : (
              <p className="text-sm text-slate-500 italic">
                No consent notice is currently marked active. Please publish a notice version.
              </p>
            )}

            <div className="flex items-center gap-2 text-xs text-slate-500 pt-1">
              <Info className="w-4 h-4 text-slate-400" />
              <span>
                According to Research Governance Feature 6 &amp; 21: Withdrawn students are strictly excluded from all downstream ML analytics and pseudonymized data export APIs.
              </span>
            </div>
          </div>

          {/* Course-level Consent Breakdown Table */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-slate-600" />
                <h3 className="font-semibold text-slate-900 text-sm">
                  Course-Level Consent Coverage
                </h3>
              </div>
              <button
                onClick={() => refetch()}
                disabled={isFetching}
                className="text-xs text-slate-500 hover:text-indigo-600 flex items-center gap-1"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 tracking-wider">
                  <tr>
                    <th className="px-6 py-3 text-left">Course</th>
                    <th className="px-6 py-3 text-center">Enrolled</th>
                    <th className="px-6 py-3 text-center text-emerald-600">Consented</th>
                    <th className="px-6 py-3 text-center text-amber-600">Pending</th>
                    <th className="px-6 py-3 text-center text-rose-600">Withdrawn</th>
                    <th className="px-6 py-3 text-right">Coverage Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {!consentData?.course_breakdown || consentData.course_breakdown.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-6 py-8 text-center text-slate-400">
                        No courses registered in the platform.
                      </td>
                    </tr>
                  ) : (
                    consentData.course_breakdown.map((c) => (
                      <tr key={c.course_id} className="hover:bg-slate-50/80">
                        <td className="px-6 py-3.5">
                          <div className="flex flex-col">
                            <span className="font-medium text-slate-900">{c.course_title}</span>
                            <span className="text-xs font-mono text-slate-400">{c.course_id}</span>
                          </div>
                        </td>
                        <td className="px-6 py-3.5 text-center font-medium text-slate-700">
                          {c.enrolled_students}
                        </td>
                        <td className="px-6 py-3.5 text-center font-semibold text-emerald-600">
                          {c.accepted}
                        </td>
                        <td className="px-6 py-3.5 text-center font-medium text-amber-600">
                          {c.pending}
                        </td>
                        <td className="px-6 py-3.5 text-center font-medium text-rose-600">
                          {c.withdrawn}
                        </td>
                        <td className="px-6 py-3.5 text-right">
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                              c.coverage_percentage >= 75
                                ? 'bg-emerald-50 text-emerald-700'
                                : c.coverage_percentage >= 40
                                ? 'bg-amber-50 text-amber-700'
                                : 'bg-rose-50 text-rose-700'
                            }`}
                          >
                            {c.coverage_percentage}%
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Notice Version History */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex items-center gap-2 bg-slate-50">
              <History className="w-5 h-5 text-slate-600" />
              <h3 className="font-semibold text-slate-900 text-sm">
                Consent Notice Version History
              </h3>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 tracking-wider">
                  <tr>
                    <th className="px-6 py-3 text-left">Version</th>
                    <th className="px-6 py-3 text-left">Status</th>
                    <th className="px-6 py-3 text-left">Effective Date</th>
                    <th className="px-6 py-3 text-left">Notice Text Preview</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {!consentData?.notice_history || consentData.notice_history.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-6 py-8 text-center text-slate-400">
                        No notice history found.
                      </td>
                    </tr>
                  ) : (
                    consentData.notice_history.map((n) => (
                      <tr key={n.id} className="hover:bg-slate-50/80">
                        <td className="px-6 py-3.5 font-bold text-slate-900">
                          v{n.version}
                        </td>
                        <td className="px-6 py-3.5">
                          {n.is_active ? (
                            <span className="px-2.5 py-1 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-full border border-emerald-200">
                              Active
                            </span>
                          ) : (
                            <span className="px-2.5 py-1 bg-slate-100 text-slate-600 text-xs font-medium rounded-full">
                              Archived
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-3.5 text-slate-600 text-xs">
                          {new Date(n.effective_from).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-3.5 text-slate-600 text-xs font-sans truncate max-w-md">
                          {n.text}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Publish New Notice Modal */}
      {isPublishModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-lg w-full p-6 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Scale className="w-5 h-5 text-indigo-600" />
                <h3 className="text-lg font-semibold text-slate-900">
                  Publish New Consent Notice Version
                </h3>
              </div>
              <button
                onClick={() => setIsPublishModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Warning Alert */}
            <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-xs flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Important Governance Notice:</p>
                <p className="mt-0.5 leading-relaxed">
                  Publishing a new notice will archive the current active notice. Student consent coverage is strictly evaluated against the active version only. All students will need to review and accept the new notice upon their next login.
                </p>
              </div>
            </div>

            <form onSubmit={handlePublishSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Notice Text Body
                </label>
                <textarea
                  rows={8}
                  placeholder="Specify the full ethics notice text, data processing purposes, and student rights..."
                  value={newNoticeText}
                  onChange={(e) => setNewNoticeText(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 font-sans"
                  required
                />
              </div>

              {publishNoticeMutation.isError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                  <span>Failed to publish notice. Please verify administrator permissions.</span>
                </div>
              )}

              <div className="pt-3 flex justify-end gap-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsPublishModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={publishNoticeMutation.isPending || !newNoticeText.trim()}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {publishNoticeMutation.isPending ? 'Publishing...' : 'Publish Version'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
