import { apiClient } from './client';

export interface ModalityContributions {
  affective: number;
  behavioral: number;
  academic: number;
}

export interface StudentRiskRow {
  pid: string;
  student_id: string;
  name: string;
  email: string;
  risk_score: number;
  risk_tier: 'critical' | 'high' | 'medium' | 'low';
  trajectory_label: 'declining' | 'stable' | 'improving' | 'volatile';
  trajectory_confidence: number;
  modality_contributions: ModalityContributions;
  primary_driver_modality: 'Affective' | 'Behavioral' | 'Academic';
  top_drivers: string[];
  contributing_indicators: string[];
  week_index: number;
}

export interface CourseOption {
  id: string;
  title: string;
  course_code: string;
}

export interface CohortRiskSummary {
  total_students: number;
  avg_risk_score: number;
  high_risk_percentage: number;
  tier_distribution: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  trajectory_distribution: {
    declining: number;
    stable: number;
    improving: number;
    volatile: number;
  };
  avg_modality_contributions: ModalityContributions;
}

export interface CohortRiskResponse {
  course_id: string;
  course_title: string;
  available_courses: CourseOption[];
  current_week: number;
  available_weeks: number[];
  summary: CohortRiskSummary;
  students: StudentRiskRow[];
}

export interface LongitudinalPoint {
  week_index: number;
  week_label: string;
  risk_score: number;
  risk_tier: string;
  affective_pct: number;
  behavioral_pct: number;
  academic_pct: number;
  trajectory_label: string;
  trajectory_confidence: number;
  login_count: number;
  session_minutes: number;
  clicks: number;
  video_completion_pct: number;
  submissions_count: number;
  avg_submission_delay_hours: number;
  attendance_pct: number;
  ca_marks?: number | null;
  stress_label?: string | null;
  top_drivers: string[];
  contributing_indicators: string[];
}

export interface RecommendedIntervention {
  category: string;
  title: string;
  description: string;
  urgency: string;
  action_type: string;
}

export interface StudentRiskDetail {
  student: {
    pid: string;
    student_id: string;
    name: string;
    email: string;
    course_id: string;
    course_title: string;
  };
  latest_assessment: {
    week_index: number;
    risk_score: number;
    risk_tier: string;
    modality_contributions: ModalityContributions;
    top_drivers: string[];
    trajectory_label: string;
    trajectory_confidence: number;
    contributing_indicators: string[];
  };
  longitudinal_trends: LongitudinalPoint[];
  recommended_interventions: RecommendedIntervention[];
}

export interface SyntheticGenerateRequest {
  course_id: string;
  num_students: number;
  num_weeks: number;
  cohort_profile: 'balanced' | 'high_risk_heavy' | 'healthy_cohort' | 'volatile';
  clear_existing: boolean;
}

export interface SyntheticGenerateResponse {
  message: string;
  course_id: string;
  students_count: number;
  weeks_count: number;
  cohort_profile: string;
  records_generated: {
    risk_assessments: number;
    engagement_trajectories: number;
    behavior_weekly: number;
    affective_weekly: number;
    academic_records: number;
    messages: number;
  };
  sample_students: Array<{
    pid: string;
    name: string;
    student_id: string;
  }>;
}

export const analyticsApi = {
  getCohortRisk: async (params?: {
    course_id?: string;
    week_index?: number;
    risk_tier?: string;
    trajectory?: string;
    search?: string;
  }): Promise<CohortRiskResponse> => {
    const response = await apiClient.get<CohortRiskResponse>('/analytics/cohort-risk', {
      params,
    });
    return response.data;
  },

  getStudentRiskDetail: async (
    pid: string,
    course_id?: string
  ): Promise<StudentRiskDetail> => {
    const response = await apiClient.get<StudentRiskDetail>(
      `/analytics/students/${encodeURIComponent(pid)}/detail`,
      {
        params: course_id ? { course_id } : undefined,
      }
    );
    return response.data;
  },

  generateSyntheticCohort: async (
    payload: SyntheticGenerateRequest
  ): Promise<SyntheticGenerateResponse> => {
    const response = await apiClient.post<SyntheticGenerateResponse>(
      '/analytics/synthetic/generate',
      payload
    );
    return response.data;
  },

  clearSyntheticData: async (course_id: string): Promise<{ message: string; deleted_counts: Record<string, number> }> => {
    const response = await apiClient.delete('/analytics/synthetic/clear', {
      params: { course_id },
    });
    return response.data;
  },
};
