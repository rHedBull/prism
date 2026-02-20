import api from "./api";
import type { FileMetadata, PaginatedResponse } from "../types/api";

export async function uploadFile(
  workspaceId: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<FileMetadata> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("workspace_id", workspaceId);

  const { data } = await api.post<FileMetadata>("/files/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (event) => {
      if (event.total && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    },
  });
  return data;
}

export async function listFiles(
  workspaceId: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedResponse<FileMetadata>> {
  const { data } = await api.get<PaginatedResponse<FileMetadata>>("/files", {
    params: { workspace_id: workspaceId, page, page_size: pageSize },
  });
  return data;
}

export async function deleteFile(fileId: string): Promise<void> {
  await api.delete(`/files/${fileId}`);
}

export async function getDownloadUrl(fileId: string): Promise<string> {
  const { data } = await api.get<{ url: string }>(`/files/${fileId}/download-url`);
  return data.url;
}
