import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  adminApi,
  AdminEnrolmentItem,
  AdminPaginatedEnrolmentsResponse,
  AdminBulkEnrolmentResponse,
} from '../../api/admin';
import { useAuth } from '../../hooks/useAuth';
import { PageHeader } from '../../components/admin/PageHeader';
import { StatusBadge } from '../../components/admin/StatusBadge';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import {
  UserCheck,
  Search,
  UserPlus,
  AlertCircle,
  X,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  UserMinus,
  FileSpreadsheet,
  Copy,
  Check,
} from 'lucide-react';

export const AdminEnrolmentsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();
  const isAuditor = currentUser?.role === 'auditor';

  // Filters & Pagination
  const [page, setPage] = useState(1);
  const pageSize = 15;
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [courseFilter, setCourseFilter] = useState<string>('all');

  // Modals state
  const [isSingleModalOpen, setIsSingleModalOpen] = useState(false);
  const [isBulkModalOpen, setIsBulkModalOpen] = useState(false);
  const [singleCourseId, setSingleCourseId] = useState('');
  const [singleStudentIdentifier, setSingleStudentIdentifier] = useState('');

  // Bulk Enrol state
  const [bulkCourseId, setBulkCourseId] = useState('');
  const [bulkIdentifiersText, setBulkIdentifiersText] = useState('');
  const [bulkResult, setBulkResult] = useState<AdminBulkEnrolmentResponse | null>(null);

  // Copied PID state
  const [copiedPid, setCopiedPid] = useState<string | null>(null);

  // Confirmation dialog state
  const [confirmState, setConfirmState] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
    variant: 'danger' | 'warning' | 'primary';
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => {},
    variant: 'danger',
  });

  // Query: Courses list for dropdowns and filter
  const { data: coursesData } = useQuery({
    queryKey: ['adminCoursesDropdown'],
    queryFn: () => adminApi.getAdminCoursesPaginated({ page_size: 100 }),
  });
  const coursesList = coursesData?.items || [];

  // Query: Paginated Enrolments
  const {
    data: enrolmentsData,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery<AdminPaginatedEnrolmentsResponse>({
    queryKey: ['adminEnrolments', page, searchQuery, statusFilter, courseFilter],
    queryFn: () =>
      adminApi.getAdminEnrolmentsPaginated({
        page,
        page_size: pageSize,
        q: searchQuery || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter,
        course_id: courseFilter === 'all' ? undefined : courseFilter,
      }),
  });

  // Mutation: Single Enrolment
  const singleEnrolMutation = useMutation({
    mutationFn: (payload: { course_id: string; student_identifier: string }) =>
      adminApi.createAdminEnrolment(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminEnrolments'] });
      queryClient.invalidateQueries({ queryKey: ['adminCourses'] });
      queryClient.invalidateQueries({ queryKey: ['adminOverview'] });
      setIsSingleModalOpen(false);
      setSingleStudentIdentifier('');
    },
  });

  // Mutation: Soft-Drop Enrolment
  const dropMutation = useMutation({
    mutationFn: (enrolmentId: string) => adminApi.deleteAdminEnrolment(enrolmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminEnrolments'] });
      queryClient.invalidateQueries({ queryKey: ['adminCourses'] });
      queryClient.invalidateQueries({ queryKey: ['adminOverview'] });
    },
  });

  // Mutation: Bulk Enrolment
  const bulkEnrolMutation = useMutation({
    mutationFn: (payload: { course_id: string; student_identifiers: string[] }) =>
      adminApi.bulkAdminEnrolment(payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['adminEnrolments'] });
      queryClient.invalidateQueries({ queryKey: ['adminCourses'] });
      queryClient.invalidateQueries({ queryKey: ['adminOverview'] });
      setBulkResult(data);
    },
  });

  const handleCopyPid = (pid: string) => {
    navigator.clipboard.writeText(pid);
    setCopiedPid(pid);
    setTimeout(() => setCopiedPid(null), 2000);
  };

  const handleDropEnrolment = (enr: AdminEnrolmentItem) => {
    if (isAuditor) return;
    setConfirmState({
      isOpen: true,
      title: 'Soft-Drop Course Enrolment',
      message: `Are you sure you want to drop student ${enr.student_name || enr.pid} from "${enr.course_title || enr.course_id}"? This will set their enrolment status to "dropped". Their academic marks, quiz attempts, and submitted works remain fully preserved in accordance with academic integrity rules.`,
      variant: 'danger',
      onConfirm: () => {
        dropMutation.mutate(enr.id);
        setConfirmState((prev) => ({ ...prev, isOpen: false }));
      },
    });
  };

  const handleSingleEnrolSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!singleCourseId || !singleStudentIdentifier.trim()) return;
    singleEnrolMutation.mutate({
      course_id: singleCourseId,
      student_identifier: singleStudentIdentifier.trim(),
    });
  };

  const handleBulkEnrolSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!bulkCourseId || !bulkIdentifiersText.trim()) return;
    const lines = bulkIdentifiersText
      .split(/[\n,]+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    if (lines.length === 0) return;

    bulkEnrolMutation.mutate({
      course_id: bulkCourseId,
      student_identifiers: lines,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader
          title="Enrolments Management"
          description="Student academic enrolments, soft-drop controls, and bulk student intake."
          actions={
            isAuditor ? (
              <span className="px-2.5 py-1 bg-indigo-50 text-indigo-700 text-xs font-semibold rounded-full border border-indigo-200">
                Read-Only Auditor View
              </span>
            ) : undefined
          }
        />

        {!isAuditor && (
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setSingleCourseId(coursesList[0]?.course_id || coursesList[0]?.id || '');
                setIsSingleModalOpen(true);
              }}
              className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 text-sm font-medium rounded-lg shadow-sm transition-colors"
            >
              <UserPlus className="w-4 h-4 text-indigo-600" />
              Enrol Student
            </button>
            <button
              onClick={() => {
                setBulkCourseId(coursesList[0]?.course_id || coursesList[0]?.id || '');
                setBulkResult(null);
                setBulkIdentifiersText('');
                setIsBulkModalOpen(true);
              }}
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors"
            >
              <FileSpreadsheet className="w-4 h-4" />
              Bulk Enrol
            </button>
          </div>
        )}
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="flex flex-1 w-full gap-3 flex-wrap sm:flex-nowrap">
          {/* Search Box */}
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search student, email, PID or course..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(1);
              }}
              className="w-full pl-9 pr-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            {searchQuery && (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setPage(1);
                }}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700"
          >
            <option value="all">All Enrolment Statuses</option>
            <option value="active">Active Only</option>
            <option value="dropped">Dropped Only</option>
          </select>

          {/* Course Filter */}
          <select
            value={courseFilter}
            onChange={(e) => {
              setCourseFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-700 max-w-xs truncate"
          >
            <option value="all">All Courses</option>
            {coursesList.map((c) => (
              <option key={c.id} value={c.course_id || c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center px-3 py-2 text-sm text-slate-600 hover:text-indigo-600 border border-slate-300 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors"
          title="Refresh table"
        >
          <RefreshCw className={`w-4 h-4 mr-1.5 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Main Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Student
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Course
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Enrolled On
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-slate-500">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-500" />
                    Loading student enrolments...
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-rose-500">
                    <AlertCircle className="w-6 h-6 mx-auto mb-2" />
                    Failed to load enrolments. Please verify system permissions.
                  </td>
                </tr>
              ) : !enrolmentsData?.items || enrolmentsData.items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-slate-500">
                    <UserCheck className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    No enrolments found matching current criteria.
                  </td>
                </tr>
              ) : (
                enrolmentsData.items.map((enr) => (
                  <tr key={enr.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-semibold text-slate-900">
                          {enr.student_name || 'Enrolled Student'}
                        </span>
                        <span className="text-xs text-slate-500">{enr.student_email}</span>
                        {enr.pid && (
                          <div className="flex items-center gap-1.5 mt-1">
                            <span className="text-xs font-mono bg-purple-50 text-purple-700 px-2 py-0.5 rounded border border-purple-200">
                              {enr.pid}
                            </span>
                            <button
                              onClick={() => handleCopyPid(enr.pid!)}
                              className="text-slate-400 hover:text-purple-600 transition-colors"
                              title="Copy PID"
                            >
                              {copiedPid === enr.pid ? (
                                <Check className="w-3.5 h-3.5 text-emerald-600" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-medium text-slate-800">
                          {enr.course_title || 'Untitled Course'}
                        </span>
                        <span className="text-xs font-mono text-indigo-600">{enr.course_id}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">
                      {enr.enrolled_at ? (
                        <span>{new Date(enr.enrolled_at).toLocaleDateString()}</span>
                      ) : (
                        <span className="text-slate-400">N/A</span>
                      )}
                      {enr.enrolment_end && (
                        <div className="text-xs text-rose-500 mt-0.5">
                          Dropped: {new Date(enr.enrolment_end).toLocaleDateString()}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge
                        status={enr.status === 'active' ? 'active' : 'suspended'}
                      />
                    </td>
                    <td className="px-6 py-4 text-right">
                      {enr.status === 'active' ? (
                        <button
                          onClick={() => handleDropEnrolment(enr)}
                          disabled={isAuditor || dropMutation.isPending}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-rose-600 hover:bg-rose-50 rounded-lg transition-colors disabled:opacity-40"
                          title="Soft-Drop Enrolment"
                        >
                          <UserMinus className="w-3.5 h-3.5" />
                          Drop
                        </button>
                      ) : (
                        <span className="text-xs text-slate-400 italic">Dropped</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {enrolmentsData && enrolmentsData.total_pages > 1 && (
          <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
            <p className="text-sm text-slate-600">
              Showing <span className="font-medium">{(page - 1) * pageSize + 1}</span> to{' '}
              <span className="font-medium">
                {Math.min(page * pageSize, enrolmentsData.total)}
              </span>{' '}
              of <span className="font-medium">{enrolmentsData.total}</span> enrolments
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 border border-slate-300 rounded-lg text-slate-600 hover:bg-white disabled:opacity-40 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-sm font-medium text-slate-700 px-2">
                Page {page} of {enrolmentsData.total_pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(enrolmentsData.total_pages, p + 1))}
                disabled={page === enrolmentsData.total_pages}
                className="p-1.5 border border-slate-300 rounded-lg text-slate-600 hover:bg-white disabled:opacity-40 transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Single Enrol Modal */}
      {isSingleModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-indigo-600" />
                <h3 className="text-lg font-semibold text-slate-900">Enrol Single Student</h3>
              </div>
              <button
                onClick={() => setIsSingleModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSingleEnrolSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Target Course
                </label>
                <select
                  value={singleCourseId}
                  onChange={(e) => setSingleCourseId(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  required
                >
                  {coursesList.map((c) => (
                    <option key={c.id} value={c.course_id || c.id}>
                      {c.title} ({c.course_id})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Student Identifier
                </label>
                <input
                  type="text"
                  placeholder="Student email, UUID, or PID (STU_...)"
                  value={singleStudentIdentifier}
                  onChange={(e) => setSingleStudentIdentifier(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  required
                />
                <p className="text-xs text-slate-400 mt-1">
                  Accepts student registration email, system account ID, or pseudonym identifier.
                </p>
              </div>

              {singleEnrolMutation.isError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>
                    {(singleEnrolMutation.error as any)?.response?.data?.detail ||
                      'Failed to enrol student. Please verify the account exists.'}
                  </span>
                </div>
              )}

              <div className="pt-3 flex justify-end gap-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsSingleModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={singleEnrolMutation.isPending || !singleStudentIdentifier.trim()}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {singleEnrolMutation.isPending ? 'Enrolling...' : 'Confirm Enrolment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Bulk Enrol Modal */}
      {isBulkModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-xl w-full p-6 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-indigo-600" />
                <h3 className="text-lg font-semibold text-slate-900">Bulk Student Intake</h3>
              </div>
              <button
                onClick={() => {
                  setIsBulkModalOpen(false);
                  setBulkResult(null);
                }}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {!bulkResult ? (
              <form onSubmit={handleBulkEnrolSubmit} className="mt-4 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Target Academic Course
                  </label>
                  <select
                    value={bulkCourseId}
                    onChange={(e) => setBulkCourseId(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    required
                  >
                    {coursesList.map((c) => (
                      <option key={c.id} value={c.course_id || c.id}>
                        {c.title} ({c.course_id})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Student Identifiers (One per line or comma-separated)
                  </label>
                  <textarea
                    rows={6}
                    placeholder="student1@sliit.lk&#10;student2@sliit.lk&#10;STU_a8f9b2c1"
                    value={bulkIdentifiersText}
                    onChange={(e) => setBulkIdentifiersText(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    required
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Paste student emails or PIDs. The intake process is completely idempotent; existing enrolments will be preserved without duplicates.
                  </p>
                </div>

                {bulkEnrolMutation.isError && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>Failed to process bulk enrolment batch.</span>
                  </div>
                )}

                <div className="pt-3 flex justify-end gap-3 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => setIsBulkModalOpen(false)}
                    className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={bulkEnrolMutation.isPending || !bulkIdentifiersText.trim()}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                  >
                    {bulkEnrolMutation.isPending ? 'Processing Intake...' : 'Run Bulk Enrolment'}
                  </button>
                </div>
              </form>
            ) : (
              /* Bulk Results Report */
              <div className="mt-4 space-y-4">
                <div className="grid grid-cols-4 gap-2 text-center">
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                    <p className="text-xs text-slate-500 font-medium">Total</p>
                    <p className="text-lg font-bold text-slate-800">{bulkResult.total}</p>
                  </div>
                  <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                    <p className="text-xs text-emerald-600 font-medium">Enrolled</p>
                    <p className="text-lg font-bold text-emerald-700">{bulkResult.enrolled_count}</p>
                  </div>
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                    <p className="text-xs text-amber-600 font-medium">Skipped</p>
                    <p className="text-lg font-bold text-amber-700">{bulkResult.skipped_count}</p>
                  </div>
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg">
                    <p className="text-xs text-rose-600 font-medium">Failed</p>
                    <p className="text-lg font-bold text-rose-700">{bulkResult.failed_count}</p>
                  </div>
                </div>

                <div className="max-h-60 overflow-y-auto border border-slate-200 rounded-lg divide-y divide-slate-100 text-xs">
                  {bulkResult.results.map((row, idx) => (
                    <div key={idx} className="p-2.5 flex items-center justify-between">
                      <div className="flex flex-col">
                        <span className="font-mono font-medium text-slate-800">{row.identifier}</span>
                        {row.reason && <span className="text-slate-500">{row.reason}</span>}
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded font-medium ${
                          row.status === 'enrolled'
                            ? 'bg-emerald-100 text-emerald-800'
                            : row.status === 'skipped'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {row.status}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="pt-3 flex justify-end gap-3 border-t border-slate-100">
                  <button
                    onClick={() => {
                      setBulkResult(null);
                      setBulkIdentifiersText('');
                    }}
                    className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Enrol Another Batch
                  </button>
                  <button
                    onClick={() => {
                      setIsBulkModalOpen(false);
                      setBulkResult(null);
                    }}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium"
                  >
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Confirmation Dialog */}
      <ConfirmDialog
        isOpen={confirmState.isOpen}
        title={confirmState.title}
        message={confirmState.message}
        onConfirm={confirmState.onConfirm}
        onCancel={() => setConfirmState((prev) => ({ ...prev, isOpen: false }))}
        variant={confirmState.variant}
        isLoading={dropMutation.isPending}
      />
    </div>
  );
};
