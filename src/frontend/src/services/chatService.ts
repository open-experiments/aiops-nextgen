import api from './api';
import type { ChatSession, ChatMessage, Persona } from '../types/chat';

export const chatService = {
  async createSession(personaId?: string, clusterContext?: string[]): Promise<ChatSession> {
    const response = await api.post('/chat/sessions', {
      persona_id: personaId,
      cluster_context: clusterContext,
    });
    return response.data;
  },

  async getSession(sessionId: string): Promise<ChatSession> {
    const response = await api.get(`/chat/sessions/${sessionId}`);
    return response.data;
  },

  async listSessions(): Promise<ChatSession[]> {
    const response = await api.get('/chat/sessions');
    return response.data.sessions || response.data;
  },

  async deleteSession(sessionId: string): Promise<void> {
    await api.delete(`/chat/sessions/${sessionId}`);
  },

  async sendMessage(sessionId: string, content: string): Promise<ChatMessage> {
    const response = await api.post(`/chat/sessions/${sessionId}/messages`, { content });
    return response.data;
  },

  async getMessages(sessionId: string): Promise<ChatMessage[]> {
    const response = await api.get(`/chat/sessions/${sessionId}/messages`);
    return response.data.messages || response.data;
  },

  async streamMessage(
    sessionId: string,
    content: string,
    onChunk: (chunk: string) => void
  ): Promise<void> {
    const response = await fetch(
      `${import.meta.env.VITE_API_URL || '/api/v1'}/chat/sessions/${sessionId}/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('auth_token') || ''}`,
        },
        body: JSON.stringify({ content }),
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) return;

    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      onChunk(chunk);
    }
  },

  async getPersonas(): Promise<Persona[]> {
    const response = await api.get('/personas');
    return response.data.personas || response.data;
  },
};
