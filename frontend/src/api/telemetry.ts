import { apiClient } from './client';

export interface TelemetryPayload {
  course_id?: string;
  week_index?: number;
  event_type: string;
  event_payload?: Record<string, any>;
  clicks?: number;
}

export interface ActivityEventResponse {
  id: string;
  schema_version: number;
  pid: string;
  course_id: string;
  week_index: number;
  event_type: string;
  event_payload?: Record<string, any>;
  clicks: number;
  timestamp: string;
  ingested_at: string;
  source_version: string;
}

export const telemetryApi = {
  logEvent: async (payload: TelemetryPayload) => {
    const response = await apiClient.post<{
      event_id: string;
      status: string;
      timestamp: string;
    }>('/telemetry/events', payload);
    return response.data;
  },

  getMySessions: async (): Promise<ActivityEventResponse[]> => {
    const response = await apiClient.get<ActivityEventResponse[]>('/telemetry/sessions');
    return response.data;
  },

  getMyActivity: async (): Promise<ActivityEventResponse[]> => {
    const response = await apiClient.get<ActivityEventResponse[]>('/telemetry/my-activity');
    return response.data;
  },

  getRecentCourseEvents: async (courseId: string): Promise<ActivityEventResponse[]> => {
    const response = await apiClient.get<ActivityEventResponse[]>(
      `/telemetry/course/${courseId}/recent`
    );
    return response.data;
  },
};
