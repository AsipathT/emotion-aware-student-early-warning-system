/**
 * src/api/staffResources.ts
 *
 * Feature 38-C: Staff Support Resources & Referral Library API Client.
 * Connects to /api/v1/support/resources for cataloging learning materials,
 * guidance guides, and campus referrals, and sharing them with interventions.
 */

import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1/support/resources',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to attach JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export type ResourceType = 'resource' | 'guidance' | 'referral';

export interface SupportResourceItem {
  id: string;
  title: string;
  description: string;
  resource_type: ResourceType;
  url?: string | null;
  contact_info?: string | null;
  intervention_types: string[];
  is_active: boolean;
  created_by: string;
  created_at: string;
  updated_at?: string | null;
}

export interface ResourceListResponse {
  items: SupportResourceItem[];
  total_count: number;
}

export interface ResourceCreatePayload {
  title: string;
  description: string;
  resource_type: ResourceType;
  url?: string | null;
  contact_info?: string | null;
  intervention_types?: string[];
  is_active?: boolean;
}

export interface ResourceUpdatePayload {
  title?: string;
  description?: string;
  resource_type?: ResourceType;
  url?: string | null;
  contact_info?: string | null;
  intervention_types?: string[];
  is_active?: boolean;
}

export interface SharedResourceItem {
  resource_id: string;
  title: string;
  description: string;
  resource_type: string;
  url?: string | null;
  contact_info?: string | null;
  shared_at: string;
  shared_by: string;
  viewed_at?: string | null;
  message?: string | null;
}

export interface SharedResourceListResponse {
  items: SharedResourceItem[];
  total_count: number;
}

export interface ShareResourceRequestPayload {
  resource_id: string;
  message?: string | null;
}

export const staffResourcesApi = {
  /**
   * Retrieves resources with optional type, intervention_type, and active filters.
   */
  getResources: async (params?: {
    type?: string;
    intervention_type?: string;
    active?: boolean;
  }): Promise<ResourceListResponse> => {
    const res = await api.get<ResourceListResponse>('', { params });
    return res.data;
  },

  /**
   * Retrieves a single support resource by ID.
   */
  getResource: async (id: string): Promise<SupportResourceItem> => {
    const res = await api.get<SupportResourceItem>(`/${encodeURIComponent(id)}`);
    return res.data;
  },

  /**
   * Creates a new support resource, guidance note, or campus referral.
   */
  createResource: async (payload: ResourceCreatePayload): Promise<SupportResourceItem> => {
    const res = await api.post<SupportResourceItem>('', payload);
    return res.data;
  },

  /**
   * Updates an existing resource or toggles its active status.
   */
  updateResource: async (
    id: string,
    payload: ResourceUpdatePayload,
  ): Promise<SupportResourceItem> => {
    const res = await api.patch<SupportResourceItem>(`/${encodeURIComponent(id)}`, payload);
    return res.data;
  },

  /**
   * Retrieves shared resources for a specific intervention.
   */
  getSharedResources: async (interventionId: string): Promise<SharedResourceListResponse> => {
    const res = await api.get<SharedResourceListResponse>(
      `/interventions/${encodeURIComponent(interventionId)}/shared`,
    );
    return res.data;
  },

  /**
   * Shares a cataloged resource with an accepted/in-progress intervention.
   */
  shareResource: async (
    interventionId: string,
    payload: ShareResourceRequestPayload,
  ): Promise<SharedResourceItem> => {
    const res = await api.post<SharedResourceItem>(
      `/interventions/${encodeURIComponent(interventionId)}/share`,
      payload,
    );
    return res.data;
  },
};
