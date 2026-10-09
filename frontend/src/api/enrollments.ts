import { apiClient } from './client';
import { UserRole } from './auth';
import { ProfileResponse } from './users';

export interface EnrollmentCourseSummary {
  id: string;
  title: string;
  description: string | null;
  lecturer_id: string;
  is_published: boolean;
  created_at: string;
}

export interface EnrollmentStudentSummary {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  profile?: ProfileResponse | null;
}

export interface EnrollmentResponse {
  id: string;
  student_id: string;
  course_id: string;
  status: string;
  enrolled_at: string;
  updated_at: string;
  course?: EnrollmentCourseSummary | null;
  student?: EnrollmentStudentSummary | null;
}

export interface EnrollmentCreatePayload {
  status?: string;
}

export interface EnrollmentUpdatePayload {
  status: string;
}

/**
 * Enrolls the currently authenticated student in the specified published course.
 */
export const enrollInCourse = async (
  courseId: string
): Promise<EnrollmentResponse> => {
  const response = await apiClient.post<EnrollmentResponse>(
    `/enrollments/${courseId}`
  );
  return response.data;
};

/**
 * Retrieves all active course enrollments for the calling student.
 */
export const getMyEnrollments = async (): Promise<EnrollmentResponse[]> => {
  const response = await apiClient.get<EnrollmentResponse[]>('/enrollments/me');
  return response.data;
};

/**
 * Retrieves the enrolled students roster for a course (Instructors/Admins only).
 */
export const getCourseRoster = async (
  courseId: string
): Promise<EnrollmentResponse[]> => {
  const response = await apiClient.get<EnrollmentResponse[]>(
    `/courses/${courseId}/enrollments`
  );
  return response.data;
};

export const enrollmentsApi = {
  enrollInCourse,
  getMyEnrollments,
  getCourseRoster,
};
