import { create } from 'zustand';
import type { ChatSession, ChatMessage, Persona } from '../types/chat';
import { chatService } from '../services/chatService';

interface ChatState {
  sessions: ChatSession[];
  currentSession: ChatSession | null;
  messages: ChatMessage[];
  personas: Persona[];
  selectedPersona: Persona | null;
  streaming: boolean;
  loading: boolean;
  error: string | null;
  fetchSessions: () => Promise<void>;
  fetchPersonas: () => Promise<void>;
  createSession: (personaId?: string) => Promise<ChatSession>;
  selectSession: (sessionId: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  setPersona: (persona: Persona) => void;
  addMessage: (message: ChatMessage) => void;
  updateStreamingContent: (content: string) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  currentSession: null,
  messages: [],
  personas: [],
  selectedPersona: null,
  streaming: false,
  loading: false,
  error: null,

  fetchSessions: async () => {
    try {
      const sessions = await chatService.listSessions();
      set({ sessions });
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    }
  },

  fetchPersonas: async () => {
    try {
      const personas = await chatService.getPersonas();
      set({ personas, selectedPersona: personas[0] || null });
    } catch (error) {
      console.error('Failed to fetch personas:', error);
    }
  },

  createSession: async (personaId?: string) => {
    const persona = personaId || get().selectedPersona?.id;
    const session = await chatService.createSession(persona);
    set((state) => ({
      sessions: [session, ...state.sessions],
      currentSession: session,
      messages: [],
    }));
    return session;
  },

  selectSession: async (sessionId: string) => {
    set({ loading: true });
    try {
      const session = await chatService.getSession(sessionId);
      const messages = await chatService.getMessages(sessionId);
      set({ currentSession: session, messages, loading: false });
    } catch (error) {
      set({ error: (error as Error).message, loading: false });
    }
  },

  sendMessage: async (content: string) => {
    const session = get().currentSession;
    if (!session) {
      // Create a new session if none exists
      const newSession = await get().createSession();
      set({ currentSession: newSession });
    }

    const currentSession = get().currentSession!;

    // Add user message
    const userMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      session_id: currentSession.id,
      role: 'USER',
      content,
      persona_id: null,
      tool_calls: null,
      tool_results: null,
      model: null,
      tokens_used: null,
      latency_ms: null,
      created_at: new Date().toISOString(),
    };
    set((state) => ({ messages: [...state.messages, userMessage] }));

    // Stream the response
    set({ streaming: true });
    let assistantContent = '';

    try {
      await chatService.streamMessage(currentSession.id, content, (chunk) => {
        assistantContent += chunk;
        get().updateStreamingContent(assistantContent);
      });
    } catch (error) {
      set({ error: (error as Error).message });
    } finally {
      set({ streaming: false });
    }
  },

  setPersona: (persona: Persona) => {
    set({ selectedPersona: persona });
  },

  addMessage: (message: ChatMessage) => {
    set((state) => ({
      messages: [...state.messages, message],
    }));
  },

  updateStreamingContent: (content: string) => {
    set((state) => {
      const messages = [...state.messages];
      const lastMessage = messages[messages.length - 1];

      if (lastMessage?.role === 'ASSISTANT') {
        messages[messages.length - 1] = { ...lastMessage, content };
      } else {
        messages.push({
          id: `stream-${Date.now()}`,
          session_id: state.currentSession?.id || '',
          role: 'ASSISTANT',
          content,
          persona_id: state.selectedPersona?.id || null,
          tool_calls: null,
          tool_results: null,
          model: null,
          tokens_used: null,
          latency_ms: null,
          created_at: new Date().toISOString(),
        });
      }

      return { messages };
    });
  },
}));
