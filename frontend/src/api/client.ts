import axios from "axios";
import type {
  CriteriaSet,
  CriteriaSetWithCriteria,
  Criterion,
  RecordDetail,
  RecordItem,
  ScoringSession,
} from "./types";

const api = axios.create({ baseURL: "/api" });

export const CriteriaApi = {
  listSets: () => api.get<CriteriaSet[]>("/criteria-sets").then((r) => r.data),
  getSet: (id: string) => api.get<CriteriaSetWithCriteria>(`/criteria-sets/${id}`).then((r) => r.data),
  createSet: (payload: Partial<CriteriaSet>) => api.post<CriteriaSet>("/criteria-sets", payload).then((r) => r.data),
  updateSet: (id: string, payload: Partial<CriteriaSet>) =>
    api.patch<CriteriaSet>(`/criteria-sets/${id}`, payload).then((r) => r.data),
  deleteSet: (id: string) => api.delete(`/criteria-sets/${id}`),

  addCriterion: (setId: string, payload: Partial<Criterion>) =>
    api.post<Criterion>(`/criteria-sets/${setId}/criteria`, payload).then((r) => r.data),
  updateCriterion: (id: string, payload: Partial<Criterion>) =>
    api.patch<Criterion>(`/criteria/${id}`, payload).then((r) => r.data),
  deleteCriterion: (id: string) => api.delete(`/criteria/${id}`),
};

export const RecordsApi = {
  list: () => api.get<RecordItem[]>("/records").then((r) => r.data),
  get: (id: string) => api.get<RecordDetail>(`/records/${id}`).then((r) => r.data),
  upload: (file: File, criteriaSetId: string, uploadedBy: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("criteria_set_id", criteriaSetId);
    form.append("uploaded_by", uploadedBy);
    return api.post<RecordItem>("/records", form).then((r) => r.data);
  },
  uploadFromUrl: (url: string, criteriaSetId: string, uploadedBy: string) =>
    api
      .post<RecordItem>("/records/from-url", { url, criteria_set_id: criteriaSetId, uploaded_by: uploadedBy })
      .then((r) => r.data),
  audioUrl: (id: string) => `/api/records/${id}/audio`,
  delete: (id: string) => api.delete(`/records/${id}`),
  update: (id: string, payload: { criteria_set_id?: string; uploaded_by?: string }) =>
    api.patch<RecordItem>(`/records/${id}`, payload).then((r) => r.data),
};

export const ScoringApi = {
  createSession: (recordId: string, scorerName: string) =>
    api.post<ScoringSession>(`/records/${recordId}/scoring-session`, { scorer_name: scorerName }).then((r) => r.data),
  get: (id: string) => api.get<ScoringSession>(`/scoring-sessions/${id}`).then((r) => r.data),
  list: () => api.get<ScoringSession[]>("/scoring-sessions").then((r) => r.data),
  update: (id: string, payload: Partial<ScoringSession>) =>
    api.patch<ScoringSession>(`/scoring-sessions/${id}`, payload).then((r) => r.data),
  updateItem: (sessionId: string, criterionId: string, payload: { final_score?: number | null; note?: string }) =>
    api
      .patch(`/scoring-sessions/${sessionId}/items/${criterionId}`, payload)
      .then((r) => r.data),
  complete: (id: string) => api.post<ScoringSession>(`/scoring-sessions/${id}/complete`).then((r) => r.data),
  delete: (id: string) => api.delete(`/scoring-sessions/${id}`),
};

export default api;
