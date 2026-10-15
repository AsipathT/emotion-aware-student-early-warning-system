import { apiClient } from './client';

export interface ModuleResponse {
  id: string;
  course_id: string;
  title: string;
  content_payload: any;
  sequence_order: number;
  created_at: string;
  updated_at: string;
}

export interface CourseResponse {
  id: string;
  title: string;
  description: string | null;
  lecturer_id: string;
  is_published: boolean;
  created_at: string;
  updated_at: string;
  modules: ModuleResponse[];
}

export interface CourseCreatePayload {
  title: string;
  description?: string | null;
  is_published?: boolean;
  lecturer_id?: string | null;
}

export interface ModuleCreatePayload {
  title: string;
  content_payload?: any;
  sequence_order?: number;
}

/**
 * Fetches all courses visible to the authenticated user.
 * (Admins see all; Lecturers see published + own drafts; Students see published)
 */
export const getCourses = async (): Promise<CourseResponse[]> => {
  const response = await apiClient.get<CourseResponse[]>('/courses');
  return response.data;
};

/**
 * Fetches a single course by UUID with its complete ordered curriculum modules.
 */
export const getCourseById = async (courseId: string): Promise<CourseResponse> => {
  const response = await apiClient.get<CourseResponse>(`/courses/${courseId}`);
  return response.data;
};

/**
 * Creates a new course. (Restricted to Lecturer or Admin)
 */
export const createCourse = async (
  payload: CourseCreatePayload
): Promise<CourseResponse> => {
  const response = await apiClient.post<CourseResponse>('/courses', payload);
  return response.data;
};

/**
 * Appends a module to an existing course. (Restricted to assigned Lecturer or Admin)
 */
export const addModule = async (
  courseId: string,
  payload: ModuleCreatePayload
): Promise<ModuleResponse> => {
  const response = await apiClient.post<ModuleResponse>(
    `/courses/${courseId}/modules`,
    payload
  );
  return response.data;
};

export const coursesApi = {
  getCourses,
  getCourseById,
  createCourse,
  addModule,
};
