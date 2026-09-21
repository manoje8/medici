import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

import type { UploadedDoc } from '@/types';

interface UploadState {
  uploadedDocs: UploadedDoc[];
  isUploading: boolean;
  uploadError: string | null;
}

const initialState: UploadState = {
  uploadedDocs: [],
  isUploading: false,
  uploadError: null,
};

const uploadSlice = createSlice({
  name: 'upload',
  initialState,
  reducers: {
    addUploadedDoc(state, action: PayloadAction<UploadedDoc>) {
      state.uploadedDocs.push(action.payload);
    },
    setUploading(state, action: PayloadAction<boolean>) {
      state.isUploading = action.payload;
    },
    setUploadError(state, action: PayloadAction<string | null>) {
      state.uploadError = action.payload;
    },
    clearUploadedDocs(state) {
      state.uploadedDocs = [];
    },
  },
});

export const { addUploadedDoc, setUploading, setUploadError, clearUploadedDocs } =
  uploadSlice.actions;
export default uploadSlice.reducer;
