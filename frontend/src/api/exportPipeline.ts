import { apiClient } from './client';

export interface Envelope<T> {
  schema_version: string;
  generated_at: string;
  source: string;
  request_id: string;
  data: T;
  page?: number;
  page_size?: number;
  total?: number;
}

export interface TextMessageRecord {
  message_id: string;
  pid: string;
  course_id: string;
  week_index: number;
  source_type: string;
  clean_text: string;
  timestamp: string;
  response_latency_seconds?: number | null;
  message_length_chars: number;
  message_length_words: number;
  reply_to_id?: string | null;
}

export interface BehaviorWeeklyRecord {
  pid: string;
  course_id: string;
  week_index: number;
  login_count: number;
  session_minutes: number;
  clicks: number;
  video_play_count: number;
  video_pause_count: number;
  video_rewind_count: number;
  video_skip_count: number;
  video_completion_pct: number;
  submissions_count: number;
  avg_submission_delay_hours: number;
}

export interface AcademicRecord {
  pid: string;
  course_id: string;
  week_index: number;
  attendance_rate?: number | null;
  formative_score_avg?: number | null;
  quiz_score_avg?: number | null;
  midterm_score?: number | null;
  assignments_submitted_count: number;
  avg_submission_delay_days: number;
}

export interface PipelineStatusResponse {
  scheduler: {
    running: boolean;
    job_count?: number;
    jobs?: Array<{ id: string; name: string; next_run_time: string | null }>;
  };
  latest_execution: {
    run_id?: string;
    component?: string;
    started_at?: string;
    completed_at?: string | null;
    status?: string;
    records_processed?: number;
    behavior_records_created?: number;
  } | null;
  server_time: string;
}

export interface TriggerPipelineParams {
  course_id?: string;
  week_index?: number;
}

export interface ExportFilterParams {
  course_id?: string;
  week_from?: number;
  week_to?: number;
  pid?: string;
  page?: number;
  page_size?: number;
}

export const exportPipelineApi = {
  // Feature 42: Export Datasets
  getMessages: async (params: ExportFilterParams): Promise<Envelope<TextMessageRecord[]>> => {
    const res = await apiClient.get<Envelope<TextMessageRecord[]>>('/export/messages', { params });
    return res.data;
  },

  getBehavior: async (params: ExportFilterParams): Promise<Envelope<BehaviorWeeklyRecord[]>> => {
    const res = await apiClient.get<Envelope<BehaviorWeeklyRecord[]>>('/export/behavior', { params });
    return res.data;
  },

  getAcademic: async (params: ExportFilterParams): Promise<Envelope<AcademicRecord[]>> => {
    const res = await apiClient.get<Envelope<AcademicRecord[]>>('/export/academic', { params });
    return res.data;
  },

  // Feature 20: Weekly Pipeline Management
  getPipelineStatus: async (): Promise<PipelineStatusResponse> => {
    const res = await apiClient.get<PipelineStatusResponse>('/pipeline/status');
    return res.data;
  },

  triggerWeeklyPipeline: async (params: TriggerPipelineParams): Promise<any> => {
    const res = await apiClient.post('/pipeline/trigger-weekly', null, { params });
    return res.data;
  },
};
