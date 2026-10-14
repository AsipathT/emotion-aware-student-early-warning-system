/**
 * src/api/notifications.ts
 *
 * API client and TypeScript interfaces for Feature 37:
 * Student Notifications (Component 4 Uptake Path).
 */

import { apiClient } from './client';

export interface NotificationItem {
  id: string;
  user_id: string;
  type: string;
  title: string;
  body: string;
  link?: string | null;
  related_id?: string | null;
  created_at: string;
  read_at?: string | null;
  is_read: boolean;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  total_count: number;
  unread_count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export interface MarkReadResponse {
  id: string;
  read_at: string;
}

export interface MarkAllReadResponse {
  marked_count: number;
}

export const notificationsApi = {
  getNotifications: async (params?: {
    unread_only?: boolean;
    page?: number;
    page_size?: number;
  }): Promise<NotificationListResponse> => {
    const response = await apiClient.get<NotificationListResponse>(
      '/notifications',
      { params }
    );
    return response.data;
  },

  getUnreadCount: async (): Promise<UnreadCountResponse> => {
    const response = await apiClient.get<UnreadCountResponse>(
      '/notifications/unread-count'
    );
    return response.data;
  },

  markAsRead: async (id: string): Promise<MarkReadResponse> => {
    const response = await apiClient.post<MarkReadResponse>(
      `/notifications/${encodeURIComponent(id)}/read`
    );
    return response.data;
  },

  markAllAsRead: async (): Promise<MarkAllReadResponse> => {
    const response = await apiClient.post<MarkAllReadResponse>(
      '/notifications/read-all'
    );
    return response.data;
  },
};
