export * from './auth';
export * from './lead';
export * from './customer';
export * from './sale';
export * from './dashboard';

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiError {
  status: number;
  message: string;
  details?: Record<string, string[]>;
}
