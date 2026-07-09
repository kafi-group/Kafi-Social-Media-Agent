/**
 * TypeScript Interfaces - Updated for media upload & social posting
 */

export interface ContentGenerationRequest {
  platforms: string[];
  topic: string;
  brand_context?: string;
  tone?: string;
  target_audience?: string;
  call_to_action?: string;
  additional_instructions?: string;
}

export interface ContentRegenerateRequest {
  topic: string;
  brand_context?: string;
  tone?: string;
  target_audience?: string;
  call_to_action?: string;
  additional_instructions?: string;
  regeneration_instructions?: string;
}

export interface ContentGenerationResponse {
  content_id: number;
  platform: string;
  title: string;
  body: string;
  metadata: {
    hashtags: string[];
    keywords: string[];
    tone: string;
    target_audience: string;
    call_to_action?: string;
  };
  status: string;
  generated_at: string;
  media_path?: string | null;
  media_type?: string | null;
  media_original_name?: string | null;
}

export interface ContentDetailResponse extends ContentGenerationResponse {
  created_at: string;
  updated_at: string;
  linkedin_post_status?: string;
  facebook_post_status?: string;
  instagram_post_status?: string;
  youtube_post_status?: string;
  linkedin_post_id?: string | null;
  facebook_post_id?: string | null;
  instagram_post_id?: string | null;
  youtube_post_id?: string | null;
  linkedin_accounts_results?: LinkedInAccountPostResult[] | null;
}

export interface LinkedInAccountPostResult {
  label: string;
  status: string;
  post_id?: string | null;
  post_url?: string | null;
  error_message?: string | null;
}

export interface MediaUploadResponse {
  media_path: string;
  media_type: string;
  media_original_name: string;
  media_url: string;
}

export interface LinkedInAccountInfo {
  index: number;
  label: string;
  configured: boolean;
}

export interface SocialPostRequest {
  content_id: number;
  platforms: string[];
  draft_mode: boolean;
  override_title?: string | null;
  override_body?: string | null;
  linkedin_account_labels?: string[];
  designer_pin?: string | null;
}

export interface SocialPostResponse {
  content_id: number;
  platform: string;
  status: string;
  post_url?: string | null;
  post_id?: string | null;
  error_message?: string | null;
  account_label?: string | null;
}

export type ScheduleStatus =
  | 'pending'
  | 'publishing'
  | 'published'
  | 'partial'
  | 'failed'
  | 'cancelled';

export interface CalendarEvent {
  id: number;
  content_id: number;
  scheduled_date: string;
  status: ScheduleStatus | string;
  platforms: string[];
  draft_mode: boolean;
  override_title?: string | null;
  override_body?: string | null;
  linkedin_account_labels?: string[] | null;
  notes?: string | null;
  published_at?: string | null;
  error_message?: string | null;
  results?: SocialPostResponse[] | null;
  created_at: string;
  updated_at?: string | null;
  content_platform?: string | null;
  content_title?: string | null;
  content_body?: string | null;
  media_path?: string | null;
  media_type?: string | null;
  media_url?: string | null;
}

export interface CalendarEventCreate {
  content_id: number;
  scheduled_date: string; // ISO 8601 UTC
  platforms: string[];
  draft_mode?: boolean;
  override_title?: string | null;
  override_body?: string | null;
  linkedin_account_labels?: string[];
  notes?: string | null;
}

export interface CalendarEventUpdate {
  scheduled_date?: string;
  platforms?: string[];
  draft_mode?: boolean;
  override_title?: string | null;
  override_body?: string | null;
  linkedin_account_labels?: string[];
  notes?: string | null;
  status?: string;
}

export interface AnalyticsOverview {
  total_content_generated: number;
  content_by_platform: Record<string, number>;
  total_qa_passed: number;
  qa_pass_rate: number;
}

export type AnalyticsPlatform = 'facebook' | 'instagram' | 'youtube' | 'tiktok';

export type AnalyticsStatus = 'ok' | 'not_configured' | 'permission_error' | 'api_error';

export interface AnalyticsRange {
  start: string;
  end: string;
  days: number;
}

export interface AnalyticsTotals {
  views?: number;
  reach?: number;
  impressions?: number;
  engagements?: number;
  followers?: number;
  subscribers?: number;
  likes?: number;
  comments?: number;
  shares?: number;
  clicks?: number;
  watch_time_minutes?: number;
  configured_platforms?: number;
  total_platforms?: number;
}

export interface AnalyticsSeriesPoint {
  date: string;
  views?: number;
  engagements?: number;
}

export interface PlatformAnalyticsResponse {
  platform: AnalyticsPlatform;
  status: AnalyticsStatus;
  range: AnalyticsRange;
  totals: AnalyticsTotals;
  series: AnalyticsSeriesPoint[];
  message?: string;
  fetched_at?: string;
}

export interface AnalyticsSummaryResponse {
  range: AnalyticsRange;
  totals: AnalyticsTotals;
  platforms: PlatformAnalyticsResponse[];
}

// ---------------------------------------------------------------------------
// Designer Approval Workflow (QA Checker)
// ---------------------------------------------------------------------------

export type ApprovalStatus = 'pending' | 'approved' | 'rejected';

export interface ApprovalConfig {
  approval_required: boolean;
}

export interface ApprovalCreateRequest {
  content_id: number;
  platforms: string[];
  draft_mode?: boolean;
  override_title?: string | null;
  override_body?: string | null;
  linkedin_account_labels?: string[];
  requested_by?: string | null;
}

export interface ApprovalRequest {
  id: number;
  content_id: number;
  status: ApprovalStatus | string;
  platforms?: string[] | null;
  draft_mode: boolean;
  override_title?: string | null;
  override_body?: string | null;
  linkedin_account_labels?: string[] | null;
  requested_by?: string | null;
  reviewer_note?: string | null;
  results?: SocialPostResponse[] | null;
  decided_at?: string | null;
  created_at: string;
  title?: string | null;
  body?: string | null;
  media_path?: string | null;
  media_type?: string | null;
  media_url?: string | null;
  platform?: string | null;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  errors?: string[];
}

// ---------------------------------------------------------------------------
// Rival Review (competitor intelligence)
// ---------------------------------------------------------------------------

export type RivalPlatform = 'youtube' | 'instagram' | 'website';

export type RivalSnapshotStatus =
  | 'ok'
  | 'not_configured'
  | 'unavailable'
  | 'error';

export interface RivalRecentItem {
  title?: string;
  caption?: string;
  url?: string;
  published?: string;
  published_at?: string;
  timestamp?: string;
  summary?: string | null;
  views?: number;
  likes?: number;
  comments?: number;
  media_type?: string;
}

export interface RivalSnapshot {
  id: number;
  platform: RivalPlatform | string;
  status: RivalSnapshotStatus | string;
  metrics: Record<string, number | string | null>;
  recent_items: RivalRecentItem[];
  message?: string | null;
  captured_at?: string | null;
}

export interface Rival {
  id: number;
  name: string;
  category?: string | null;
  website?: string | null;
  youtube_channel_id?: string | null;
  youtube_handle?: string | null;
  instagram_username?: string | null;
  rss_url?: string | null;
  notes?: string | null;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  platforms: Partial<Record<RivalPlatform | string, RivalSnapshot>>;
  last_refreshed_at?: string | null;
}

export interface RivalCreate {
  name: string;
  category?: string | null;
  website?: string | null;
  youtube_channel_id?: string | null;
  youtube_handle?: string | null;
  instagram_username?: string | null;
  rss_url?: string | null;
  notes?: string | null;
  is_active?: boolean;
}

export type RivalUpdate = Partial<RivalCreate>;

export interface RivalInsight {
  rival: string;
  platform: 'youtube' | 'instagram' | 'website' | 'general' | string;
  observation: string;
  why_better: string;
  recommendation: string;
  priority: 'high' | 'medium' | 'low' | string;
}

export interface RivalPlatformConfig {
  configured: boolean;
  hint: string;
  auth_mode?: string | null;
  api_key_set?: boolean;
  oauth_set?: boolean;
}

export interface RivalsConfigResponse {
  youtube: RivalPlatformConfig;
  instagram: RivalPlatformConfig;
  website: RivalPlatformConfig;
}

export interface RivalInsightsResponse {
  generated_at: string;
  rival_count: number;
  our_summary?: unknown;
  suggestions: RivalInsight[];
  raw?: string | null;
  message?: string | null;
}

// ============================================
// Content Creation (chatbot)
// ============================================

export type ChatRole = 'system' | 'user' | 'assistant';

export interface ChatMessage {
  role: ChatRole;
  content: string;
  /** Base64 reference image for vision-based prompt writing (user messages). */
  image_base64?: string | null;
  image_mime_type?: string | null;
  /** Local preview URL (client-only, not sent to API). */
  image_preview_url?: string | null;
}

export type CreationIntent = 'prompt' | 'create_image' | 'create_voice' | 'video_prompt';

export interface ChatRequest {
  model: string;
  intent?: CreationIntent;
  language?: string;
  messages: ChatMessage[];
}

export interface MatchedProduct {
  id: string;
  name: string;
  brand: string;
  category: string;
  description: string;
  packaging: string[];
}

export interface ChatResponse {
  model: string;
  reply: string;
  matched_product?: MatchedProduct | null;
  intent?: CreationIntent;
}

export interface CreationModel {
  id: string;
  label: string;
}

export interface CreationModelsResponse {
  models: CreationModel[];
  gemini_web_url: string;
  meta_ai_web_url?: string;
  elevenlabs_web_url?: string;
  google_flow_characters_url?: string;
  google_flow_final_product_url?: string;
  chat_ready: boolean;
  image_ready?: boolean;
  image_model?: string;
  image_provider?: string;
  cloudflare_configured?: boolean;
  voice_ready?: boolean;
  voice_moods?: { id: string; label: string }[];
  languages?: { code: string; label: string; speech_lang: string }[];
}

export interface ImageGenerateResponse {
  media_path: string;
  media_url: string;
  model: string;
  caption?: string | null;
}

export interface VoiceGenerateResponse {
  media_path: string;
  media_url: string;
  mood: string;
  voice: string;
  script_preview: string;
}
