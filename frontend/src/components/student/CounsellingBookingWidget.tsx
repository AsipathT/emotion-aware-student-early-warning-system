/**
 * src/components/student/CounsellingBookingWidget.tsx
 *
 * Feature 38-B: Student Counselling Appointment Booking & Schedule Widget.
 * Embedded in SupportPage for sensitive counselling interventions:
 *   1. Displays open appointment slots published by academic counsellors.
 *   2. Allows student to atomically book an appointment (sets scheduled_for, transitions to in_progress).
 *   3. Displays confirmed booking details (mode, date/time, confidential link/location).
 *   4. Allows self-service cancellation with 2-hour advance lead time enforcement.
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Calendar,
  Clock,
  Video,
  MapPin,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Loader2,
  Lock,
  ExternalLink,
  Info,
  XCircle,
  Shield,
} from 'lucide-react';
import {
  supportApi,
  StudentSupportInterventionItem,
  AvailableSlotItem,
} from '../../api/support';

interface CounsellingBookingWidgetProps {
  intervention: StudentSupportInterventionItem;
  onBookingChanged?: () => void;
}

export const CounsellingBookingWidget: React.FC<CounsellingBookingWidgetProps> = ({
  intervention,
  onBookingChanged,
}) => {
  const queryClient = useQueryClient();

  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null);
  const [showCancelModal, setShowCancelModal] = useState<boolean>(false);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [bookingSuccess, setBookingSuccess] = useState<string | null>(null);

  const isCounselling = intervention.delivery_module === 'counselling_booking';
  const hasBookedSlot = Boolean(intervention.slot);
  const isAcceptedOrInProgress =
    intervention.status === 'accepted' || intervention.status === 'in_progress';

  // Query open available slots if intervention is accepted/in_progress and not yet booked
  const {
    data: availableData,
    isLoading: isLoadingSlots,
    isError: isSlotsError,
    error: slotsError,
    refetch: refetchSlots,
  } = useQuery({
    queryKey: ['available-counselling-slots', intervention.id],
    queryFn: () => supportApi.getAvailableSlots(intervention.id),
    enabled: isCounselling && !hasBookedSlot && isAcceptedOrInProgress,
  });

  // Book slot mutation
  const bookMutation = useMutation({
    mutationFn: (slotId: string) => supportApi.bookSlot(intervention.id, slotId),
    onSuccess: (res) => {
      setBookingError(null);
      setBookingSuccess(res.message);
      setSelectedSlotId(null);
      queryClient.invalidateQueries({ queryKey: ['my-support-interventions'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      if (onBookingChanged) onBookingChanged();
      setTimeout(() => setBookingSuccess(null), 6000);
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to book appointment. This slot may have just been claimed or starts within 2 hours.';
      setBookingError(detail);
      refetchSlots();
    },
  });

  // Cancel booking mutation
  const cancelMutation = useMutation({
    mutationFn: () => supportApi.cancelBooking(intervention.id),
    onSuccess: (res) => {
      setBookingError(null);
      setBookingSuccess(res.message);
      setShowCancelModal(false);
      queryClient.invalidateQueries({ queryKey: ['my-support-interventions'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      if (onBookingChanged) onBookingChanged();
      setTimeout(() => setBookingSuccess(null), 6000);
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to cancel booking. Cancellations require at least 2 hours advance notice.';
      setBookingError(detail);
    },
  });

  if (!isCounselling) {
    return null;
  }

  // --- STATE 1: Already Booked Appointment ---
  if (hasBookedSlot && intervention.slot) {
    const slot = intervention.slot;
    const startUtc = new Date(slot.start_at).getTime();
    const twoHoursFromNow = Date.now() + 2 * 60 * 60 * 1000;
    const canCancel = startUtc > twoHoursFromNow;
    const formattedDate = new Date(slot.start_at).toLocaleDateString(undefined, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
    const formattedTime = new Date(slot.start_at).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    });

    const isUrl =
      slot.location_or_link &&
      (slot.location_or_link.startsWith('http://') ||
        slot.location_or_link.startsWith('https://'));

    return (
      <div className="pt-3 border-t border-slate-100">
        {/* Feedback Banners */}
        {bookingSuccess && (
          <div className="mb-3 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>{bookingSuccess}</span>
          </div>
        )}
        {bookingError && (
          <div className="mb-3 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            <span>{bookingError}</span>
          </div>
        )}

        <div className="bg-indigo-50/50 rounded-2xl border border-indigo-100 p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-indigo-600 text-white shadow-sm">
                <Calendar className="w-5 h-5" />
              </div>
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-700 block">
                  Confirmed Counselling Appointment
                </span>
                <h4 className="text-sm font-bold text-slate-900">
                  {formattedDate} at {formattedTime}
                </h4>
              </div>
            </div>

            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 self-start sm:self-auto">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              Appointment Confirmed
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            {/* Counsellor & Duration */}
            <div className="bg-white rounded-xl p-3 border border-slate-200 space-y-1.5">
              <div className="flex items-center gap-1.5 text-slate-800 font-semibold">
                <span>Counsellor:</span>
                <span className="text-indigo-600">
                  {slot.counsellor_name || 'Academic Counsellor'}
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-slate-500">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                <span>Duration: {slot.duration_minutes} minutes</span>
              </div>
              <div className="flex items-center gap-1.5 text-slate-500">
                {slot.mode === 'online' ? (
                  <>
                    <Video className="w-3.5 h-3.5 text-indigo-500" />
                    <span>Online Video Session</span>
                  </>
                ) : (
                  <>
                    <MapPin className="w-3.5 h-3.5 text-amber-500" />
                    <span>In-Person Campus Session</span>
                  </>
                )}
              </div>
            </div>

            {/* Location / Meeting Link (Confidential) */}
            <div className="bg-white rounded-xl p-3 border border-slate-200 space-y-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-1 text-[11px] font-bold text-slate-700 mb-1">
                  <Lock className="w-3 h-3 text-indigo-500" />
                  <span>Confidential Meeting Coordinates:</span>
                </div>
                {slot.location_or_link ? (
                  isUrl ? (
                    <a
                      href={slot.location_or_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-indigo-600 hover:text-indigo-800 font-semibold text-xs break-all"
                    >
                      <ExternalLink className="w-3.5 h-3.5 flex-shrink-0" />
                      <span>{slot.location_or_link}</span>
                    </a>
                  ) : (
                    <p className="text-slate-800 font-medium break-words">
                      {slot.location_or_link}
                    </p>
                  )
                ) : (
                  <p className="text-slate-400 italic">
                    Coordinates will be emailed prior to the session.
                  </p>
                )}
              </div>

              {isUrl && (
                <a
                  href={slot.location_or_link!}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-2 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs transition"
                >
                  <Video className="w-3.5 h-3.5" />
                  <span>Join Video Consultation</span>
                </a>
              )}
            </div>
          </div>

          {/* Cancellation Notice and Button */}
          <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-t border-indigo-100 text-xs">
            <p className="text-slate-500 flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
              <span>
                Cancellations must be made at least 2 hours before the appointment.
              </span>
            </p>

            {canCancel ? (
              <button
                type="button"
                onClick={() => {
                  setBookingError(null);
                  setShowCancelModal(true);
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-rose-200 text-rose-600 bg-white hover:bg-rose-50 font-semibold transition self-start sm:self-auto"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Cancel Appointment</span>
              </button>
            ) : (
              <span className="text-[11px] text-amber-700 bg-amber-50 px-2.5 py-1 rounded-lg border border-amber-200">
                Starts in &lt; 2 hours (Online cancel disabled)
              </span>
            )}
          </div>
        </div>

        {/* Cancel Confirmation Modal */}
        {showCancelModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2.5 rounded-xl bg-amber-50 text-amber-600">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-base font-bold text-slate-900">
                    Cancel Counselling Appointment?
                  </h4>
                  <p className="text-xs text-slate-500">
                    {formattedDate} at {formattedTime}
                  </p>
                </div>
              </div>

              <p className="text-xs text-slate-600 mb-6 leading-relaxed">
                Cancelling will release this slot so other students can book it. Your advisor
                will be notified with a neutral update, and you can book a new time whenever convenient.
              </p>

              <div className="flex items-center justify-end gap-3">
                <button
                  type="button"
                  disabled={cancelMutation.isPending}
                  onClick={() => setShowCancelModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
                >
                  Keep Appointment
                </button>
                <button
                  type="button"
                  disabled={cancelMutation.isPending}
                  onClick={() => cancelMutation.mutate()}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-sm transition disabled:opacity-50"
                >
                  {cancelMutation.isPending ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
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
  }

  // --- STATE 2: Offered Status (Not yet accepted) ---
  if (intervention.status === 'offered') {
    return (
      <div className="pt-3 border-t border-slate-100">
        <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 flex items-center gap-2.5">
          <Info className="w-4 h-4 text-indigo-500 flex-shrink-0" />
          <span>
            Appointment booking will become available once you voluntary accept this support initiative above.
          </span>
        </div>
      </div>
    );
  }

  // --- STATE 3: Accepted or In-Progress without a booked slot ---
  if (!isAcceptedOrInProgress) {
    return null;
  }

  const openSlots: AvailableSlotItem[] = availableData?.items || [];

  return (
    <div className="pt-3 border-t border-slate-100 space-y-3">
      {/* Feedback Banners */}
      {bookingSuccess && (
        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{bookingSuccess}</span>
        </div>
      )}
      {bookingError && (
        <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{bookingError}</span>
        </div>
      )}

      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-indigo-600" />
          <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Book an Appointment
          </h4>
        </div>
        <button
          type="button"
          onClick={() => refetchSlots()}
          className="text-[11px] font-semibold text-slate-500 hover:text-indigo-600 transition"
        >
          Refresh Times
        </button>
      </div>

      <p className="text-xs text-slate-500">
        Select a consultation time below. Slots start at least 2 hours in advance to guarantee advisor availability.
      </p>

      {/* Slots Loading / Empty / Available */}
      {isLoadingSlots ? (
        <div className="p-6 rounded-xl border border-slate-200 bg-slate-50 text-center">
          <Loader2 className="w-5 h-5 text-indigo-600 animate-spin mx-auto mb-2" />
          <p className="text-xs text-slate-500">Loading open appointment slots...</p>
        </div>
      ) : isSlotsError ? (
        <div className="p-4 rounded-xl border border-rose-200 bg-rose-50 text-xs text-rose-700">
          <p className="font-semibold">Unable to load appointment slots</p>
          <p className="mt-0.5">
            {(slotsError as any)?.response?.data?.detail || 'Please try again in a few moments.'}
          </p>
        </div>
      ) : openSlots.length === 0 ? (
        <div className="p-5 rounded-xl border border-slate-200 bg-slate-50/70 text-center text-xs text-slate-600 space-y-1">
          <Calendar className="w-6 h-6 text-slate-300 mx-auto mb-1" />
          <p className="font-semibold text-slate-700">No open appointment slots right now</p>
          <p className="text-slate-500 max-w-md mx-auto text-[11px]">
            Your advisor has been notified that you accepted this support. They will publish new availability soon or contact you directly.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
            {openSlots.map((slot) => {
              const startDate = new Date(slot.start_at);
              const isSelected = selectedSlotId === slot.id;

              return (
                <button
                  key={slot.id}
                  type="button"
                  onClick={() => setSelectedSlotId(slot.id)}
                  className={`text-left p-3 rounded-xl border transition flex flex-col justify-between ${
                    isSelected
                      ? 'border-indigo-600 bg-indigo-50/60 ring-2 ring-indigo-500/20 shadow-sm'
                      : 'border-slate-200 bg-white hover:border-indigo-300 hover:bg-slate-50/50'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between gap-1 mb-1">
                      <span className="text-xs font-bold text-slate-900">
                        {startDate.toLocaleDateString(undefined, {
                          weekday: 'short',
                          month: 'short',
                          day: 'numeric',
                        })}
                      </span>
                      <span className="text-xs font-semibold text-indigo-600">
                        {startDate.toLocaleTimeString(undefined, {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>

                    <p className="text-[11px] text-slate-500 line-clamp-1 mb-2">
                      {slot.counsellor_name || 'Academic Counsellor'}
                    </p>
                  </div>

                  <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-100">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="w-3 h-3 text-slate-400" />
                      {slot.duration_minutes}m
                    </span>
                    <span className="inline-flex items-center gap-1">
                      {slot.mode === 'online' ? (
                        <>
                          <Video className="w-3 h-3 text-indigo-500" />
                          <span>Online</span>
                        </>
                      ) : (
                        <>
                          <MapPin className="w-3 h-3 text-amber-500" />
                          <span>In-Person</span>
                        </>
                      )}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Confirm Booking Bar */}
          {selectedSlotId && (
            <div className="p-3.5 rounded-xl bg-indigo-50 border border-indigo-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition">
              <div className="flex items-center gap-2 text-xs text-indigo-900">
                <Shield className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                <span>
                  <strong>Selected:</strong> Ready to confirm your confidential appointment session.
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedSlotId(null)}
                  className="px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
                >
                  Clear
                </button>
                <button
                  type="button"
                  disabled={bookMutation.isPending}
                  onClick={() => bookMutation.mutate(selectedSlotId)}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-sm transition disabled:opacity-50"
                >
                  {bookMutation.isPending ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Confirming...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Confirm Appointment</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
