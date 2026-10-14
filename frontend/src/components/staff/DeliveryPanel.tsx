/**
 * src/components/staff/DeliveryPanel.tsx
 *
 * Feature 38-C: Intervention Delivery Panel (Resource, Guidance & Referral Sharing).
 * Embedded in StaffInterventionDetailPage to enable:
 *   1. Selecting and sharing cataloged resources with the student.
 *   2. Viewing the history of shared learning materials and referrals.
 *   3. Monitoring student engagement uptake through the 'viewed' status.
 *
 * Contains expansion slots for:
 *   - Part B: Counselling Booking (F38-B)
 *   - Part D: Peer Mentoring (F38-D)
 */

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Calendar,
  BookOpen,
  Share2,
  ExternalLink,
  PhoneCall,
  CheckCircle2,
  EyeOff,
  AlertCircle,
  Loader2,
  Sparkles,
  Info,
  Clock,
  MessageSquare,
  FileText,
  UserCheck,
  Users,
  UserPlus,
  Search,
  XCircle,
} from 'lucide-react';
import {
  staffResourcesApi,
  SupportResourceItem,
  SharedResourceItem,
} from '../../api/staffResources';
import {
  staffMentoringApi,
  CandidateStudent,
} from '../../api/staffMentoring';

interface DeliveryPanelProps {
  interventionId: string;
  interventionType: string;
  status: string;
  onResourceShared?: () => void;
}

export const DeliveryPanel: React.FC<DeliveryPanelProps> = ({
  interventionId,
  interventionType,
  status,
  onResourceShared,
}) => {
  const queryClient = useQueryClient();

  const [selectedResourceId, setSelectedResourceId] = useState<string>('');
  const [shareMessage, setShareMessage] = useState<string>('');
  const [filterByInterventionType, setFilterByInterventionType] = useState<boolean>(true);
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  // Fetch active resources for sharing
  const {
    data: resourcesData,
    isLoading: isLoadingResources,
  } = useQuery({
    queryKey: ['staff-resources-active'],
    queryFn: () => staffResourcesApi.getResources({ active: true }),
  });

  // Fetch already shared resources for this intervention
  const {
    data: sharedData,
    isLoading: isLoadingShared,
    refetch: refetchShared,
  } = useQuery({
    queryKey: ['intervention-shared-resources', interventionId],
    queryFn: () => staffResourcesApi.getSharedResources(interventionId),
    enabled: !!interventionId,
  });

  // Share mutation
  const shareMutation = useMutation({
    mutationFn: (payload: { resource_id: string; message?: string | null }) =>
      staffResourcesApi.shareResource(interventionId, payload),
    onSuccess: (res) => {
      setFeedbackError(null);
      setFeedbackSuccess(`Successfully shared "${res.title}" with student.`);
      setSelectedResourceId('');
      setShareMessage('');
      refetchShared();
      queryClient.invalidateQueries({ queryKey: ['staff-intervention-detail', interventionId] });
      if (onResourceShared) {
        onResourceShared();
      }
      setTimeout(() => setFeedbackSuccess(null), 5000);
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to share resource. Please check status eligibility.';
      setFeedbackError(detail);
    },
  });

  const handleShareSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedResourceId) return;
    setFeedbackError(null);
    shareMutation.mutate({
      resource_id: selectedResourceId,
      message: shareMessage.trim() ? shareMessage.trim() : null,
    });
  };

  // State eligibility checks
  const isAcceptedOrInProgress = status === 'accepted' || status === 'in_progress';
  const isOffered = status === 'offered';
  const canShareReferralsOnly = isOffered;
  const canShareAny = isAcceptedOrInProgress;
  const canShareAtAll = canShareAny || canShareReferralsOnly;

  // Mentoring state and queries (Feature 38-D)
  const isPeerMentoring = interventionType.toLowerCase() === 'peer_mentoring';
  const [mentorSearchQuery, setMentorSearchQuery] = useState<string>('');

  const {
    data: mentoringAssignment,
    isLoading: isLoadingMentoring,
    refetch: refetchMentoring,
  } = useQuery({
    queryKey: ['staff-mentoring-assignment', interventionId],
    queryFn: () => staffMentoringApi.getAssignment(interventionId),
    enabled: Boolean(interventionId) && isPeerMentoring,
  });

  const {
    data: candidateData,
    isLoading: isLoadingCandidates,
  } = useQuery({
    queryKey: ['staff-mentor-candidates', interventionId, mentorSearchQuery],
    queryFn: () => staffMentoringApi.getCandidates(mentorSearchQuery, interventionId),
    enabled: isPeerMentoring && isAcceptedOrInProgress && !mentoringAssignment,
  });

  const assignMentorMutation = useMutation({
    mutationFn: (mentorUserId: string) =>
      staffMentoringApi.assignMentor(interventionId, mentorUserId),
    onSuccess: (res) => {
      setFeedbackError(null);
      setFeedbackSuccess(
        `Successfully paired peer mentor "${res.mentor_name}". Both students have been notified.`
      );
      refetchMentoring();
      queryClient.invalidateQueries({
        queryKey: ['staff-intervention-detail', interventionId],
      });
      if (onResourceShared) onResourceShared();
      setTimeout(() => setFeedbackSuccess(null), 5000);
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to assign peer mentor.';
      setFeedbackError(detail);
    },
  });

  const endMentoringMutation = useMutation({
    mutationFn: (assignmentId: string) =>
      staffMentoringApi.endAssignment(assignmentId),
    onSuccess: () => {
      setFeedbackError(null);
      setFeedbackSuccess('Peer mentoring assignment concluded.');
      refetchMentoring();
      queryClient.invalidateQueries({
        queryKey: ['staff-intervention-detail', interventionId],
      });
      if (onResourceShared) onResourceShared();
      setTimeout(() => setFeedbackSuccess(null), 5000);
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to end mentoring assignment.';
      setFeedbackError(detail);
    },
  });

  // Filter available resources
  const availableResources = (resourcesData?.items || []).filter((r: SupportResourceItem) => {
    if (canShareReferralsOnly && r.resource_type !== 'referral') {
      return false;
    }
    if (filterByInterventionType) {
      if (r.intervention_types && r.intervention_types.length > 0) {
        return r.intervention_types.includes(interventionType.toLowerCase());
      }
      return true;
    }
    return true;
  });

  const getResourceTypeBadge = (type: string) => {
    switch (type) {
      case 'guidance':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-sky-50 text-sky-700 border border-sky-200">
            <FileText className="w-3 h-3" />
            Guidance Note
          </span>
        );
      case 'referral':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-purple-50 text-purple-700 border border-purple-200">
            <PhoneCall className="w-3 h-3" />
            Campus Referral
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <BookOpen className="w-3 h-3" />
            Learning Resource
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
      {/* Panel Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-4 border-b border-slate-100">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-indigo-50 text-indigo-600">
            <Share2 className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
              Intervention Delivery: Resources & Referrals
            </h3>
            <p className="text-xs text-slate-500">
              Share supplementary materials, time-management guides, or institutional service referrals.
            </p>
          </div>
        </div>
        <span className="text-xs font-mono font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200 self-start sm:self-auto">
          {sharedData?.total_count || 0} Shared
        </span>
      </div>

      {/* Expansion Slot: Part B (F38-B Counselling Booking) */}
      {interventionType.toLowerCase() === 'counselling_mental_health' && (
        <div className="p-3.5 rounded-xl bg-indigo-50/60 border border-indigo-100 flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 text-indigo-900">
            <Calendar className="w-4 h-4 text-indigo-600 flex-shrink-0" />
            <span>
              <strong>Counselling Delivery Module:</strong> Appointment slots can be published and managed in the Slots schedule.
            </span>
          </div>
          <Link
            to="/staff/slots"
            className="inline-flex items-center gap-1 font-semibold text-indigo-600 hover:text-indigo-800 transition"
          >
            <span>Manage Slots</span>
            <ExternalLink className="w-3 h-3" />
          </Link>
        </div>
      )}
      {/* Expansion Slot: Part D (F38-D Peer Mentoring Connection) */}
      {isPeerMentoring && (
        <div className="p-5 rounded-2xl border border-indigo-200 bg-white shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-100">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-600">
                <Users className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-900">
                  Peer Mentoring Connection
                </h4>
                <p className="text-xs text-slate-500">
                  Pair this student with a trained senior peer mentor for course encouragement and study tips.
                </p>
              </div>
            </div>
            {mentoringAssignment && mentoringAssignment.status === 'active' && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 self-start sm:self-auto">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                Active Mentorship
              </span>
            )}
          </div>

          {isLoadingMentoring ? (
            <div className="p-6 text-center text-xs text-slate-500">
              <Loader2 className="w-5 h-5 text-indigo-600 animate-spin mx-auto mb-2" />
              <span>Loading mentoring status...</span>
            </div>
          ) : mentoringAssignment && mentoringAssignment.status === 'active' ? (
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <UserCheck className="w-4 h-4 text-indigo-600" />
                  <span className="text-sm font-bold text-slate-900">
                    {mentoringAssignment.mentor_name || 'Assigned Peer Mentor'}
                  </span>
                </div>
                <div className="text-xs text-slate-500 flex items-center gap-3">
                  <span>Matched: {new Date(mentoringAssignment.created_at).toLocaleDateString()}</span>
                  <span className="text-slate-400">·</span>
                  <span>Direct Chat: Active</span>
                </div>
              </div>

              <button
                type="button"
                disabled={endMentoringMutation.isPending}
                onClick={() => {
                  if (confirm('Conclude this peer mentoring connection? The mentor and mentee will no longer be active study partners.')) {
                    endMentoringMutation.mutate(mentoringAssignment.id);
                  }
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-rose-200 text-rose-600 bg-white hover:bg-rose-50 text-xs font-semibold transition self-start sm:self-auto"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>End Mentorship</span>
              </button>
            </div>
          ) : isOffered ? (
            <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-start gap-2.5">
              <Info className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Mentee Has Not Accepted Yet</p>
                <p className="mt-0.5 text-amber-800">
                  Strict Privacy Policy: Peer mentors can only be matched after the mentee voluntarily accepts this support initiative.
                </p>
              </div>
            </div>
          ) : isAcceptedOrInProgress ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    placeholder="Search active students to pair as peer mentor..."
                    value={mentorSearchQuery}
                    onChange={(e) => setMentorSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-xs border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
              </div>

              {isLoadingCandidates ? (
                <div className="p-4 text-center text-xs text-slate-500">
                  <Loader2 className="w-4 h-4 text-indigo-600 animate-spin mx-auto mb-1" />
                  <span>Searching student candidates...</span>
                </div>
              ) : (candidateData?.items || []).length === 0 ? (
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-center text-xs text-slate-500">
                  <span>No student candidates found matching "{mentorSearchQuery}".</span>
                </div>
              ) : (
                <div className="max-h-56 overflow-y-auto space-y-1.5 pr-1">
                  {(candidateData?.items || []).map((cand: CandidateStudent) => (
                    <div
                      key={cand.id}
                      className="p-2.5 rounded-xl border border-slate-200 bg-slate-50/50 hover:bg-white flex items-center justify-between gap-3 text-xs transition"
                    >
                      <div className="flex items-center gap-2">
                        <Users className="w-3.5 h-3.5 text-indigo-500" />
                        <span className="font-semibold text-slate-800">{cand.full_name}</span>
                      </div>
                      <button
                        type="button"
                        disabled={assignMentorMutation.isPending}
                        onClick={() => assignMentorMutation.mutate(cand.id)}
                        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm transition disabled:opacity-50"
                      >
                        <UserPlus className="w-3.5 h-3.5" />
                        <span>Pair as Mentor</span>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </div>
      )}

      {/* Notification Banner */}
      {feedbackSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{feedbackSuccess}</span>
        </div>
      )}

      {feedbackError && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{feedbackError}</span>
        </div>
      )}

      {/* Status Warning Banner when not eligible */}
      {!canShareAtAll && (
        <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-start gap-2.5">
          <Info className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Resource Sharing Inactive</p>
            <p className="mt-0.5 text-amber-800">
              Resource and referral sharing is active when an intervention is{' '}
              <strong>accepted</strong> or <strong>in_progress</strong> (or offered for referrals).
              Current status: <strong className="uppercase">{status}</strong>.
            </p>
          </div>
        </div>
      )}

      {/* Share Resource Form */}
      {canShareAtAll && (
        <form onSubmit={handleShareSubmit} className="space-y-4 p-4 rounded-xl bg-slate-50 border border-slate-100">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              Share from Resource Library
            </h4>
            <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
              <input
                type="checkbox"
                checked={filterByInterventionType}
                onChange={(e) => setFilterByInterventionType(e.target.checked)}
                className="rounded text-indigo-600 focus:ring-indigo-500"
              />
              <span>Filter by intervention type</span>
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Resource Selector */}
            <div>
              <label className="text-xs text-slate-600 block mb-1">
                Select Library Resource or Referral <span className="text-rose-500">*</span>:
              </label>
              <select
                value={selectedResourceId}
                onChange={(e) => setSelectedResourceId(e.target.value)}
                disabled={shareMutation.isPending || isLoadingResources}
                className="w-full text-xs border-slate-200 rounded-xl px-3 py-2 bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                required
              >
                <option value="">-- Choose active material --</option>
                {availableResources.map((res: SupportResourceItem) => (
                  <option key={res.id} value={res.id}>
                    [{res.resource_type.toUpperCase()}] {res.title}
                  </option>
                ))}
              </select>
              {availableResources.length === 0 && (
                <p className="text-[11px] text-slate-400 mt-1">
                  No matching active resources. Toggle filter above or add resources in the Resources tab.
                </p>
              )}
            </div>

            {/* Optional Personal Note */}
            <div>
              <label className="text-xs text-slate-600 block mb-1">
                Optional Counselor Guidance Note (max 300 chars):
              </label>
              <input
                type="text"
                maxLength={300}
                placeholder="e.g., Focus on sections 2 and 4 for this week's assignment."
                value={shareMessage}
                onChange={(e) => setShareMessage(e.target.value)}
                disabled={shareMutation.isPending}
                className="w-full text-xs border-slate-200 rounded-xl px-3 py-2 bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div className="flex items-center justify-end pt-1">
            <button
              type="submit"
              disabled={!selectedResourceId || shareMutation.isPending}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition disabled:opacity-40"
            >
              {shareMutation.isPending ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Sharing...
                </>
              ) : (
                <>
                  <Share2 className="w-3.5 h-3.5" />
                  Share with Student
                </>
              )}
            </button>
          </div>
        </form>
      )}

      {/* Shared Materials History Table / Cards */}
      <div className="space-y-3">
        <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
          <BookOpen className="w-3.5 h-3.5 text-indigo-600" />
          Shared Materials & Referral Uptake
        </h4>

        {isLoadingShared ? (
          <div className="p-6 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
            Loading shared materials...
          </div>
        ) : !sharedData?.items || sharedData.items.length === 0 ? (
          <div className="p-6 text-center rounded-xl bg-slate-50 border border-dashed border-slate-200 text-xs text-slate-400">
            No resources or referrals shared with this student yet.
          </div>
        ) : (
          <div className="space-y-3">
            {sharedData.items.map((item: SharedResourceItem, idx: number) => (
              <div
                key={idx}
                className="p-4 rounded-xl border border-slate-200 hover:border-slate-300 transition bg-white flex flex-col md:flex-row md:items-start justify-between gap-4"
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold text-slate-900">
                      {item.title}
                    </span>
                    {getResourceTypeBadge(item.resource_type)}
                  </div>

                  {item.description && (
                    <p className="text-xs text-slate-600 leading-relaxed">
                      {item.description}
                    </p>
                  )}

                  {/* Destination link or contact */}
                  <div className="flex flex-wrap items-center gap-3 text-xs pt-1">
                    {item.url && (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 font-semibold break-all"
                      >
                        <ExternalLink className="w-3 h-3" />
                        {item.url}
                      </a>
                    )}
                    {item.contact_info && (
                      <span className="inline-flex items-center gap-1 text-slate-700 bg-slate-100 px-2 py-0.5 rounded-lg text-[11px]">
                        <PhoneCall className="w-3 h-3 text-slate-500" />
                        {item.contact_info}
                      </span>
                    )}
                  </div>

                  {/* Counselor Note */}
                  {item.message && (
                    <div className="mt-2 p-2.5 rounded-lg bg-indigo-50/50 border border-indigo-100 text-xs text-indigo-900 flex items-start gap-2">
                      <MessageSquare className="w-3.5 h-3.5 text-indigo-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold block text-[11px] text-indigo-800">
                          Counselor Message:
                        </span>
                        <p className="italic">"{item.message}"</p>
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-2 text-[11px] text-slate-400 pt-1">
                    <Clock className="w-3 h-3" />
                    <span>Shared {new Date(item.shared_at).toLocaleString()}</span>
                  </div>
                </div>

                {/* Engagement / Uptake Signal Badge */}
                <div className="flex-shrink-0 self-start md:self-center">
                  {item.viewed_at ? (
                    <div className="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <div>
                        <span className="font-bold block">Viewed by Student</span>
                        <span className="text-[10px] text-emerald-700">
                          {new Date(item.viewed_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-slate-500 text-xs flex items-center gap-2">
                      <EyeOff className="w-4 h-4 text-slate-400" />
                      <div>
                        <span className="font-semibold block">Not Viewed Yet</span>
                        <span className="text-[10px] text-slate-400">Awaiting student access</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
