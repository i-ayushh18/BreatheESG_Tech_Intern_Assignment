import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface IngestionResponse {
  id: number;
  status: string;
}

export interface NormalizedRecord {
  id: number;
  facility: string;
  activity_type: string;
  scope: number;
  activity_value: number;
  activity_unit: string;
  co2e_kg: number;
  status: 'pending' | 'approved' | 'flagged' | 'locked';
  flagged_reason?: string | null;
  quality_flags?: DataQualityFlag[];
  flag_count?: number;
  highest_severity?: 'warning' | 'error' | '';
}

export interface DataQualityFlag {
  id: number;
  flag_type: string;
  severity: 'warning' | 'error';
  description: string;
  created_at: string;
}

export interface RawRecordIssue {
  id: number;
  ingestion: number;
  ingestion_source_type: string;
  ingestion_filename: string;
  ingestion_status: string;
  row_number: number;
  raw_data: Record<string, unknown>;
  normalized_count: number;
  validation_error: string;
  created_at: string;
}

export interface PaginatedResponse<T> {
  results?: T[];
  count?: number;
}

export interface AuditLog {
  id: number;
  changed_at: string;
  field_name: string;
  old_value: string;
  new_value: string;
  reason: string;
}

export const uploadFile = async (
  sourceType: string,
  file: File,
  clientId: number
): Promise<IngestionResponse> => {
  const formData = new FormData();
  formData.append('source_type', sourceType);
  formData.append('file', file);
  formData.append('client_id', clientId.toString());

  const response = await api.post<IngestionResponse>('/ingest/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const getClients = async (): Promise<any[]> => {
  const response = await api.get<any>('/clients/');
  const data = response.data;
  // DRF may return paginated results { count, results, ... }
  if (data && Array.isArray(data)) return data;
  if (data && data.results && Array.isArray(data.results)) return data.results;
  return [];
};

export const getRecords = async (params: Record<string, string> = {}): Promise<NormalizedRecord[]> => {
  const response = await api.get<PaginatedResponse<NormalizedRecord> | NormalizedRecord[]>('/records/', { params });
  const data = response.data as PaginatedResponse<NormalizedRecord>;
  return data.results || (response.data as NormalizedRecord[]);
};

export const getInvalidRawRecords = async (
  params: Record<string, string> = {}
): Promise<RawRecordIssue[]> => {
  const response = await api.get<PaginatedResponse<RawRecordIssue> | RawRecordIssue[]>(
    '/raw-records/',
    { params: { invalid_only: 'true', ...params } }
  );
  const data = response.data as PaginatedResponse<RawRecordIssue>;
  return data.results || (response.data as RawRecordIssue[]);
};

export const approveRecord = async (recordId: number): Promise<NormalizedRecord> => {
  const response = await api.post<NormalizedRecord>(`/records/${recordId}/approve/`);
  return response.data;
};

export const flagRecord = async (recordId: number, reason: string): Promise<NormalizedRecord> => {
  const response = await api.post<NormalizedRecord>(`/records/${recordId}/flag/`, { reason });
  return response.data;
};

export const getAuditLog = async (recordId: number): Promise<AuditLog[]> => {
  const response = await api.get<AuditLog[]>(`/records/${recordId}/audit_log/`);
  return response.data;
};

export const bulkApprove = async (recordIds: number[]): Promise<{ message: string }> => {
  const response = await api.post<{ message: string }>('/records/bulk_approve/', { record_ids: recordIds });
  return response.data;
};
