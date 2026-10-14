/**
 * src/pages/StaffResourcesPage.tsx
 *
 * Feature 38-C: Staff Support Resources & Referral Library Management Page.
 * Allows counsellors and administrators to browse, filter, create, and update
 * learning resources, study skills guides, and service referrals.
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  BookOpen,
  Plus,
  Search,
  Filter,
  ExternalLink,
  PhoneCall,
  CheckCircle2,
  XCircle,
  FileText,
  AlertCircle,
  Edit,
  Loader2,
  X,
  Layers,
  Sparkles,
} from 'lucide-react';
import { StaffTabs } from '../components/staff/StaffTabs';
import {
  staffResourcesApi,
  SupportResourceItem,
  ResourceCreatePayload,
  ResourceUpdatePayload,
  ResourceType,
} from '../api/staffResources';

const INTERVENTION_TYPE_OPTIONS = [
  { value: 'academic_support', label: 'Academic Support & Tutoring' },
  { value: 'time_management_guidance', label: 'Time Management & Study Skills' },
  { value: 'additional_learning_resources', label: 'Supplementary Learning Materials' },
  { value: 'counselling_mental_health', label: 'Mental Health & Wellbeing Counselling' },
  { value: 'peer_mentoring', label: 'Peer Mentoring Connection' },
  { value: 'referral_services', label: 'Campus Support Services Referral' },
  { value: 'academic_advising', label: 'Academic Advising Consultation' },
];

export const StaffResourcesPage: React.FC = () => {
  const queryClient = useQueryClient();

  // Filters
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [activeFilter, setActiveFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [editingResource, setEditingResource] = useState<SupportResourceItem | null>(null);

  // Form states
  const [formData, setFormData] = useState<{
    title: string;
    description: string;
    resource_type: ResourceType;
    url: string;
    contact_info: string;
    intervention_types: string[];
    is_active: boolean;
  }>({
    title: '',
    description: '',
    resource_type: 'resource',
    url: '',
    contact_info: '',
    intervention_types: ['additional_learning_resources'],
    is_active: true,
  });

  const [formError, setFormError] = useState<string | null>(null);
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null);

  // Fetch resources
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['staff-resources-list', typeFilter, activeFilter],
    queryFn: () => {
      const activeParam =
        activeFilter === 'all' ? undefined : activeFilter === 'active';
      return staffResourcesApi.getResources({
        type: typeFilter || undefined,
        active: activeParam,
      });
    },
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (payload: ResourceCreatePayload) => staffResourcesApi.createResource(payload),
    onSuccess: (res) => {
      setIsModalOpen(false);
      resetForm();
      setFeedbackSuccess(`Resource "${res.title}" created successfully.`);
      queryClient.invalidateQueries({ queryKey: ['staff-resources-list'] });
      queryClient.invalidateQueries({ queryKey: ['staff-resources-active'] });
      setTimeout(() => setFeedbackSuccess(null), 4000);
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to save resource. Ensure URL uses http/https protocol.';
      setFormError(detail);
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ResourceUpdatePayload }) =>
      staffResourcesApi.updateResource(id, payload),
    onSuccess: (res) => {
      setIsModalOpen(false);
      resetForm();
      setFeedbackSuccess(`Resource "${res.title}" updated successfully.`);
      queryClient.invalidateQueries({ queryKey: ['staff-resources-list'] });
      queryClient.invalidateQueries({ queryKey: ['staff-resources-active'] });
      setTimeout(() => setFeedbackSuccess(null), 4000);
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to update resource. Ensure at least one of URL or Contact info is present.';
      setFormError(detail);
    },
  });

  // Toggle active mutation
  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      staffResourcesApi.updateResource(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['staff-resources-list'] });
      queryClient.invalidateQueries({ queryKey: ['staff-resources-active'] });
    },
    onError: (err: any) => {
      alert(err?.response?.data?.detail || 'Failed to toggle resource status.');
    },
  });

  const resetForm = () => {
    setEditingResource(null);
    setFormData({
      title: '',
      description: '',
      resource_type: 'resource',
      url: '',
      contact_info: '',
      intervention_types: ['additional_learning_resources'],
      is_active: true,
    });
    setFormError(null);
  };

  const handleOpenCreate = () => {
    resetForm();
    setIsModalOpen(true);
  };

  const handleOpenEdit = (res: SupportResourceItem) => {
    setEditingResource(res);
    setFormData({
      title: res.title,
      description: res.description,
      resource_type: res.resource_type,
      url: res.url || '',
      contact_info: res.contact_info || '',
      intervention_types: res.intervention_types || [],
      is_active: res.is_active,
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    // Basic frontend check
    if (!formData.url.trim() && !formData.contact_info.trim()) {
      setFormError('At least one of Web URL or Contact Information is required.');
      return;
    }

    if (
      formData.url.trim() &&
      !formData.url.trim().startsWith('http://') &&
      !formData.url.trim().startsWith('https://')
    ) {
      setFormError('URL must use an "http://" or "https://" scheme (e.g., https://example.com).');
      return;
    }

    const payload: ResourceCreatePayload = {
      title: formData.title.trim(),
      description: formData.description.trim(),
      resource_type: formData.resource_type,
      url: formData.url.trim() ? formData.url.trim() : null,
      contact_info: formData.contact_info.trim() ? formData.contact_info.trim() : null,
      intervention_types: formData.intervention_types,
      is_active: formData.is_active,
    };

    if (editingResource) {
      updateMutation.mutate({ id: editingResource.id, payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const toggleInterventionType = (typeKey: string) => {
    setFormData((prev) => {
      const exists = prev.intervention_types.includes(typeKey);
      if (exists) {
        return {
          ...prev,
          intervention_types: prev.intervention_types.filter((t) => t !== typeKey),
        };
      } else {
        return {
          ...prev,
          intervention_types: [...prev.intervention_types, typeKey],
        };
      }
    });
  };

  // Filter items by search query
  const filteredItems = (data?.items || []).filter((item) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      item.title.toLowerCase().includes(q) ||
      item.description.toLowerCase().includes(q) ||
      (item.url && item.url.toLowerCase().includes(q)) ||
      (item.contact_info && item.contact_info.toLowerCase().includes(q))
    );
  });

  const getResourceTypeBadge = (type: string) => {
    switch (type) {
      case 'guidance':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200">
            <FileText className="w-3 h-3" />
            Guidance
          </span>
        );
      case 'referral':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
            <PhoneCall className="w-3 h-3" />
            Referral
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <BookOpen className="w-3 h-3" />
            Resource
          </span>
        );
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <StaffTabs />

      {/* Page Title & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-indigo-600" />
            Support Resources & Referral Library
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Curate supplementary learning materials, time-management guides, and university service referrals for intervention sharing.
          </p>
        </div>

        <button
          onClick={handleOpenCreate}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold hover:bg-indigo-700 shadow-sm transition self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          Add Resource or Referral
        </button>
      </div>

      {/* Success Notification */}
      {feedbackSuccess && (
        <div className="mb-6 p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{feedbackSuccess}</span>
        </div>
      )}

      {/* Filters Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search resources by title, description or URL..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 text-xs border border-slate-200 rounded-xl bg-slate-50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        {/* Filter Chips */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-600">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span>Type:</span>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="text-xs border-slate-200 rounded-lg px-2.5 py-1 bg-slate-50 focus:bg-white focus:border-indigo-500"
            >
              <option value="">All Types</option>
              <option value="resource">Learning Resource</option>
              <option value="guidance">Time Guidance</option>
              <option value="referral">Campus Referral</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5 text-xs text-slate-600">
            <span>Status:</span>
            <select
              value={activeFilter}
              onChange={(e) => setActiveFilter(e.target.value)}
              className="text-xs border-slate-200 rounded-lg px-2.5 py-1 bg-slate-50 focus:bg-white focus:border-indigo-500"
            >
              <option value="all">All</option>
              <option value="active">Active Only</option>
              <option value="inactive">Inactive Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* Resources Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
            <Loader2 className="w-5 h-5 animate-spin text-indigo-600" />
            Loading resource catalog...
          </div>
        ) : isError ? (
          <div className="p-12 text-center text-xs text-rose-600">
            <AlertCircle className="w-6 h-6 mx-auto mb-2 text-rose-500" />
            Failed to load resources: {(error as any)?.message || 'Network error'}
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-400 space-y-3">
            <Layers className="w-8 h-8 mx-auto text-slate-300" />
            <p>No support resources found matching your current filters.</p>
            <button
              onClick={handleOpenCreate}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg font-semibold hover:bg-indigo-100 transition"
            >
              <Plus className="w-3.5 h-3.5" />
              Create First Resource
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase tracking-wider text-[11px] font-bold">
                  <th className="py-3 px-4">Title & Description</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Access Point</th>
                  <th className="py-3 px-4">Applicable Interventions</th>
                  <th className="py-3 px-4 text-center">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredItems.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/50 transition">
                    {/* Title & Desc */}
                    <td className="py-3.5 px-4 max-w-xs">
                      <span className="font-bold text-slate-900 block text-xs">
                        {item.title}
                      </span>
                      <p className="text-[11px] text-slate-500 line-clamp-2 mt-0.5">
                        {item.description}
                      </p>
                    </td>

                    {/* Type */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {getResourceTypeBadge(item.resource_type)}
                    </td>

                    {/* Access Point (URL / Contact) */}
                    <td className="py-3.5 px-4 max-w-xs">
                      {item.url && (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 font-semibold truncate max-w-full block"
                        >
                          <ExternalLink className="w-3 h-3 flex-shrink-0" />
                          <span className="truncate">{item.url}</span>
                        </a>
                      )}
                      {item.contact_info && (
                        <span className="inline-flex items-center gap-1 text-slate-700 bg-slate-100 px-2 py-0.5 rounded text-[11px] mt-1">
                          <PhoneCall className="w-3 h-3 text-slate-500 flex-shrink-0" />
                          <span className="truncate">{item.contact_info}</span>
                        </span>
                      )}
                    </td>

                    {/* Applicable types */}
                    <td className="py-3.5 px-4">
                      <div className="flex flex-wrap gap-1">
                        {item.intervention_types && item.intervention_types.length > 0 ? (
                          item.intervention_types.map((it) => (
                            <span
                              key={it}
                              className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px] font-mono"
                            >
                              {it}
                            </span>
                          ))
                        ) : (
                          <span className="text-[11px] text-slate-400">All types</span>
                        )}
                      </div>
                    </td>

                    {/* Active toggle */}
                    <td className="py-3.5 px-4 text-center whitespace-nowrap">
                      <button
                        onClick={() =>
                          toggleActiveMutation.mutate({
                            id: item.id,
                            is_active: !item.is_active,
                          })
                        }
                        title={item.is_active ? 'Click to deactivate' : 'Click to activate'}
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold border transition ${
                          item.is_active
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                            : 'bg-slate-100 text-slate-500 border-slate-200 hover:bg-slate-200'
                        }`}
                      >
                        {item.is_active ? (
                          <>
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            Active
                          </>
                        ) : (
                          <>
                            <XCircle className="w-3 h-3 text-slate-400" />
                            Inactive
                          </>
                        )}
                      </button>
                    </td>

                    {/* Actions */}
                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <button
                        onClick={() => handleOpenEdit(item)}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-slate-600 hover:text-indigo-600 hover:bg-slate-100 text-xs font-semibold transition"
                      >
                        <Edit className="w-3.5 h-3.5" />
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create / Edit Modal Dialog */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm overflow-y-auto">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-xl border border-slate-200 my-8">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-xl bg-indigo-50 text-indigo-600">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    {editingResource ? 'Edit Support Resource' : 'Catalog New Support Resource'}
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Provide title, type, and at least one destination URL or service contact.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {formError && (
              <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleFormSubmit} className="space-y-4">
              {/* Title */}
              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Resource Title (max 120 chars) <span className="text-rose-500">*</span>:
                </label>
                <input
                  type="text"
                  maxLength={120}
                  required
                  placeholder="e.g. Formative Quiz Walkthrough & Practice Notes"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="w-full text-xs border border-slate-200 rounded-xl px-3 py-2 bg-slate-50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* Resource Type */}
              <div className="grid grid-cols-3 gap-2">
                <label className="text-xs font-semibold text-slate-700 col-span-3 mb-0.5">
                  Resource Classification:
                </label>
                {(['resource', 'guidance', 'referral'] as ResourceType[]).map((rt) => (
                  <button
                    key={rt}
                    type="button"
                    onClick={() => setFormData({ ...formData, resource_type: rt })}
                    className={`py-2 px-3 rounded-xl text-xs font-semibold border text-center transition capitalize ${
                      formData.resource_type === rt
                        ? 'border-indigo-600 bg-indigo-50 text-indigo-900 ring-1 ring-indigo-500'
                        : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {rt === 'resource'
                      ? 'Learning Resource'
                      : rt === 'guidance'
                      ? 'Study Guidance'
                      : 'Campus Referral'}
                  </button>
                ))}
              </div>

              {/* Description */}
              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Overview & Guidance Instructions (max 500 chars) <span className="text-rose-500">*</span>:
                </label>
                <textarea
                  rows={3}
                  maxLength={500}
                  required
                  placeholder="Briefly describe what this material covers or how students should utilize this referral..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full text-xs border border-slate-200 rounded-xl p-2.5 bg-slate-50 focus:bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* URL & Contact Info Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-3.5 rounded-xl bg-slate-50 border border-slate-100">
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">
                    Web URL (http/https only):
                  </label>
                  <input
                    type="text"
                    maxLength={2048}
                    placeholder="https://learning.university.edu/guide"
                    value={formData.url}
                    onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                    className="w-full text-xs border border-slate-200 rounded-xl px-3 py-2 bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  />
                  <span className="text-[10px] text-slate-400 block mt-0.5">
                    For digital links or guides
                  </span>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">
                    Contact Point / Location:
                  </label>
                  <input
                    type="text"
                    maxLength={200}
                    placeholder="Student Wellbeing Hub, Room B-204"
                    value={formData.contact_info}
                    onChange={(e) => setFormData({ ...formData, contact_info: e.target.value })}
                    className="w-full text-xs border border-slate-200 rounded-xl px-3 py-2 bg-white focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  />
                  <span className="text-[10px] text-slate-400 block mt-0.5">
                    For physical service referrals
                  </span>
                </div>

                <p className="col-span-full text-[11px] text-slate-500 italic">
                  * Note: At least one of Web URL or Contact Point must be provided.
                </p>
              </div>

              {/* Linked Intervention Types */}
              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1.5">
                  Associated Canonical Intervention Types:
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-36 overflow-y-auto p-2 rounded-xl border border-slate-200 bg-slate-50">
                  {INTERVENTION_TYPE_OPTIONS.map((opt) => (
                    <label
                      key={opt.value}
                      className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer p-1 rounded hover:bg-white"
                    >
                      <input
                        type="checkbox"
                        checked={formData.intervention_types.includes(opt.value)}
                        onChange={() => toggleInterventionType(opt.value)}
                        className="rounded text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="truncate">{opt.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Active Toggle */}
              <div className="flex items-center justify-between pt-1">
                <label className="flex items-center gap-2 text-xs font-semibold text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className="rounded text-indigo-600 focus:ring-indigo-500"
                  />
                  <span>Active & available for staff to share</span>
                </label>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending || updateMutation.isPending}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition disabled:opacity-50"
                  >
                    {createMutation.isPending || updateMutation.isPending ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Saving...
                      </>
                    ) : editingResource ? (
                      'Save Changes'
                    ) : (
                      'Create Resource'
                    )}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
