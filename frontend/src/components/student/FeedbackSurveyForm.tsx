/**
 * src/components/student/FeedbackSurveyForm.tsx
 *
 * Feature 39: Student Feedback Survey Form (Component 4 Feedback Loop).
 * Allows students to submit 5-star helpfulness rating, attendance status,
 * optional barrier chips, and confidential comments.
 */

import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Star,
  AlertTriangle,
  Loader2,
  Lock,
  ChevronDown,
  ChevronUp,
  MessageSquareHeart,
  Send,
} from 'lucide-react';
import { supportApi, StudentFeedbackPayload } from '../../api/support';

interface FeedbackSurveyFormProps {
  interventionId: string;
  studentLabel: string;
  onSubmitted: () => void;
}

const BARRIER_OPTIONS: { value: 'time' | 'not_relevant' | 'uncomfortable' | 'technical' | 'other'; label: string }[] = [
  { value: 'time', label: 'Schedule conflict / No time' },
  { value: 'not_relevant', label: 'Not relevant to my need' },
  { value: 'uncomfortable', label: 'Felt uncomfortable / hesitant' },
  { value: 'technical', label: 'Technical / access issue' },
  { value: 'other', label: 'Other personal reason' },
];

export const FeedbackSurveyForm: React.FC<FeedbackSurveyFormProps> = ({
  interventionId,
  studentLabel,
  onSubmitted,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [helpfulness, setHelpfulness] = useState<number>(5);
  const [hoverRating, setHoverRating] = useState<number>(0);
  const [attended, setAttended] = useState<'yes' | 'partly' | 'no'>('yes');
  const [barrier, setBarrier] = useState<'time' | 'not_relevant' | 'uncomfortable' | 'technical' | 'other' | null>(null);
  const [comment, setComment] = useState<string>('');
  const [submitError, setSubmitError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: StudentFeedbackPayload) =>
      supportApi.submitFeedback(interventionId, payload),
    onSuccess: () => {
      onSubmitted();
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to submit feedback. Please try again.';
      setSubmitError(detail);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    mutation.mutate({
      helpfulness,
      attended,
      barrier: barrier || null,
      comment: comment.trim() ? comment.trim() : null,
    });
  };

  const activeStarRating = hoverRating || helpfulness;

  return (
    <div className="pt-3 border-t border-slate-100">
      {!isExpanded ? (
        <button
          onClick={() => setIsExpanded(true)}
          className="w-full p-3 rounded-xl bg-indigo-50/60 border border-indigo-100 hover:bg-indigo-50 text-indigo-700 text-xs font-semibold flex items-center justify-between transition group"
        >
          <div className="flex items-center gap-2">
            <MessageSquareHeart className="w-4 h-4 text-indigo-600 group-hover:scale-110 transition-transform" />
            <span>How was your experience? Share quick feedback (1 min)</span>
          </div>
          <div className="flex items-center gap-1 text-[11px] font-medium text-indigo-500">
            <span>Rate support</span>
            <ChevronDown className="w-3.5 h-3.5" />
          </div>
        </button>
      ) : (
        <form
          onSubmit={handleSubmit}
          className="p-4 rounded-xl bg-slate-50 border border-slate-200/90 space-y-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MessageSquareHeart className="w-4 h-4 text-indigo-600" />
              <h5 className="text-xs font-bold text-slate-900">
                Feedback on {studentLabel}
              </h5>
            </div>
            <button
              type="button"
              onClick={() => setIsExpanded(false)}
              className="text-slate-400 hover:text-slate-600 text-xs flex items-center gap-0.5"
            >
              <span>Collapse</span>
              <ChevronUp className="w-3.5 h-3.5" />
            </button>
          </div>

          {submitError && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
              <span>{submitError}</span>
            </div>
          )}

          {/* 1. Helpfulness 5-Star Rating */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Did this support help you? (1 = Not helpful, 5 = Extremely helpful)
            </label>
            <div className="flex items-center gap-1.5">
              {[1, 2, 3, 4, 5].map((starVal) => (
                <button
                  key={starVal}
                  type="button"
                  onClick={() => setHelpfulness(starVal)}
                  onMouseEnter={() => setHoverRating(starVal)}
                  onMouseLeave={() => setHoverRating(0)}
                  className="p-1 focus:outline-none focus:ring-2 focus:ring-indigo-400 rounded-lg transition"
                >
                  <Star
                    className={`w-6 h-6 transition-colors ${
                      starVal <= activeStarRating
                        ? 'fill-amber-400 text-amber-400'
                        : 'fill-slate-200 text-slate-200 hover:fill-amber-200 hover:text-amber-200'
                    }`}
                  />
                </button>
              ))}
              <span className="ml-2 text-xs font-bold text-slate-700">
                {activeStarRating}/5
              </span>
            </div>
          </div>

          {/* 2. Attendance Status */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Did you attend or participate in this session / initiative?
            </label>
            <div className="flex flex-wrap gap-2">
              {(['yes', 'partly', 'no'] as const).map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => setAttended(opt)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold border transition ${
                    attended === opt
                      ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100'
                  }`}
                >
                  {opt === 'yes' && 'Yes, attended fully'}
                  {opt === 'partly' && 'Partially attended'}
                  {opt === 'no' && 'Could not attend'}
                </button>
              ))}
            </div>
          </div>

          {/* 3. Optional Barrier Chips */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Did you experience any barriers or challenges? (Optional)
            </label>
            <div className="flex flex-wrap gap-1.5">
              {BARRIER_OPTIONS.map((opt) => {
                const isSelected = barrier === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setBarrier(isSelected ? null : opt.value)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition ${
                      isSelected
                        ? 'bg-amber-100 text-amber-900 border-amber-300 shadow-xs'
                        : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 4. Optional Comment */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                <Lock className="w-3 h-3 text-indigo-500" />
                <span>Private comments for advisors (Optional)</span>
              </label>
              <span className="text-[10px] text-slate-400">
                {comment.length}/500
              </span>
            </div>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value.slice(0, 500))}
              rows={2}
              placeholder="What worked well, or how could we improve this support for you?"
              className="w-full text-xs px-3 py-2 rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition resize-none placeholder:text-slate-400 text-slate-800"
            />
            <p className="text-[10px] text-slate-400 mt-1 flex items-center gap-1">
              <Lock className="w-2.5 h-2.5 text-slate-400 flex-shrink-0" />
              <span>Comments are kept private in the LMS and omitted from research exports.</span>
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setIsExpanded(false)}
              className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-800 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition disabled:opacity-50"
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Submitting...</span>
                </>
              ) : (
                <>
                  <Send className="w-3.5 h-3.5" />
                  <span>Submit Feedback</span>
                </>
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
