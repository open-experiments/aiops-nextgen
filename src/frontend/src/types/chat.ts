export type MessageRole = 'USER' | 'ASSISTANT' | 'SYSTEM' | 'TOOL';

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface ToolResult {
  tool_call_id: string;
  status: 'SUCCESS' | 'ERROR' | 'TIMEOUT';
  result: unknown;
  error: string | null;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  persona_id: string | null;
  tool_calls: ToolCall[] | null;
  tool_results: ToolResult[] | null;
  model: string | null;
  tokens_used: number | null;
  latency_ms: number | null;
  created_at: string;
}

export interface ChatSession {
  id: string;
  user_id: string;
  title: string;
  persona_id: string;
  cluster_context: string[];
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface Persona {
  id: string;
  name: string;
  description: string;
  icon: string;
  capabilities: string[];
}
