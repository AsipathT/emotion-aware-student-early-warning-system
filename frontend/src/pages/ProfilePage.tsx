import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { usersApi, UserMeResponse, ProfileUpdatePayload } from '../api/users';
import {
  Mail,
  Building,
  FileText,
  IdCard,
  Image as ImageIcon,
  CheckCircle2,
  AlertCircle,
  Save,
  Shield,
  Calendar,
  Sparkles,
} from 'lucide-react';
import { PrivacySettings } from '../components/profile/PrivacySettings';


export const ProfilePage: React.FC = () => {
  const queryClient = useQueryClient();

  // Form state
  const [department, setDepartment] = useState('');
  const [bio, setBio] = useState('');
  const [studentId, setStudentId] = useState('');
  const [avatarUrl, setAvatarUrl] = useState('');
  const [notification, setNotification] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);

  // Fetch user and profile data
  const {
    data: userData,
    isLoading,
    isError,
    error,
  } = useQuery<UserMeResponse>({
    queryKey: ['userProfile'],
    queryFn: usersApi.getCurrentUser,
  });

  // Populate form fields once profile data loads or changes
  useEffect(() => {
    if (userData?.profile) {
      setDepartment(userData.profile.department || '');
      setBio(userData.profile.bio || '');
      setStudentId(userData.profile.student_id || '');
      setAvatarUrl(userData.profile.avatar_url || '');
    }
  }, [userData]);

  // Update profile mutation
  const updateMutation = useMutation({
    mutationFn: (payload: ProfileUpdatePayload) => usersApi.updateUserProfile(payload),
    onSuccess: () => {
      // Refresh profile and global current user caches
      queryClient.invalidateQueries({ queryKey: ['userProfile'] });
      queryClient.invalidateQueries({ queryKey: ['currentUser'] });
      setNotification({
        type: 'success',
        message: 'Your profile information has been successfully updated.',
      });
      // Auto-hide success notification after 5 seconds
      setTimeout(() => {
        setNotification((prev) => (prev?.type === 'success' ? null : prev));
      }, 5000);
    },
    onError: (err: any) => {
      const detail =
        err.response?.data?.detail ||
        'Failed to save changes. Please review your input and try again.';
      setNotification({
        type: 'error',
        message: detail,
      });
    },
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotification(null);

    const payload: ProfileUpdatePayload = {
      department: department.trim() || null,
      bio: bio.trim() || null,
      student_id: studentId.trim() || null,
      avatar_url: avatarUrl.trim() || null,
    };

    updateMutation.mutate(payload);
  };

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-16 flex flex-col items-center justify-center space-y-4">
        <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        <p className="text-sm font-medium text-slate-500">Loading your profile details...</p>
      </div>
    );
  }

  if (isError || !userData) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12">
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl flex items-start space-x-3 text-rose-800">
          <AlertCircle className="w-6 h-6 text-rose-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-bold text-base">Unable to load profile</h3>
            <p className="text-sm mt-1 text-rose-700">
              {(error as any)?.response?.data?.detail ||
                'An error occurred while communicating with the LMS backend service.'}
            </p>
          </div>
        </div>
      </div>
    );
  }

  const roleColors: Record<string, { bg: string; text: string; border: string }> = {
    admin: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
    lecturer: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
    counsellor: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
    student: { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200' },
  };

  const currentRoleStyle =
    roleColors[userData.role] || roleColors.student;

  const initials = userData.full_name
    .split(' ')
    .map((n) => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header Banner */}
      <div className="relative bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-50/50 rounded-full blur-3xl -z-0 pointer-events-none" />

        <div className="relative z-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <div className="flex items-center space-x-5">
            {/* Avatar or Initials */}
            {userData.profile?.avatar_url ? (
              <img
                src={userData.profile.avatar_url}
                alt={userData.full_name}
                className="w-20 h-20 rounded-2xl object-cover border-2 border-indigo-100 shadow-sm"
              />
            ) : (
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-500 to-indigo-700 text-white flex items-center justify-center text-2xl font-black shadow-md shadow-indigo-100">
                {initials}
              </div>
            )}

            <div>
              <div className="flex items-center space-x-3">
                <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                  {userData.full_name}
                </h1>
                <span
                  className={`px-3 py-1 text-xs font-bold uppercase tracking-wider rounded-full border ${currentRoleStyle.bg} ${currentRoleStyle.text} ${currentRoleStyle.border}`}
                >
                  {userData.role}
                </span>
              </div>

              <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                <span className="flex items-center">
                  <Mail className="w-3.5 h-3.5 mr-1 text-slate-400" />
                  {userData.email}
                </span>
                <span className="flex items-center">
                  <Calendar className="w-3.5 h-3.5 mr-1 text-slate-400" />
                  Joined {new Date(userData.created_at).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  })}
                </span>
                <span className="flex items-center text-emerald-600 font-medium">
                  <Shield className="w-3.5 h-3.5 mr-1" />
                  {userData.is_active ? 'Active Account' : 'Inactive'}
                </span>
              </div>
            </div>
          </div>

          <div className="flex sm:flex-col items-end gap-2 text-right">
            <div className="inline-flex items-center px-3 py-1.5 bg-slate-50 border border-slate-200/80 rounded-xl text-xs text-slate-600">
              <Sparkles className="w-3.5 h-3.5 mr-1.5 text-indigo-500" />
              <span>Platform Foundation: Member 1</span>
            </div>
          </div>
        </div>
      </div>

      {/* Toast / Banner Notification */}
      {notification && (
        <div
          className={`p-4 rounded-xl border flex items-start space-x-3 transition duration-150 ${
            notification.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}
        >
          {notification.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
          ) : (
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          )}
          <div className="flex-1 text-sm font-medium leading-relaxed">
            {notification.message}
          </div>
          <button
            type="button"
            onClick={() => setNotification(null)}
            className="text-xs font-bold text-slate-400 hover:text-slate-600 ml-2"
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Profile Edit Form (2 cols) */}
        <div className="lg:col-span-2 bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-sm space-y-6">
          <div className="border-b border-slate-100 pb-4">
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Edit Profile Details
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Update institutional department affiliation, bio description, and avatar.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Department Input */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Department / Faculty
              </label>
              <div className="relative rounded-xl shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Building className="h-5 w-5" />
                </div>
                <input
                  type="text"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  placeholder="e.g. Faculty of Computing & Informatics"
                  maxLength={255}
                  className="block w-full pl-11 pr-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                />
              </div>
            </div>

            {/* Student ID / Matriculation ID */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Student / Institutional ID
              </label>
              <div className="relative rounded-xl shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <IdCard className="h-5 w-5" />
                </div>
                <input
                  type="text"
                  value={studentId}
                  onChange={(e) => setStudentId(e.target.value)}
                  placeholder="e.g. STU-2024-0042 (optional for staff)"
                  maxLength={100}
                  className="block w-full pl-11 pr-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition font-mono"
                />
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Used by the pseudonymisation engine (Feature 5) for privacy-preserving analytics.
              </p>
            </div>

            {/* Avatar URL */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Avatar Image URL
              </label>
              <div className="relative rounded-xl shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <ImageIcon className="h-5 w-5" />
                </div>
                <input
                  type="url"
                  value={avatarUrl}
                  onChange={(e) => setAvatarUrl(e.target.value)}
                  placeholder="https://example.com/images/avatar.jpg"
                  maxLength={2048}
                  className="block w-full pl-11 pr-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                />
              </div>
            </div>

            {/* Bio Description */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                  Biography / Academic Summary
                </label>
                <span className="text-[11px] text-slate-400 font-mono">
                  {bio.length} / 1000
                </span>
              </div>
              <div className="relative rounded-xl shadow-sm">
                <div className="absolute top-3 left-3.5 pointer-events-none text-slate-400">
                  <FileText className="h-5 w-5" />
                </div>
                <textarea
                  rows={4}
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  placeholder="Share a short summary about your academic focus, interests, or teaching background..."
                  maxLength={1000}
                  className="block w-full pl-11 pr-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                />
              </div>
            </div>

            {/* Save Button */}
            <div className="pt-2 flex justify-end">
              <button
                type="submit"
                disabled={updateMutation.isPending}
                className="inline-flex items-center px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm rounded-xl shadow-sm hover:shadow focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-60 transition"
              >
                {updateMutation.isPending ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                    <span>Saving Changes...</span>
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    <span>Save Changes</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Read-Only Account Summary & Info (1 col) */}
        <div className="space-y-6">
          {/* Identity & Account Card */}
          <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm space-y-4">
            <h3 className="font-bold text-sm text-slate-900 uppercase tracking-wider">
              Account Metadata
            </h3>

            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between py-2 border-b border-slate-100">
                <span className="text-slate-500 text-xs font-medium">User Identifier</span>
                <span className="font-mono text-xs text-slate-700 truncate max-w-[150px]" title={userData.id}>
                  {userData.id}
                </span>
              </div>

              <div className="flex items-center justify-between py-2 border-b border-slate-100">
                <span className="text-slate-500 text-xs font-medium">Account Status</span>
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                  {userData.is_active ? 'Active' : 'Suspended'}
                </span>
              </div>

              <div className="flex items-center justify-between py-2 border-b border-slate-100">
                <span className="text-slate-500 text-xs font-medium">Email Verified</span>
                <span className="text-xs font-semibold text-slate-700">
                  {userData.is_verified ? 'Yes' : 'Pending Verification'}
                </span>
              </div>

              <div className="flex items-center justify-between py-2">
                <span className="text-slate-500 text-xs font-medium">Last Profile Update</span>
                <span className="text-xs text-slate-600 font-mono">
                  {userData.profile?.updated_at
                    ? new Date(userData.profile.updated_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : 'Not yet'}
                </span>
              </div>
            </div>
          </div>

          {/* Privacy & Ethics Notice Card */}
          <div className="bg-indigo-50/60 rounded-2xl p-6 border border-indigo-100 text-xs text-indigo-950 space-y-2.5">
            <div className="flex items-center space-x-2 text-indigo-900 font-bold">
              <Shield className="w-4 h-4 text-indigo-600" />
              <span>Ethics & Privacy Assurance</span>
            </div>
            <p className="leading-relaxed text-indigo-900/80">
              Student emotional sentiment and longitudinal engagement scores are strictly processed
              through the platform's pseudonymization layer. Identifiable attributes are never
              exposed to downstream machine learning analytics pipelines.
            </p>
          </div>
        </div>
      </div>

      {/* Feature 6: Ethics & Privacy Consent Management (Students) */}
      {userData.role === 'student' && <PrivacySettings />}
    </div>
  );
};

