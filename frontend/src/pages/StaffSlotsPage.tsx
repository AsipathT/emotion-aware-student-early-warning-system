/**
 * src/pages/StaffSlotsPage.tsx
 *
 * Feature 38-B: Staff Counselling Slot Publishing & Schedule Management Workspace.
 * Enables counsellors and administrators to:
 *   1. Publish confidential consultation appointment slots (date/time, duration, mode, link/room).
 *   2. View their upcoming schedule with real-time Open / Booked / Cancelled status indicators.
 *   3. Delete unbooked slots or cancel booked appointments with automated student notification.
 *
 * Research Link: Component 4 Intervention Delivery (sensitive mental health / counselling booking).
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Calendar,
  Clock,
  Video,
  MapPin,
  Plus,
  Trash2,
  XCircle,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Shield,
  Lock,
  ExternalLink,
  UserCheck,
  AlertTriangle,
  Info,
} from 'lucide-react';
import { StaffTabs } from '../components/staff/StaffTabs';
import {
  staffSlotsApi,
  CounsellingSlotItem,
  SlotCreatePayload,
  SlotMode,
} from '../api/staffSlots';

export const StaffSlotsPage: React.FC = () => {
  const queryClient = useQueryClient();

  // Slot creation form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [startAt, setStartAt] = useState('');
  const [durationMinutes, setDurationMinutes] = useState<number>(45);
  const [mode, setMode] = useState<SlotMode>('online');
  const [locationOrLink, setLocationOrLink] = useState('');

  // Status filter state
  const [filterStatus, setFilterStatus] = useState<'all' | 'open' | 'booked' | 'cancelled'>('all');

  // Cancel slot modal state
  const [slotToCancel, setSlotToCancel] = useState<CounsellingSlotItem | null>(null);

  // Notification banners
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  // Fetch slots for current counsellor
  const {
    data: slotsData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['staff-counselling-slots-mine'],
    queryFn: () => staffSlotsApi.getMySlots(),
  });

  // Create slot mutation
  const createMutation = useMutation({
    mutationFn: (payload: SlotCreatePayload) => staffSlotsApi.createSlot(payload),
    onSuccess: (newSlot) => {
      setFeedbackError(null);
      setFeedbackSuccess(`Appointment slot created successfully for ${new Date(newSlot.start_at).toLocaleString()}.`);
      setShowCreateForm(false);
      setStartAt('');
      setLocationOrLink('');
      setDurationMinutes(45);
      setMode('online');
      queryClient.invalidateQueries({ queryKey: ['staff-counselling-slots-mine'] });
      setTimeout(() => setFeedbackSuccess(null), 5000);
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to create appointment slot. Please verify the time is in the future.';
      setFeedbackError(detail);
    },
  });

  // Delete slot mutation (unbooked)
  const deleteMutation = useMutation({
    mutationFn: (id: string) => staffSlotsApi.deleteSlot(id),
    onSuccess: () => {
      setFeedbackError(null);
      setFeedbackSuccess('Slot deleted successfully.');
      queryClient.invalidateQueries({ queryKey: ['staff-counselling-slots-mine'] });
      setTimeout(() => setFeedbackSuccess(null), 4000);
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to delete slot. Booked slots cannot be deleted; cancel them instead.';
      setFeedbackError(detail);
    },
  });

  // Cancel slot mutation (booked)
  const cancelMutation = useMutation({
    mutationFn: (id: string) => staffSlotsApi.cancelSlot(id),
    onSuccess: () => {
      setFeedbackError(null);
      setFeedbackSuccess('Appointment cancelled. The student has been notified and the slot is released.');
      setSlotToCancel(null);
      queryClient.invalidateQueries({ queryKey: ['staff-counselling-slots-mine'] });
      setTimeout(() => setFeedbackSuccess(null), 5000);
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to cancel appointment.';
      setFeedbackError(detail);
    },
  });

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!startAt || !locationOrLink.trim()) {
      setFeedbackError('Please select a date/time and provide the meeting location or link.');
      return;
    }

    // Convert local datetime string to ISO UTC
    const dateObj = new Date(startAt);
    if (isNaN(dateObj.getTime())) {
      setFeedbackError('Invalid appointment start date/time.');
      return;
    }

    if (dateObj.getTime() <= Date.now()) {
      setFeedbackError('Appointment slot start time must be in the future.');
      return;
    }

    createMutation.mutate({
      start_at: dateObj.toISOString(),
      duration_minutes: Number(durationMinutes),
      mode,
      location_or_link: locationOrLink.trim(),
    });
  };

  const allSlots = slotsData?.items || [];

  const filteredSlots = allSlots.filter((slot) => {
    if (filterStatus === 'cancelled') return Boolean(slot.cancelled_at);
    if (filterStatus === 'booked') return slot.is_booked && !slot.cancelled_at;
    if (filterStatus === 'open') return !slot.is_booked && !slot.cancelled_at;
    return true;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Navigation Tabs */}
      <StaffTabs />

      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-600 mb-1">
            <Shield className="w-4 h-4" />
            <span>Component 4 · Sensitive Intervention Delivery</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">
            Counselling Appointment Slots
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Publish confidential consultation slots for students with accepted counselling interventions.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setShowCreateForm(!showCreateForm);
            setFeedbackError(null);
          }}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold shadow-sm transition self-start md:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>{showCreateForm ? 'Close Form' : 'Publish New Slot'}</span>
        </button>
      </div>

      {/* Notifications */}
      {feedbackSuccess && (
        <div className="mb-6 p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-800 flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          <span>{feedbackSuccess}</span>
        </div>
      )}

      {feedbackError && (
        <div className="mb-6 p-4 rounded-2xl bg-rose-50 border border-rose-200 text-sm text-rose-800 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
          <span>{feedbackError}</span>
        </div>
      )}

      {/* Create Slot Card */}
      {showCreateForm && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 mb-8 transition">
          <div className="flex items-center gap-3 mb-4 pb-4 border-b border-slate-100">
            <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-600">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Publish Confidential Counselling Slot
              </h2>
              <p className="text-xs text-slate-500">
                Students with accepted counselling interventions will be able to book this slot directly.
              </p>
            </div>
          </div>

          <form onSubmit={handleCreateSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Start Date & Time */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Start Date & Time (Local) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="datetime-local"
                  required
                  value={startAt}
                  onChange={(e) => setStartAt(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>

              {/* Duration */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Duration (Minutes) <span className="text-rose-500">*</span>
                </label>
                <select
                  value={durationMinutes}
                  onChange={(e) => setDurationMinutes(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white"
                >
                  <option value={15}>15 minutes</option>
                  <option value={30}>30 minutes</option>
                  <option value={45}>45 minutes (Standard)</option>
                  <option value={60}>60 minutes (1 hour)</option>
                  <option value={90}>90 minutes</option>
                  <option value={120}>120 minutes (2 hours)</option>
                </select>
              </div>

              {/* Mode */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Consultation Mode <span className="text-rose-500">*</span>
                </label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as SlotMode)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white"
                >
                  <option value="online">Online (Video Meeting Link)</option>
                  <option value="in_person">In-Person (Campus Office)</option>
                </select>
              </div>
            </div>

            {/* Location or Meeting Link */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                {mode === 'online' ? 'Secure Meeting Link' : 'Office Location / Room'}{' '}
                <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                maxLength={200}
                placeholder={
                  mode === 'online'
                    ? 'e.g. https://meet.google.com/abc-defg-hij'
                    : 'e.g. Student Wellbeing Center, Room 302, 3rd Floor'
                }
                value={locationOrLink}
                onChange={(e) => setLocationOrLink(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
              <div className="mt-1.5 flex items-center gap-1.5 text-xs text-slate-500">
                <Lock className="w-3.5 h-3.5 text-indigo-500 flex-shrink-0" />
                <span>
                  <strong>Confidentiality Protection:</strong> This details field is strictly hidden
                  from the public directory and is only visible to the specific student who confirms the booking.
                </span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="px-4 py-2 rounded-xl text-sm font-semibold text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="inline-flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold shadow-sm transition disabled:opacity-50"
              >
                {createMutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Publishing...</span>
                  </>
                ) : (
                  <span>Publish Slot</span>
                )}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center justify-between flex-wrap gap-3 mb-6">
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-100 border border-slate-200 text-xs font-semibold text-slate-600">
          <button
            type="button"
            onClick={() => setFilterStatus('all')}
            className={`px-3 py-1.5 rounded-lg transition ${filterStatus === 'all'
              ? 'bg-white text-indigo-600 shadow-sm'
              : 'hover:text-slate-900'
              }`}
          >
            All Slots ({allSlots.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterStatus('open')}
            className={`px-3 py-1.5 rounded-lg transition ${filterStatus === 'open'
              ? 'bg-white text-emerald-600 shadow-sm'
              : 'hover:text-slate-900'
              }`}
          >
            Open ({allSlots.filter((s) => !s.is_booked && !s.cancelled_at).length})
          </button>
          <button
            type="button"
            onClick={() => setFilterStatus('booked')}
            className={`px-3 py-1.5 rounded-lg transition ${filterStatus === 'booked'
              ? 'bg-white text-indigo-600 shadow-sm'
              : 'hover:text-slate-900'
              }`}
          >
            Booked ({allSlots.filter((s) => s.is_booked && !s.cancelled_at).length})
          </button>
          <button
            type="button"
            onClick={() => setFilterStatus('cancelled')}
            className={`px-3 py-1.5 rounded-lg transition ${filterStatus === 'cancelled'
              ? 'bg-white text-slate-700 shadow-sm'
              : 'hover:text-slate-900'
              }`}
          >
            Cancelled ({allSlots.filter((s) => Boolean(s.cancelled_at)).length})
          </button>
        </div>

        <button
          type="button"
          onClick={() => refetch()}
          className="text-xs font-semibold text-slate-500 hover:text-slate-800 transition"
        >
          Refresh Schedule
        </button>
      </div>

      {/* Slots List / Grid */}
      {isLoading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center">
          <Loader2 className="w-8 h-8 text-indigo-600 animate-spin mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-600">Loading appointment schedule...</p>
        </div>
      ) : isError ? (
        <div className="bg-white rounded-2xl border border-rose-200 p-8 text-center text-rose-700">
          <AlertCircle className="w-8 h-8 text-rose-500 mx-auto mb-2" />
          <p className="text-sm font-semibold">Failed to load counselling slots</p>
          <p className="text-xs text-rose-600 mt-1">
            {(error as any)?.response?.data?.detail || 'An unexpected error occurred.'}
          </p>
        </div>
      ) : filteredSlots.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center">
          <Calendar className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <h3 className="text-sm font-bold text-slate-800">No appointment slots found</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            {filterStatus === 'all'
              ? 'You have not published any counselling slots yet. Click "Publish New Slot" above to set your availability.'
              : `No slots found matching the "${filterStatus}" filter.`}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredSlots.map((slot) => {
            const startDate = new Date(slot.start_at);
            const isPast = startDate.getTime() < Date.now();
            const isCancelled = Boolean(slot.cancelled_at);
            const isBooked = slot.is_booked && !isCancelled;
            const isOpen = !slot.is_booked && !isCancelled;

            return (
              <div
                key={slot.id}
                className={`bg-white rounded-2xl border transition p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4 ${isCancelled
                  ? 'border-slate-200 opacity-60 bg-slate-50/50'
                  : isBooked
                    ? 'border-indigo-200 shadow-sm'
                    : 'border-slate-200 hover:border-slate-300'
                  }`}
              >
                <div className="flex items-start gap-4">
                  <div
                    className={`p-3 rounded-xl flex-shrink-0 ${isCancelled
                      ? 'bg-slate-100 text-slate-400'
                      : isBooked
                        ? 'bg-indigo-50 text-indigo-600'
                        : 'bg-emerald-50 text-emerald-600'
                      }`}
                  >
                    <Calendar className="w-5 h-5" />
                  </div>

                  <div>
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-sm font-bold text-slate-900">
                        {startDate.toLocaleDateString(undefined, {
                          weekday: 'short',
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                        })}
                      </span>
                      <span className="text-sm font-semibold text-indigo-600">
                        {startDate.toLocaleTimeString(undefined, {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>

                      {/* Status Badges */}
                      {isCancelled ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                          <XCircle className="w-3 h-3 text-slate-400" />
                          Cancelled
                        </span>
                      ) : isBooked ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                          <UserCheck className="w-3 h-3 text-indigo-600" />
                          Booked
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          Open
                        </span>
                      )}

                      {isPast && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                          Past
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-3 text-xs text-slate-500 flex-wrap">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        {slot.duration_minutes} minutes
                      </span>
                      <span className="inline-flex items-center gap-1">
                        {slot.mode === 'online' ? (
                          <>
                            <Video className="w-3.5 h-3.5 text-indigo-500" />
                            <span>Online Consultation</span>
                          </>
                        ) : (
                          <>
                            <MapPin className="w-3.5 h-3.5 text-amber-500" />
                            <span>In-Person Consultation</span>
                          </>
                        )}
                      </span>
                    </div>

                    {/* Booking Details or Location preview */}
                    <div className="mt-2 text-xs text-slate-600 flex items-center gap-2 flex-wrap">
                      {isBooked && (
                        <>
                          {slot.intervention_id && (
                            <Link
                              to={`/staff/interventions/${slot.intervention_id}`}
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold border border-indigo-200 transition"
                            >
                              <span>View Linked Intervention</span>
                              <ExternalLink className="w-3 h-3" />
                            </Link>
                          )}
                          {slot.booked_at && (
                            <span className="text-slate-400">
                              Booked on {new Date(slot.booked_at).toLocaleDateString()}
                            </span>
                          )}
                        </>
                      )}

                      {slot.location_or_link && (
                        <span className="inline-flex items-center gap-1 text-slate-500 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                          <Lock className="w-3 h-3 text-slate-400" />
                          <span className="truncate max-w-xs">{slot.location_or_link}</span>
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 self-end md:self-center flex-shrink-0">
                  {isOpen && !isPast && (
                    <button
                      type="button"
                      disabled={deleteMutation.isPending}
                      onClick={() => {
                        if (confirm('Are you sure you want to delete this open slot?')) {
                          deleteMutation.mutate(slot.id);
                        }
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-rose-200 text-rose-600 hover:bg-rose-50 text-xs font-semibold transition"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Delete</span>
                    </button>
                  )}

                  {isBooked && !isPast && (
                    <button
                      type="button"
                      onClick={() => setSlotToCancel(slot)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-amber-200 text-amber-700 bg-amber-50 hover:bg-amber-100 text-xs font-semibold transition"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Cancel Appointment</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Cancel Booking Confirmation Modal */}
      {slotToCancel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 rounded-xl bg-amber-50 text-amber-600">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-base font-bold text-slate-900">
                  Cancel Booked Appointment
                </h4>
                <p className="text-xs text-slate-500">
                  Scheduled for {new Date(slotToCancel.start_at).toLocaleString()}
                </p>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 space-y-2 mb-6">
              <p className="flex items-start gap-1.5">
                <Info className="w-4 h-4 text-indigo-500 flex-shrink-0 mt-0.5" />
                <span>
                  <strong>Automated Student Notification:</strong> The booked student will receive a supportive,
                  neutral notification that their appointment was cancelled so they can choose another slot.
                </span>
              </p>
              <p>
                The appointment slot will be cleared and the intervention record schedule will be reset.
              </p>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                disabled={cancelMutation.isPending}
                onClick={() => setSlotToCancel(null)}
                className="px-4 py-2 rounded-xl text-sm font-semibold text-slate-600 hover:bg-slate-100 transition"
              >
                Keep Appointment
              </button>
              <button
                type="button"
                disabled={cancelMutation.isPending}
                onClick={() => cancelMutation.mutate(slotToCancel.id)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-sm font-semibold shadow-sm transition disabled:opacity-50"
              >
                {cancelMutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Cancelling...</span>
                  </>
                ) : (
                  <span>Confirm Cancellation</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
