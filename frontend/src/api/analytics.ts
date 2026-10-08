import { apiClient } from './client';

export interface DashboardSummary {
  active_alerts: number;
  recent_risk_scores: Array<{
    student_id: string;
    score: number;
    tier: string;
  }>;
}

export interface RiskScore {
  id: string;
  student_id: string;
  course_id: string;
  week_index: number;
  risk_score: number;
  risk_tier: string;
  calibrated: boolean;
  modality_weights: any;
  top_features: any;
  schema_version: string;
  created_at: string;
}

export interface TrajectoryLabel {
  id: string;
  student_id: string;
  course_id: string;
  week_index: number;
  label: string;
  p_stable: number | null;
  p_improving: number | null;
  p_declining: number | null;
  p_volatile: number | null;
  confidence: number | null;
  created_at: string;
}

export const analyticsApi = {
  getDashboardSummary: async (): Promise<DashboardSummary> => {
    const res = await apiClient.get('/analytics/dashboard');
    return res.data;
  },
  getCourseRisk: async (courseId: string): Promise<RiskScore[]> => {
    const res = await apiClient.get(`/analytics/courses/${courseId}/risk`);
    return res.data;
  },
  getStudentTrajectory: async (courseId: string, studentId: string): Promise<TrajectoryLabel[]> => {
    const res = await apiClient.get(`/analytics/students/${studentId}/trajectory?course_id=${courseId}`);
    return res.data;
  },
  triggerSyntheticData: async (courseId: string): Promise<void> => {
    await apiClient.post(`/analytics/courses/${courseId}/synthetic`);
  },
};
