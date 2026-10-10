export type CreatorType = 'new' | 'existing';
export type ProfileFields = Record<'occupation' | 'experience' | 'skills' | 'interests' | 'creator_goal' | 'target_audience' | 'content_assets' | 'bio' | 'current_positioning' | 'operation_duration' | 'current_problem', string>;
export interface Account { id: string; name: string; creator_type: CreatorType; current_profile_version_id: string | null }
export interface Profile { id: string; version: number; created_at: string; raw_input: { fields?: ProfileFields; account?: { name: string; creator_type: CreatorType } } & Partial<ProfileFields> }
export interface DiagnosisResult {
  positioning_hypothesis: { positioning: string; target_audience: string; core_value: string; differentiation: string };
  content_pillars: { name: string; reason: string }[];
  strengths: string[]; risks: string[]; missing_information: string[]; assumptions: string[];
  confidence: 'low' | 'medium' | 'high';
}
export interface Diagnosis { id: string; profile_version_id: string; status: 'pending' | 'confirmed'; created_at: string; result: DiagnosisResult }
export interface Run { id: string; stage: string; status: 'running' | 'succeeded' | 'failed'; error: string | null; model: string | null; started_at: string; completed_at: string | null; retry_count: number; tokens: number | null; cost: number | null; latency: number | null }
export interface Projection { id: string; profile_version_id: string; status: 'pending' | 'synced' | 'failed'; error: string | null }
export interface GrowthState {
  accounts: Account[]; account: Account | null; profiles: Profile[]; diagnoses: Diagnosis[]; runs: Run[];
  current_profile: Profile | null; current_diagnosis: Diagnosis | null; projections: Projection[];
  counts: { research: number; topics: number; drafts: number }; next_step: string; model_configured?: boolean;
}
export interface AccountPayload { name: string; creator_type: CreatorType; profile: ProfileFields; expected_current_id: string | null }

export const emptyProfile: ProfileFields = { occupation: '', experience: '', skills: '', interests: '', creator_goal: '', target_audience: '', content_assets: '', bio: '', current_positioning: '', operation_duration: '', current_problem: '' };

export async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 110000);
  try {
    const response = await fetch(`./api/growth${path}`, {
      method, headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const message = typeof data?.detail === 'string' ? data.detail : '请求未通过校验，请检查输入后重试。';
      throw new Error(message);
    }
    if (!data) throw new Error('服务未返回有效数据，请检查后端是否已重启。');
    return data as T;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw new Error('请求等待超时。任务可能仍在运行，请刷新查看状态。');
    throw error;
  } finally { window.clearTimeout(timeout); }
}
