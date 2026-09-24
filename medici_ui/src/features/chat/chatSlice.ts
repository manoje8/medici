import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { v4 as uuidv4 } from 'uuid';

import type { Message, PipelineStage } from '@/types';

interface ChatState {
  messages: Message[];
  sessionId: string;
  userId: string;
  isProcessing: boolean;
  pipelineStages: PipelineStage[];
  streamingTokens: string;
  isStreaming: boolean;
}

const getUserId = () => {
  if (typeof window === 'undefined') return uuidv4();
  let id = localStorage.getItem('medici_user_id');
  if (!id) {
    id = uuidv4();
    localStorage.setItem('medici_user_id', id);
  }
  return id;
};

const initialState: ChatState = {
  messages: [],
  sessionId: uuidv4(),
  userId: getUserId(),
  isProcessing: false,
  pipelineStages: [],
  streamingTokens: '',
  isStreaming: false,
};

const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    addMessage(state, action: PayloadAction<Message>) {
      state.messages.push(action.payload);
    },
    updateLastAssistantMessage(state, action: PayloadAction<Partial<Message>>) {
      const lastMsg = [...state.messages].reverse().find((m) => m.role === 'assistant');
      if (lastMsg) {
        Object.assign(lastMsg, action.payload);
      }
    },
    clearMessages(state) {
      state.messages = [];
    },
    resetSession(state) {
      state.messages = [];
      state.sessionId = uuidv4();
      state.pipelineStages = [];
      state.streamingTokens = '';
      state.isProcessing = false;
      state.isStreaming = false;
    },
    loadSession(state, action: PayloadAction<{ sessionId: string; messages: Message[] }>) {
      state.sessionId = action.payload.sessionId;
      state.messages = action.payload.messages;
      state.pipelineStages = [];
      state.streamingTokens = '';
      state.isProcessing = false;
      state.isStreaming = false;
    },
    setProcessing(state, action: PayloadAction<boolean>) {
      state.isProcessing = action.payload;
    },
    addPipelineStage(state, action: PayloadAction<PipelineStage>) {
      state.pipelineStages.push(action.payload);
    },
    clearPipelineStages(state) {
      state.pipelineStages = [];
    },
    appendStreamingToken(state, action: PayloadAction<string>) {
      state.streamingTokens += action.payload;
    },
    clearStreamingTokens(state) {
      state.streamingTokens = '';
    },
    setStreaming(state, action: PayloadAction<boolean>) {
      state.isStreaming = action.payload;
    },
  },
});

export const {
  addMessage,
  updateLastAssistantMessage,
  clearMessages,
  resetSession,
  loadSession,
  setProcessing,
  addPipelineStage,
  clearPipelineStages,
  appendStreamingToken,
  clearStreamingTokens,
  setStreaming,
} = chatSlice.actions;
export default chatSlice.reducer;
