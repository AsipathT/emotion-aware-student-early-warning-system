/**
 * src/pages/StaffInterventionDetailPage.tsx
 *
 * Feature 34: Operational Intervention Management Detail Workspace (Component 4 FR10).
 * Displays full lifecycle record, status history timeline, baseline snapshot card,
 * staff assignment editor, schedule picker, transition action buttons, and counselor case notes.
 *
 * Contains marked expansion slots for F35, F38, and F39.
 */

import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Calendar,
  Clock,
  UserCheck,
  Shield,
  AlertTriangle,
  Loader2,
  CheckCircle2,
  XCircle,
  PlayCircle,
  Send,
  MessageSquare,
  Lock,
  Sparkles,
  Layers,
  FileText,
  User,
} from 'lucide-react';
import { StaffTabs } from '../components/staff/StaffTabs';
import { OutcomeSection } from '../components/staff/OutcomeSection';
import { DeliveryPanel } from '../components/staff/DeliveryPanel';
import { FeedbackPanel } from '../components/staff/FeedbackPanel';

import {
  staffInterventionsApi,
  StaffMemberItem,
  StaffInterventionPatchRequest,
} from '../api/staffInterventions';

export const StaffInterventionDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const [noteContent, setNoteContent] = useState<string>('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Assignment & schedule state
  const [selectedStaff, setSelectedStaff] = useState<string>('');
  const [scheduledDateTime, setScheduledDateTime] = useState<string>('');

  // Transition confirmation dialog
  const [pendingStatus, setPendingStatus] = useState<string | null>(null);
  const [transitionNote, setTransitionNote] = useState<string>('');

  // Query intervention detail
  const {
    data: detail,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['staff-intervention-detail', id],
    queryFn: () => staffInterventionsApi.getInterventionDetail(id!),
    enabled: Boolean(id),
  });

  // Query staff members for assignment dropdown
  const { data: staffMembers } = useQuery({
    queryKey: ['staff-members'],
    queryFn: () => staffInterventionsApi.getStaffMembers(),
  });

  // Patch mutation
  const patchMutation = useMutation({
    mutationFn: (payload: StaffInterventionPatchRequest) =>
      staffInterventionsApi.patchIntervention(id!, payload),
    onSuccess: (updated) => {
      setActionError(null);
      setActionSuccess('Intervention updated successfully.');
      setPendingStatus(null);
      setTransitionNote('');
      queryClient.setQueryData(['staff-intervention-detail', id], updated);
      queryClient.invalidateQueries({ queryKey: ['staff-interventions'] });
      setTimeout(() => setActionSuccess(null), 4000);
    },
    onError: (err: any) => {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to update intervention record.';
      setActionError(msg);
      setPendingStatus(null);
    },
  });

  // Add note mutation
  const addNoteMutation = useMutation({
    mutationFn: (content: string) =>
      staffInterventionsApi.addInterventionNote(id!, { content }),
    onSuccess: () => {
      setNoteContent('');
      setActionError(null);
      setActionSuccess('Case note appended successfully.');
      refetch();
      setTimeout(() => setActionSuccess(null), 4000);
    },
    onError: (err: any) => {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to append case note.';
      setActionError(msg);
    },
  });

  // Handle staff assignment change
  const handleAssignStaff = (staffId: string) => {
    setSelectedStaff(staffId);
    patchMutation.mutate({ assigned_to: staffId || null });
  };

  // Handle schedule change
  const handleScheduleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!scheduledDateTime) return;
    patchMutation.mutate({ scheduled_for: new Date(scheduledDateTime).toISOString() });
  };

  // Handle status transition confirm
  const handleConfirmTransition = () => {
    if (!pendingStatus) return;
    patchMutation.mutate({
      status: pendingStatus,
      note: transitionNote.trim() || undefined,
    });
  };

  // Handle note submit
  const handleAddNote = (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteContent.trim()) return;
    addNoteMutation.mutate(noteContent.trim());
  };

  const getStatusBadge = (status: string) => {
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

  // Determine allowed counsellor transitions for current status
  const getCounsellorActions = (currStatus: string) => {
    const s = currStatus.toLowerCase();
    const actions: { target: string; label: string; icon: React.ComponentType<{ className?: string }>; style: string }[] = [];

    if (s === 'approved') {
      actions.push({
        target: 'offered',
        label: 'Dispatch / Offer to Student',
        icon: Send,
        style: 'bg-blue-600 hover:bg-blue-700 text-white',
      });
      actions.push({
        target: 'cancelled',
        label: 'Cancel Intervention',
        icon: XCircle,
        style: 'bg-slate-100 hover:bg-slate-200 text-slate-700',
      });
    } else if (s === 'offered') {
      actions.push({
        target: 'in_progress',
        label: 'Begin Implementation (In Progress)',
        icon: PlayCircle,
        style: 'bg-indigo-600 hover:bg-indigo-700 text-white',
      });
      actions.push({
        target: 'cancelled',
        label: 'Cancel Intervention',
        icon: XCircle,
        style: 'bg-slate-100 hover:bg-slate-200 text-slate-700',
      });
    } else if (s === 'accepted') {
      actions.push({
        target: 'in_progress',
        label: 'Begin Implementation (In Progress)',
        icon: PlayCircle,
        style: 'bg-indigo-600 hover:bg-indigo-700 text-white',
      });
      actions.push({
        target: 'cancelled',
        label: 'Cancel Intervention',
        icon: XCircle,
        style: 'bg-slate-100 hover:bg-slate-200 text-slate-700',
      });
    } else if (s === 'in_progress') {
      actions.push({
        target: 'cancelled',
        label: 'Cancel Intervention',
        icon: XCircle,
        style: 'bg-slate-100 hover:bg-slate-200 text-slate-700',
      });
    }

    return actions;
  };

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <StaffTabs />
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-sm">
          <Loader2 className="w-8 h-8 text-indigo-600 animate-spin mx-auto mb-3" />
          <p className="text-xs font-medium text-slate-500">Loading intervention record details...</p>
        </div>
      </div>
    );
  }

  if (isError || !detail) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <StaffTabs />
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center text-xs text-rose-800">
          <AlertTriangle className="w-6 h-6 text-rose-600 mx-auto mb-2" />
          <p className="font-semibold">Unable to load intervention record.</p>
          <p className="mt-1 text-slate-600">
            {(error as any)?.response?.data?.detail || 'Record not found or access denied.'}
          </p>
          <Link
            to="/staff/interventions"
            className="inline-flex items-center gap-1.5 mt-4 px-4 py-2 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Interventions
          </Link>
        </div>
      </div>
    );
  }

  const validActions = getCounsellorActions(detail.status);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <StaffTabs />

      {/* Back button and breadcrumb */}
      <div className="flex items-center justify-between gap-4 mb-6">
        <Link
          to="/staff/interventions"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-indigo-600 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Interventions List
        </Link>
        <span className="text-xs font-mono text-slate-400">
          ID: {detail.id}
        </span>
      </div>

      {/* Banner Feedback */}
      {actionSuccess && (
        <div className="mb-6 bg-emerald-50 border border-emerald-200 rounded-2xl p-4 text-xs text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {actionError && (
        <div className="mb-6 bg-rose-50 border border-rose-200 rounded-2xl p-4 text-xs text-rose-800 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Top Hero Card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm mb-6">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-6 pb-6 border-b border-slate-100">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2.5">
              <span
                className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold border uppercase tracking-wider ${getStatusBadge(
                  detail.status
                )}`}
              >
                {detail.status}
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 uppercase tracking-wider">
                Origin: {detail.origin}
              </span>
              {detail.recommendation_id && (
                <Link
                  to={`/staff/recommendations/${encodeURIComponent(detail.recommendation_id)}`}
                  className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  Linked Recommendation
                </Link>
              )}
            </div>

            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              {detail.label}
            </h1>
            <p className="text-xs text-slate-600 max-w-2xl leading-relaxed">
              {detail.description}
            </p>
          </div>

          <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 min-w-[260px] space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Student PID:</span>
              <Link
                to={`/staff/students/${encodeURIComponent(detail.pid)}`}
                className="font-mono font-bold text-indigo-600 hover:underline flex items-center gap-1"
              >
                <Shield className="w-3.5 h-3.5 text-indigo-500" />
                {detail.pid}
              </Link>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Course:</span>
              <span className="font-mono font-semibold text-slate-800">{detail.course_id}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Delivery Module:</span>
              <span className="font-semibold text-slate-800">{detail.delivery_module}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Created:</span>
              <span className="text-slate-700">{new Date(detail.created_at).toLocaleDateString()}</span>
            </div>
          </div>
        </div>

        {/* Student-Facing Preview */}
        <div className="mt-5 p-3.5 rounded-xl bg-indigo-50/50 border border-indigo-100 text-xs text-indigo-900 flex items-start gap-2.5">
          <Sparkles className="w-4 h-4 text-indigo-600 flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-bold block uppercase tracking-wider text-[11px] text-indigo-700">
              Student-Facing Communication Title
            </span>
            <p className="mt-0.5 text-slate-800 italic">"{detail.student_label}"</p>
          </div>
        </div>
      </div>

      {/* Main Grid: Left Operational Controls & Right Timeline / Notes */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Col: Assignment, Scheduling, Lifecycle transitions */}
        <div className="space-y-6 lg:col-span-1">
          {/* Assignment Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
              <UserCheck className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Assigned Staff Member
              </h3>
            </div>

            <div>
              <label className="text-xs text-slate-500 block mb-1.5">
                Designate counselor / academic lead responsible for delivery:
              </label>
              <select
                value={selectedStaff || detail.assigned_to || ''}
                onChange={(e) => handleAssignStaff(e.target.value)}
                disabled={patchMutation.isPending}
                className="w-full text-xs border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              >
                <option value="">-- Unassigned --</option>
                {staffMembers?.map((staff: StaffMemberItem) => (
                  <option key={staff.id} value={staff.id}>
                    {staff.full_name} ({staff.role})
                  </option>
                ))}
              </select>
            </div>

            {detail.assigned_staff_name && (
              <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-800 text-[11px] flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                <span>Currently assigned to <strong>{detail.assigned_staff_name}</strong></span>
              </div>
            )}
          </div>

          {/* Schedule Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
              <Calendar className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Intervention Schedule
              </h3>
            </div>

            {detail.scheduled_for ? (
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-xs">
                <span className="text-slate-500 block text-[11px]">Confirmed Slot:</span>
                <span className="font-semibold text-slate-900">
                  {new Date(detail.scheduled_for).toLocaleString()}
                </span>
              </div>
            ) : (
              <p className="text-xs text-slate-500">
                No session datetime scheduled yet.
              </p>
            )}

            <form onSubmit={handleScheduleSubmit} className="space-y-3">
              <label className="text-xs text-slate-600 block">
                Schedule / reschedule date & time:
              </label>
              <input
                type="datetime-local"
                min={new Date().toISOString().slice(0, 16)}
                value={scheduledDateTime}
                onChange={(e) => setScheduledDateTime(e.target.value)}
                className="w-full text-xs border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              />
              <button
                type="submit"
                disabled={!scheduledDateTime || patchMutation.isPending}
                className="w-full py-2 px-3 rounded-xl text-xs font-semibold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition disabled:opacity-40"
              >
                Save Schedule
              </button>
            </form>
          </div>

          {/* Lifecycle Action Buttons */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
              <Layers className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Lifecycle Transitions
              </h3>
            </div>

            {validActions.length === 0 ? (
              <p className="text-xs text-slate-500 italic">
                {['completed', 'cancelled', 'declined'].includes(detail.status.toLowerCase())
                  ? `Record is in terminal state '${detail.status}'. No further transitions permitted.`
                  : 'No counselor transitions available for this current state.'}
              </p>
            ) : (
              <div className="space-y-2">
                <p className="text-xs text-slate-500">
                  Advance intervention state according to clinical protocol:
                </p>
                {validActions.map((act) => {
                  const Icon = act.icon;
                  return (
                    <button
                      key={act.target}
                      onClick={() => {
                        setPendingStatus(act.target);
                        setTransitionNote('');
                      }}
                      className={`w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-semibold shadow-sm transition ${act.style}`}
                    >
                      <Icon className="w-4 h-4" />
                      {act.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Baseline Snapshot Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-3">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
              <FileText className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Baseline Analytics Snapshot
              </h3>
            </div>

            <p className="text-[11px] text-slate-500 leading-relaxed">
              Locked snapshot captured at review time for outcome delta evaluation (FR10/FR8).
            </p>

            <div className="bg-slate-50 rounded-xl p-3 border border-slate-100 space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-500">Week Index:</span>
                <span className="font-semibold text-slate-800">
                  {detail.baseline_snapshot?.week_index ?? 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Risk Score:</span>
                <span className="font-mono font-semibold text-slate-800">
                  {detail.baseline_snapshot?.risk_score != null
                    ? detail.baseline_snapshot.risk_score.toFixed(3)
                    : 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Risk Tier:</span>
                <span className="font-semibold capitalize text-slate-800">
                  {detail.baseline_snapshot?.risk_tier ?? 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Top Emotion:</span>
                <span className="font-semibold capitalize text-slate-800">
                  {detail.baseline_snapshot?.top_emotion ?? 'N/A'}
                </span>
              </div>
              {detail.baseline_snapshot?.captured_at && (
                <div className="flex justify-between pt-1 border-t border-slate-200/60 text-[11px]">
                  <span className="text-slate-400">Captured:</span>
                  <span className="text-slate-500">
                    {new Date(detail.baseline_snapshot.captured_at).toLocaleDateString()}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Col: Timeline & Notes Thread */}
        <div className="space-y-6 lg:col-span-2">
          {/* Status History Timeline */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center gap-2 pb-4 border-b border-slate-100 mb-6">
              <Clock className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Lifecycle Status Timeline
              </h3>
            </div>

            <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
              {detail.status_history.map((sh, idx) => (
                <div key={idx} className="relative">
                  <div className="absolute -left-6 top-0.5 w-4 h-4 rounded-full bg-white border-2 border-indigo-600 flex items-center justify-center">
                    <div className="w-1.5 h-1.5 rounded-full bg-indigo-600" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs uppercase tracking-wider text-slate-900">
                        {sh.to_status}
                      </span>
                      <span className="text-[11px] text-slate-400">
                        {new Date(sh.changed_at).toLocaleString()}
                      </span>
                    </div>
                    {sh.note && (
                      <p className="mt-1 text-xs text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                        "{sh.note}"
                      </p>
                    )}
                    <span className="text-[10px] text-slate-400 block mt-0.5">
                      Actor: {sh.changed_by}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Confidential Staff Notes Thread */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-4">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-indigo-600" />
                <div>
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Staff Clinical Case Notes
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Confidential counselor observations. Immutable, strictly excluded from institutional contract exports.
                  </p>
                </div>
              </div>
              <span className="text-xs font-mono font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                {detail.notes?.length || 0} / 50 notes
              </span>
            </div>

            {/* Existing Notes */}
            <div className="space-y-3 mb-6 max-h-96 overflow-y-auto">
              {!detail.notes || detail.notes.length === 0 ? (
                <div className="p-6 text-center text-xs text-slate-400 italic bg-slate-50 rounded-xl">
                  No counselor notes added yet.
                </div>
              ) : (
                detail.notes.map((note) => (
                  <div
                    key={note.note_id}
                    className="p-4 rounded-xl bg-slate-50 border border-slate-100 text-xs text-slate-700 space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-[11px] text-slate-500">
                      <div className="flex items-center gap-1.5 font-semibold text-slate-800">
                        <User className="w-3.5 h-3.5 text-indigo-600" />
                        <span>Counselor ({note.author_role})</span>
                      </div>
                      <span>{new Date(note.created_at).toLocaleString()}</span>
                    </div>
                    <p className="leading-relaxed whitespace-pre-wrap text-slate-800 font-sans">
                      {note.content}
                    </p>
                  </div>
                ))
              )}
            </div>

            {/* Add Note Form */}
            <form onSubmit={handleAddNote} className="space-y-3 pt-4 border-t border-slate-100">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5 text-slate-400" />
                  Append Confidential Note (1 - 2000 chars)
                </label>
                <span className="text-[11px] text-slate-400 font-mono">
                  {noteContent.length} / 2000
                </span>
              </div>
              <textarea
                rows={3}
                maxLength={2000}
                placeholder="Record session notes, student feedback, or intervention adjustments..."
                value={noteContent}
                onChange={(e) => setNoteContent(e.target.value)}
                disabled={(detail.notes?.length || 0) >= 50 || addNoteMutation.isPending}
                className="w-full text-xs border-slate-200 rounded-xl p-3 bg-slate-50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
              />
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={!noteContent.trim() || (detail.notes?.length || 0) >= 50 || addNoteMutation.isPending}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition disabled:opacity-50"
                >
                  {addNoteMutation.isPending ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Appending...
                    </>
                  ) : (
                    'Add Case Note'
                  )}
                </button>
              </div>
            </form>
          </div>

          {/* Dushan: F35 outcome section */}
          <OutcomeSection
            interventionId={detail.id}
            status={detail.status}
            onOutcomeSaved={() => refetch()}
          />

          {/* Dushan: F38 delivery panel */}
          <DeliveryPanel
            interventionId={detail.id}
            interventionType={detail.intervention_type}
            status={detail.status}
            onResourceShared={() => refetch()}
          />


          {/* Dushan: F39 feedback panel */}
          <FeedbackPanel interventionId={detail.id} />
        </div>
      </div>

      {/* Transition Confirmation Modal */}
      {pendingStatus && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-600">
                <Layers className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-base font-bold text-slate-900">
                  Confirm Lifecycle Transition
                </h4>
                <p className="text-xs text-slate-500">
                  Advance status to <strong className="uppercase text-indigo-600">{pendingStatus}</strong>.
                </p>
              </div>
            </div>

            <div className="space-y-4 mb-5">
              <p className="text-xs text-slate-600 leading-relaxed">
                You are transitioning this intervention from{' '}
                <strong className="text-slate-900 uppercase">{detail.status}</strong> to{' '}
                <strong className="text-slate-900 uppercase">{pendingStatus}</strong>.
                {pendingStatus === 'offered' &&
                  ' This will notify and offer the intervention to the student.'}
              </p>

              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Optional Transition Note (max 500 chars):
                </label>
                <textarea
                  rows={2}
                  maxLength={500}
                  placeholder="Reason or operational context for this state change..."
                  value={transitionNote}
                  onChange={(e) => setTransitionNote(e.target.value)}
                  className="w-full text-xs border-slate-200 rounded-xl p-2.5 bg-slate-50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setPendingStatus(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={patchMutation.isPending}
                onClick={handleConfirmTransition}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition disabled:opacity-50"
              >
                {patchMutation.isPending ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Transitioning...
                  </>
                ) : (
                  'Confirm State Change'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
