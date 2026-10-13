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
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
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
} from 'lucide-react';
import {
  staffResourcesApi,
  SupportResourceItem,
  SharedResourceItem,
} from '../../api/staffResources';

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
      {/* Expansion Slot: Part D (F38-D Peer Mentoring Connection) */}

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
