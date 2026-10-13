/**
 * src/pages/NotificationsPage.tsx
 *
 * Feature 37: Student & User Notifications Feed (Component 4 Uptake Path).
 * Displays full notification history with filtering (all vs unread), read/unread management,
 * and supportive action redirects.
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  CheckCheck,
  CheckCircle2,
  ExternalLink,
  Filter,
  Loader2,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  Clock,
} from 'lucide-react';
import {
  notificationsApi,
  NotificationItem,
} from '../api/notifications';

export const NotificationsPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [unreadOnly, setUnreadOnly] = useState<boolean>(false);
  const [page, setPage] = useState<number>(1);
  const pageSize = 15;

  // Query notifications list
  const {
    data: listData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['notifications-list', unreadOnly, page],
    queryFn: () =>
      notificationsApi.getNotifications({
        unread_only: unreadOnly,
        page,
        page_size: pageSize,
      }),
  });

  // Mark single as read mutation
  const markReadMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.markAsRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-latest'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-list'] });
    },
  });

  // Mark all as read mutation
  const markAllMutation = useMutation({
    mutationFn: () => notificationsApi.markAllAsRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-latest'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-list'] });
    },
  });

  const handleAction = (item: NotificationItem) => {
    if (!item.is_read) {
      markReadMutation.mutate(item.id);
    }
    if (item.link) {
      navigate(item.link);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 rounded-2xl bg-indigo-50 text-indigo-600">
              <Bell className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                My Notifications
              </h1>
              <p className="text-sm text-slate-500">
                Course support updates, advisory sessions, and academic guidance notices.
              </p>
            </div>
          </div>
        </div>

        {/* Mark All as Read Button */}
        {listData && listData.unread_count > 0 && (
          <button
            onClick={() => markAllMutation.mutate()}
            disabled={markAllMutation.isPending}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 hover:text-indigo-600 shadow-sm transition disabled:opacity-50"
          >
            <CheckCheck className="w-4 h-4 text-indigo-600" />
            <span>Mark all as read</span>
          </button>
        )}
      </div>

      {/* Filter Chips Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm mb-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-indigo-600" />
          <span className="text-xs font-bold text-slate-700">Filter:</span>
          <div className="flex gap-2 ml-1">
            <button
              onClick={() => {
                setUnreadOnly(false);
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition ${
                !unreadOnly
                  ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
            >
              All Notifications
            </button>
            <button
              onClick={() => {
                setUnreadOnly(true);
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition ${
                unreadOnly
                  ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
            >
              Unread Only {listData && listData.unread_count > 0 && `(${listData.unread_count})`}
            </button>
          </div>
        </div>

        {listData && (
          <div className="text-xs text-slate-500 font-medium">
            Total: {listData.total_count}
          </div>
        )}
      </div>

      {/* Main List / State View */}
      {isLoading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-sm">
          <Loader2 className="w-8 h-8 text-indigo-600 animate-spin mx-auto mb-3" />
          <p className="text-xs font-medium text-slate-500">Loading notifications...</p>
        </div>
      ) : isError ? (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center text-xs text-rose-800">
          <p className="font-semibold">Unable to load notifications.</p>
          <p className="mt-1 text-slate-600">
            {(error as any)?.response?.data?.detail || 'An unexpected error occurred.'}
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
          <Sparkles className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <h3 className="text-sm font-bold text-slate-800">No Notifications</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            {unreadOnly
              ? 'You have caught up with all your notifications!'
              : 'You do not have any notification records right now.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {listData.items.map((item: NotificationItem) => (
            <div
              key={item.id}
              className={`bg-white rounded-2xl border p-5 shadow-sm transition flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
                !item.is_read
                  ? 'border-indigo-200 bg-indigo-50/20 ring-1 ring-indigo-50'
                  : 'border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="flex items-start gap-3.5 flex-1 min-w-0">
                {/* Status Dot */}
                <div className="mt-1 flex-shrink-0">
                  <span
                    className={`inline-block w-2.5 h-2.5 rounded-full ${
                      !item.is_read
                        ? 'bg-indigo-600 ring-4 ring-indigo-100'
                        : 'bg-slate-300'
                    }`}
                  />
                </div>

                <div className="space-y-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-bold text-slate-900">
                      {item.title}
                    </h3>
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-slate-100 text-slate-600 capitalize">
                      {item.type.replace(/_/g, ' ')}
                    </span>
                  </div>

                  <p className="text-xs text-slate-600 leading-relaxed">
                    {item.body}
                  </p>

                  <div className="flex items-center gap-1.5 text-[11px] text-slate-400 pt-1">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{new Date(item.created_at).toLocaleString()}</span>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 flex-shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100">
                {item.link && (
                  <button
                    onClick={() => handleAction(item)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition"
                  >
                    <span>View Support</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </button>
                )}

                {!item.is_read && (
                  <button
                    onClick={() => markReadMutation.mutate(item.id)}
                    disabled={markReadMutation.isPending}
                    title="Mark as read"
                    className="inline-flex items-center gap-1 px-3 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:text-indigo-600 hover:bg-slate-100 transition"
                  >
                    <CheckCircle2 className="w-4 h-4 text-slate-400 hover:text-indigo-600" />
                    <span>Mark read</span>
                  </button>
                )}
              </div>
            </div>
          ))}

          {/* Pagination Controls */}
          {listData.total_pages > 1 && (
            <div className="bg-white rounded-2xl border border-slate-200 px-5 py-3.5 shadow-sm flex items-center justify-between text-xs text-slate-600 mt-6">
              <div>
                Showing <span className="font-semibold">{(page - 1) * pageSize + 1}</span> to{' '}
                <span className="font-semibold">
                  {Math.min(page * pageSize, listData.total_count)}
                </span>{' '}
                of <span className="font-semibold">{listData.total_count}</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                  className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40 transition"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="font-medium">
                  Page {page} of {listData.total_pages}
                </span>
                <button
                  disabled={page >= listData.total_pages}
                  onClick={() => setPage((prev) => Math.min(prev + 1, listData.total_pages))}
                  className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40 transition"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
