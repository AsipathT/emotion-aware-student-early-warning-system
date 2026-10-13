/**
 * src/pages/StaffInterventionsPage.tsx
 *
 * Feature 34: Operational Intervention Management Workspace (Component 4 FR10).
 * Displays full lifecycle intervention records with filters (status chips, 'My interventions' toggle),
 * student PID lookup, and manual intervention creation modal.
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import {
  HeartHandshake,
  PlusCircle,
  Filter,
  Search,
  UserCheck,
  Calendar,
  Clock,
  ArrowRight,
  Loader2,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Shield,
  X,
  Sparkles,
} from 'lucide-react';
import { StaffTabs } from '../components/staff/StaffTabs';
import {
  staffInterventionsApi,
  StaffInterventionListItem,
  ManualInterventionCreateRequest,
} from '../api/staffInterventions';

const CATALOG_OPTIONS = [
  { value: 'academic_support', label: 'Academic Support & Tutoring' },
  { value: 'counselling_mental_health', label: 'Mental Health & Wellbeing Counselling' },
  { value: 'time_management_guidance', label: 'Time Management & Study Skills Coaching' },
  { value: 'peer_mentoring', label: 'Peer Mentoring & Collaborative Study' },
  { value: 'additional_learning_resources', label: 'Supplementary Learning Resources' },
  { value: 'referral_services', label: 'Specialized Student Services Referral' },
  { value: 'peer_tutoring', label: 'Peer Tutoring & Study Group' },
  { value: 'academic_advising', label: 'Academic Advising Consultation' },
  { value: 'counsellor_outreach', label: 'Proactive Counsellor Outreach' },
];

const STATUS_CHIPS = [
  { value: '', label: 'All Statuses' },
  { value: 'approved', label: 'Approved' },
  { value: 'offered', label: 'Offered' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'declined', label: 'Declined' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
];

export const StaffInterventionsPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>('');
  const [onlyMine, setOnlyMine] = useState<boolean>(false);
  const [pidSearch, setPidSearch] = useState<string>('');
  const [debouncedPid, setDebouncedPid] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const pageSize = 15;

  // Manual modal state
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [modalPid, setModalPid] = useState<string>('');
  const [modalCourseId, setModalCourseId] = useState<string>('');
  const [modalType, setModalType] = useState<string>('counselling_mental_health');
  const [modalReason, setModalReason] = useState<string>('');
  const [modalError, setModalError] = useState<string | null>(null);

  // Query interventions list
  const {
    data: listData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['staff-interventions', statusFilter, onlyMine, debouncedPid, page],
    queryFn: () =>
      staffInterventionsApi.getInterventions({
        status: statusFilter || undefined,
        assigned_to: onlyMine ? 'me' : undefined,
        pid: debouncedPid || undefined,
        page,
        page_size: pageSize,
      }),
  });

  // Manual intervention creation mutation
  const createMutation = useMutation({
    mutationFn: (payload: ManualInterventionCreateRequest) =>
      staffInterventionsApi.createManualIntervention(payload),
    onSuccess: (newRecord) => {
      setIsModalOpen(false);
      resetModalForm();
      queryClient.invalidateQueries({ queryKey: ['staff-interventions'] });
      navigate(`/staff/interventions/${encodeURIComponent(newRecord.id)}`);
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to initiate manual intervention.';
      setModalError(detail);
    },
  });

  const resetModalForm = () => {
    setModalPid('');
    setModalCourseId('');
    setModalType('counselling_mental_health');
    setModalReason('');
    setModalError(null);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setDebouncedPid(pidSearch.trim());
    setPage(1);
  };

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setModalError(null);

    if (!modalPid.trim()) {
      setModalError('Student PID is required.');
      return;
    }
    if (!modalCourseId.trim()) {
      setModalError('Target course ID is required.');
      return;
    }
    if (modalReason.trim().length < 10) {
      setModalError('Reason must be at least 10 characters.');
      return;
    }

    createMutation.mutate({
      pid: modalPid.trim(),
      course_id: modalCourseId.trim(),
      intervention_type: modalType,
      reason: modalReason.trim(),
    });
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status.toLowerCase()) {
      case 'approved':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'offered':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'in_progress':
        return 'bg-indigo-100 text-indigo-800 border-indigo-200';
      case 'accepted':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'declined':
        return 'bg-rose-100 text-rose-800 border-rose-200';
      case 'completed':
        return 'bg-teal-100 text-teal-800 border-teal-200';
      case 'cancelled':
        return 'bg-slate-100 text-slate-700 border-slate-200';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Navigation tabs */}
      <StaffTabs />

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 rounded-2xl bg-indigo-50 text-indigo-600">
              <HeartHandshake className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                Intervention Operations & Case Management
              </h1>
              <p className="text-sm text-slate-500">
                Track scheduled student support actions, assign clinical staff, record private notes, and oversee the full intervention lifecycle (C4 FR10).
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={() => {
            resetModalForm();
            setIsModalOpen(true);
          }}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition"
        >
          <PlusCircle className="w-4 h-4" />
          New Manual Intervention
        </button>
      </div>

      {/* Filter and Control Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm mb-6 space-y-4">
        {/* Status Filter Chips */}
        <div>
          <div className="flex items-center gap-2 text-xs font-bold text-slate-600 mb-2.5">
            <Filter className="w-3.5 h-3.5 text-indigo-600" />
            <span>Filter by Lifecycle State:</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {STATUS_CHIPS.map((chip) => {
              const isActive = statusFilter === chip.value;
              return (
                <button
                  key={chip.value}
                  onClick={() => {
                    setStatusFilter(chip.value);
                    setPage(1);
                  }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition ${
                    isActive
                      ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                      : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  {chip.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="pt-3 border-t border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-4">
          {/* PID Search Input */}
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 flex-1 max-w-md">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search by student PID (e.g. STU_...)"
                value={pidSearch}
                onChange={(e) => setPidSearch(e.target.value)}
                className="w-full text-xs pl-9 pr-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
            <button
              type="submit"
              className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 transition"
            >
              Search
            </button>
            {debouncedPid && (
              <button
                type="button"
                onClick={() => {
                  setPidSearch('');
                  setDebouncedPid('');
                  setPage(1);
                }}
                className="p-2 text-slate-400 hover:text-slate-600"
                title="Clear search"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </form>

          {/* My Interventions Toggle */}
          <div className="flex items-center gap-3">
            <label className="inline-flex items-center gap-2 cursor-pointer select-none text-xs font-semibold text-slate-700">
              <input
                type="checkbox"
                checked={onlyMine}
                onChange={(e) => {
                  setOnlyMine(e.target.checked);
                  setPage(1);
                }}
                className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 h-4 w-4"
              />
              <UserCheck className="w-4 h-4 text-indigo-600" />
              <span>Assigned to me only</span>
            </label>
          </div>
        </div>
      </div>

      {/* Main Content: Table or Loading / Error / Empty States */}
      {isLoading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-sm">
          <Loader2 className="w-8 h-8 text-indigo-600 animate-spin mx-auto mb-3" />
          <p className="text-xs font-medium text-slate-500">Loading intervention operational records...</p>
        </div>
      ) : isError ? (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center text-xs text-rose-800">
          <AlertTriangle className="w-6 h-6 text-rose-600 mx-auto mb-2" />
          <p className="font-semibold">Unable to load intervention records.</p>
          <p className="mt-1 text-slate-600">
            {(error as any)?.response?.data?.detail || 'An unexpected server error occurred.'}
          </p>
          <button
            onClick={() => refetch()}
            className="mt-3 px-4 py-2 bg-rose-600 text-white rounded-xl font-semibold hover:bg-rose-700 transition"
          >
            Retry
          </button>
        </div>
      ) : !listData || listData.items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-sm">
          <HeartHandshake className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <h3 className="text-sm font-bold text-slate-800">No Interventions Found</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            {statusFilter || debouncedPid || onlyMine
              ? 'No intervention records match your active search filters.'
              : 'No intervention records have been generated yet. Review recommendations or create a manual intervention to begin.'}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50/75 border-b border-slate-200 text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Student PID</th>
                  <th className="px-5 py-3.5">Intervention Type</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5">Origin</th>
                  <th className="px-5 py-3.5">Assigned Staff</th>
                  <th className="px-5 py-3.5">Scheduled For</th>
                  <th className="px-5 py-3.5">Last Updated</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {listData.items.map((item: StaffInterventionListItem) => (
                  <tr key={item.id} className="hover:bg-slate-50/60 transition">
                    <td className="px-5 py-4 font-mono font-bold text-slate-900">
                      <Link
                        to={`/staff/students/${encodeURIComponent(item.pid)}`}
                        className="hover:text-indigo-600 transition flex items-center gap-1.5"
                      >
                        <Shield className="w-3.5 h-3.5 text-indigo-500" />
                        <span>{item.pid}</span>
                      </Link>
                    </td>

                    <td className="px-5 py-4">
                      <div className="font-bold text-slate-900">{item.label}</div>
                      <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                        course: {item.course_id}
                      </div>
                    </td>

                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${getStatusBadgeClass(
                          item.status
                        )}`}
                      >
                        {item.status}
                      </span>
                    </td>

                    <td className="px-5 py-4">
                      <span className="capitalize text-slate-600 font-medium">
                        {item.origin}
                      </span>
                    </td>

                    <td className="px-5 py-4">
                      {item.assigned_staff_name ? (
                        <div className="flex items-center gap-1.5 text-slate-800 font-medium">
                          <UserCheck className="w-3.5 h-3.5 text-indigo-600" />
                          <span>{item.assigned_staff_name}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">Unassigned</span>
                      )}
                    </td>

                    <td className="px-5 py-4">
                      {item.scheduled_for ? (
                        <div className="flex items-center gap-1.5 text-slate-700">
                          <Calendar className="w-3.5 h-3.5 text-slate-400" />
                          <span>{new Date(item.scheduled_for).toLocaleDateString()}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">Not scheduled</span>
                      )}
                    </td>

                    <td className="px-5 py-4 text-slate-500">
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        <span>{new Date(item.updated_at).toLocaleDateString()}</span>
                      </div>
                    </td>

                    <td className="px-5 py-4 text-right">
                      <Link
                        to={`/staff/interventions/${encodeURIComponent(item.id)}`}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-semibold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition"
                      >
                        <span>Manage</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div className="px-5 py-3.5 bg-slate-50/75 border-t border-slate-200 flex items-center justify-between text-xs text-slate-600">
            <div>
              Showing <span className="font-semibold">{(page - 1) * pageSize + 1}</span> to{' '}
              <span className="font-semibold">
                {Math.min(page * pageSize, listData.total_count)}
              </span>{' '}
              of <span className="font-semibold">{listData.total_count}</span> interventions
            </div>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                className="p-1.5 rounded-lg border border-slate-200 hover:bg-white disabled:opacity-40 transition"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="font-medium">
                Page {page} of {listData.total_pages || 1}
              </span>
              <button
                disabled={page >= listData.total_pages}
                onClick={() => setPage((prev) => Math.min(prev + 1, listData.total_pages))}
                className="p-1.5 rounded-lg border border-slate-200 hover:bg-white disabled:opacity-40 transition"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Intervention Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-200">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-indigo-50 text-indigo-600">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-sm">
                    Initiate Manual Intervention
                  </h3>
                  <p className="text-xs text-slate-500">
                    Counsellor-initiated intervention for comparative research and direct support.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {modalError && (
              <div className="mb-4 bg-rose-50 border border-rose-200 rounded-xl p-3 text-xs text-rose-800 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleManualSubmit} className="space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Student PID (Pseudonymized ID) *
                </label>
                <input
                  type="text"
                  placeholder="e.g. STU_3079b769ad0e"
                  value={modalPid}
                  onChange={(e) => setModalPid(e.target.value)}
                  className="w-full text-xs font-mono border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Target Course ID *
                </label>
                <input
                  type="text"
                  placeholder="e.g. course-ai-101"
                  value={modalCourseId}
                  onChange={(e) => setModalCourseId(e.target.value)}
                  className="w-full text-xs border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Intervention Strategy (Catalog) *
                </label>
                <select
                  value={modalType}
                  onChange={(e) => setModalType(e.target.value)}
                  className="w-full text-xs border-slate-200 rounded-xl px-3 py-2 bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                >
                  {CATALOG_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label} ({opt.value})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-bold text-slate-700">
                    Clinical / Academic Rationale (10 - 500 chars) *
                  </label>
                  <span className="text-[11px] text-slate-400 font-mono">
                    {modalReason.length} / 500
                  </span>
                </div>
                <textarea
                  rows={3}
                  maxLength={500}
                  placeholder="Detail the observational indicators and reasons for initiating this intervention manually..."
                  value={modalReason}
                  onChange={(e) => setModalReason(e.target.value)}
                  className="w-full text-xs border-slate-200 rounded-xl p-3 bg-slate-50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition disabled:opacity-50"
                >
                  {createMutation.isPending ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    'Create Intervention'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
