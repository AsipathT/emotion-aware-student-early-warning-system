/**
 * src/components/staff/FeedbackPanel.tsx
 *
 * Feature 39: Student Feedback Detail Panel for Staff Intervention Inspector.
 * Displays student-reported helpfulness rating, attendance status, reported barriers,
 * and confidential scrubbed comments.
 */

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Star,
  MessageSquare,
  Lock,
  Calendar,
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  HelpCircle,
} from 'lucide-react';
import { staffFeedbackApi, StaffFeedbackDetailResponse } from '../../api/staffFeedback';

interface FeedbackPanelProps {
  interventionId: string;
}

const BARRIER_LABELS: Record<string, string> = {
  time: 'Schedule Conflict / Lack of Time',
  not_relevant: 'Content Not Relevant to Need',
  uncomfortable: 'Felt Uncomfortable or Hesitant',
  technical: 'Technical or Access Issue',
  other: 'Other Personal Barrier',
};

export const FeedbackPanel: React.FC<FeedbackPanelProps> = ({ interventionId }) => {
  const {
    data: feedback,
    isLoading,
    isError,
  } = useQuery<StaffFeedbackDetailResponse, any>({
    queryKey: ['staff-feedback', interventionId],
    queryFn: () => staffFeedbackApi.getInterventionFeedback(interventionId),
    retry: false,
    staleTime: 30000,
  });

  const getAttendanceBadge = (attended: string) => {
    switch (attended) {
      case 'yes':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            Fully Attended
          </span>
        );
      case 'partly':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3.5 h-3.5 text-amber-600" />
            Partially Attended
          </span>
        );
      case 'no':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
            Did Not Attend
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            {attended}
          </span>
        );
    }
  };

  const getHelpfulnessText = (rating: number) => {
    switch (rating) {
      case 5:
        return 'Extremely Helpful';
      case 4:
        return 'Helpful';
      case 3:
        return 'Moderately Helpful';
      case 2:
        return 'Slightly Helpful';
      case 1:
        return 'Not Helpful';
      default:
        return `${rating} / 5`;
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-5">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-600">
            <MessageSquare className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">
              Student Experience Feedback
            </h3>
            <p className="text-xs text-slate-500">
              Self-reported helpfulness and uptake response (C4 Feedback Loop / F39).
            </p>
          </div>
        </div>

        {feedback && (
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span>
              Submitted {new Date(feedback.created_at).toLocaleDateString()}
            </span>
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="py-8 flex flex-col items-center justify-center text-slate-400 gap-2">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
          <span className="text-xs">Loading student feedback...</span>
        </div>
      ) : isError || !feedback ? (
        <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200/80 text-center">
          <HelpCircle className="w-7 h-7 text-slate-400 mx-auto mb-2" />
          <h4 className="text-sm font-semibold text-slate-800 mb-1">
            No Student Feedback Yet
          </h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            The student has not yet submitted their experience evaluation. Feedback surveys become active once the intervention is accepted or completed.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          {/* Rating and Attendance overview */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Helpfulness Score */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-xs font-medium text-slate-500 block mb-1.5">
                Helpfulness Rating
              </span>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1">
                  {[1, 2, 3, 4, 5].map((starVal) => (
                    <Star
                      key={starVal}
                      className={`w-5 h-5 ${
                        starVal <= feedback.helpfulness
                          ? 'fill-amber-400 text-amber-400'
                          : 'fill-slate-200 text-slate-200'
                      }`}
                    />
                  ))}
                </div>
                <div className="text-sm font-bold text-slate-800">
                  {feedback.helpfulness}/5{' '}
                  <span className="text-xs font-normal text-slate-500">
                    ({getHelpfulnessText(feedback.helpfulness)})
                  </span>
                </div>
              </div>
            </div>

            {/* Attendance Status */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between">
              <span className="text-xs font-medium text-slate-500 block mb-1.5">
                Session Attendance
              </span>
              <div>{getAttendanceBadge(feedback.attended)}</div>
            </div>
          </div>

          {/* Barrier chip if reported */}
          {feedback.barrier && (
            <div className="p-3.5 rounded-xl bg-amber-50/60 border border-amber-200 text-xs">
              <span className="font-semibold text-amber-900 block mb-1">
                Reported Barrier / Hindrance:
              </span>
              <span className="inline-flex items-center gap-1.5 text-amber-800 font-medium">
                <AlertCircle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                {BARRIER_LABELS[feedback.barrier] || feedback.barrier}
              </span>
            </div>
          )}

          {/* Private Free-Text Comment */}
          {feedback.comment && (
            <div className="p-4 rounded-xl bg-indigo-50/40 border border-indigo-100 space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-indigo-900">
                <Lock className="w-3.5 h-3.5 text-indigo-600" />
                <span>Confidential Student Comment</span>
                <span className="text-[10px] text-slate-500 font-normal">
                  (PII-scrubbed & excluded from research exports)
                </span>
              </div>
              <p className="text-xs text-slate-700 italic bg-white p-3 rounded-lg border border-indigo-100/60 shadow-sm leading-relaxed">
                "{feedback.comment}"
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
