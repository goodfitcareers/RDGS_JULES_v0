export interface ClientRead {
  id: string; // UUID
  display_name: string;
  notes?: string | null;
  created_at: string; // ISO datetime string
}

// Add other shared types here as needed
// For example, for API error responses (if standardized)
export interface ApiError {
  message: string;
  details?: any;
}

export enum RoleStatus {
  Pending = "Pending",           // Initial state before parsing
  Parsed = "Parsed",             // Successfully parsed from input_text by LLM
  InputCurated = "InputCurated",   // User has curated the input_text_compact for this role
  RolesVerified = "RolesVerified", // User has verified/edited the role fields (company, title, dates)
  CompanyVerified = "CompanyVerified", // User has verified/edited company details (not part of role editing)
  Processing = "Processing",       // Input text is currently being processed (e.g., by LLM)
  Failed = "Failed",               // Processing failed
}

export interface RoleRead {
  id: string; // UUID
  client_id: string; // UUID, Foreign Key to Client
  company_name: string;
  title: string;
  start_date?: string | null; // Date as string (e.g., "YYYY-MM-DD")
  end_date?: string | null; // Date as string (e.g., "YYYY-MM-DD")
  output_text: string; // The raw text output from the LLM for this role
  status: RoleStatus;
  input_text_compact?: string | null; // Compacted input text for this role, if HITL editing was done
  revision: number; // For optimistic locking
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
}

export interface RoleUpdate {
  company_name?: string;
  title?: string;
  start_date?: string | null;
  end_date?: string | null;
  input_text_compact?: string | null;
  status?: RoleStatus | null;
  revision: number; // Must be included for updates
}
