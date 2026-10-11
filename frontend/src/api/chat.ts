/**
 * src/api/chat.ts
 *
 * API module for direct / chat messaging (Feature 15).
 */

import { apiClient } from './client';

// ── Interfaces ───────────────────────────────────────────────────────────────

export interface ChatUserSummary {
  id: string;
  full_name: string;
  role: string;
}

export interface ConversationListItem {
  id: string;
  participant_ids: string[];
  created_at: string;
  last_message_at: string;
  last_message_preview: string;
  last_message_sender_id: string | null;
  other_participant?: ChatUserSummary | null;
  unread_count: number;
}

export interface ConversationResponse {
  id: string;
  participant_ids: string[];
  participant_key: string;
  created_at: string;
  last_message_at: string;
  last_message_preview: string;
  last_message_sender_id: string | null;
  other_participant?: ChatUserSummary | null;
}

export interface MessageResponse {
  id: string;
  conversation_id: string;
  sender_id: string;
  sender_role: string;
  recipient_id: string;
  body: string;
  created_at: string;
  read_at: string | null;
  metadata: Record<string, any>;
}

// ── API functions ────────────────────────────────────────────────────────────

export const searchChatUsers = async (
  params?: { search?: string; limit?: number }
): Promise<ChatUserSummary[]> => {
  const response = await apiClient.get<ChatUserSummary[]>('/chat/users', {
    params,
  });
  return response.data;
};

export const getConversations = async (): Promise<ConversationListItem[]> => {
  const response = await apiClient.get<ConversationListItem[]>(
    '/chat/conversations'
  );
  return response.data;
};

export const createConversation = async (
  recipientId: string
): Promise<ConversationResponse> => {
  const response = await apiClient.post<ConversationResponse>(
    '/chat/conversations',
    { recipient_id: recipientId }
  );
  return response.data;
};

export const getMessages = async (
  conversationId: string,
  params?: { limit?: number; before?: string }
): Promise<MessageResponse[]> => {
  const response = await apiClient.get<MessageResponse[]>(
    `/chat/conversations/${conversationId}/messages`,
    { params }
  );
  return response.data;
};

export const markConversationRead = async (
  conversationId: string
): Promise<void> => {
  await apiClient.post(`/chat/conversations/${conversationId}/read`);
};

export const sendMessage = async (
  conversationId: string,
  body: string
): Promise<MessageResponse> => {
  const response = await apiClient.post<MessageResponse>(
    `/chat/conversations/${conversationId}/messages`,
    { body }
  );
  return response.data;
};

export const chatApi = {
  searchChatUsers,
  getConversations,
  createConversation,
  getMessages,
  markConversationRead,
  sendMessage,
};
