import Constants from 'expo-constants';
import { Platform } from 'react-native';

// ── Auto-detect the backend IP from Expo's dev server ──
// This reads the IP that Expo uses to serve the JS bundle (your PC's LAN IP)
// and reuses it for API calls, so it never goes stale on restart/network change.
function getApiBase(): string {
    // debuggerHost is "IP:PORT" of the Expo dev server (e.g. "192.168.1.5:8081")
    const debuggerHost =
        Constants.expoConfig?.hostUri ||        // SDK 50+
        (Constants as any).manifest?.debuggerHost ||  // older SDKs
        (Constants as any).manifest2?.extra?.expoGo?.debuggerHost;

    if (debuggerHost) {
        const ip = debuggerHost.split(':')[0];  // strip the Expo port
        console.log(`[API] Auto-detected backend IP: ${ip}`);
        return `http://${ip}:8000`;
    }

    // Fallback for web or when detection fails
    if (Platform.OS === 'web') return 'http://localhost:8000';

    // Last resort – will likely fail on a real device but works in emulator
    console.warn('[API] Could not auto-detect IP. Falling back to 10.0.2.2 (Android emulator)');
    return 'http://10.0.2.2:8000';
}

const API_BASE = getApiBase();

// --- Helper: Generic Request Wrapper ---
async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    console.log(`[API] Request: ${options?.method || 'GET'} ${url}`);

    const headers = {
        ...options?.headers,
        'Bypass-Tunnel-Reminder': 'true', // Required for localtunnel
        'ngrok-skip-browser-warning': 'true', // Just in case
    };

    try {
        const res = await fetch(url, { ...options, headers });

        if (!res.ok) {
            let errorMessage = `API Error: ${res.status} ${res.statusText}`;
            try {
                const errorBody = await res.json();
                console.error(`[API] Error Body:`, errorBody);
                if (errorBody.detail) errorMessage += ` - ${errorBody.detail}`;
                if (errorBody.message) errorMessage += ` - ${errorBody.message}`;
            } catch (e) {
                // Could not parse error body
            }
            throw new Error(errorMessage);
        }

        // Handle 204 No Content
        if (res.status === 204) {
            return {} as T;
        }

        return res.json();
    } catch (error) {
        console.error(`[API] Network/Parse Error:`, error);
        throw error;
    }
}

// ─── Subjects ───
export const getSubjects = () => request<any[]>('/api/subjects/');

export const getSubjectDetail = (id: number) => request<any>(`/api/subjects/${id}`);

export const createSubject = (name: string, code: string) =>
    request<any>('/api/subjects/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, code })
    });

export const deleteSubject = (id: number) =>
    request<void>(`/api/subjects/${id}`, { method: 'DELETE' });

export const createUnit = (subjectId: number, name: string, unitNumber: number) =>
    request<any>(`/api/subjects/${subjectId}/units`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, unit_number: unitNumber })
    });

export const deleteUnit = (unitId: number) =>
    request<void>(`/api/units/${unitId}`, { method: 'DELETE' });

export const createTopic = (unitId: number, title: string) =>
    request<any>(`/api/units/${unitId}/topics`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title })
    });

export const deleteTopic = (topicId: number) =>
    request<void>(`/api/topics/${topicId}`, { method: 'DELETE' });

// ─── Materials ───
export const uploadMaterial = (subjectId: number, file: any, topicId?: number) => {
    const formData = new FormData();
    formData.append('file', file);
    if (topicId) {
        formData.append('topic_id', topicId.toString());
    }
    return request<any>(`/api/subjects/${subjectId}/upload-material`, {
        method: 'POST', body: formData
    });
};

export const getMaterials = (subjectId: number) =>
    request<any[]>(`/api/subjects/${subjectId}/materials`);

export const deleteMaterial = (materialId: number) =>
    request<void>(`/api/materials/${materialId}`, { method: 'DELETE' });

// ─── Topic Syllabus & Questions ───
export const updateTopicSyllabus = (topicId: number, syllabusData: any) =>
    request<any>(`/api/topics/${topicId}/syllabus`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ syllabus_data: syllabusData })
    });

export const createSampleQuestion = (topicId: number, data: { text: string; question_type: string; difficulty: string }) =>
    request<any>(`/api/topics/${topicId}/sample-questions`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });

export const getSampleQuestions = (topicId: number) =>
    request<any[]>(`/api/topics/${topicId}/sample-questions`);

export const deleteSampleQuestion = (sqId: number) =>
    request<void>(`/api/sample-questions/${sqId}`, { method: 'DELETE' });

// ─── OBE: Course Outcomes (Subject Level) ───
export const getCOs = (subjectId: number) =>
    request<any[]>(`/api/subjects/${subjectId}/cos`);

export const createCO = (subjectId: number, data: { description: string, code?: string, blooms_levels: string[] }) =>
    request<any>(`/api/subjects/${subjectId}/cos`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });

export const updateCO = (coId: number, data: any) =>
    request<any>(`/api/cos/${coId}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });

export const deleteCO = (coId: number) =>
    request<void>(`/api/cos/${coId}`, { method: 'DELETE' });

// ─── OBE: Learning Outcomes (Unit Level) ───
export const getLOs = (unitId: number) =>
    request<any[]>(`/api/units/${unitId}/los`);

export const createLO = (unitId: number, data: { description: string, code?: string }) =>
    request<any>(`/api/units/${unitId}/los`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });

export const updateLO = (loId: number, data: any) =>
    request<any>(`/api/los/${loId}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });

export const deleteLO = (loId: number) =>
    request<void>(`/api/los/${loId}`, { method: 'DELETE' });

// ─── OBE: Unit-CO Mapping ───
export const getUnitCOMapping = (unitId: number) =>
    request<any[]>(`/api/units/${unitId}/co-mapping`);

export const updateUnitCOMapping = (unitId: number, coIds: number[]) =>
    request<any>(`/api/units/${unitId}/co-mapping`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ co_ids: coIds })
    });

// ─── OBE: Bloom's Taxonomy (Topic Level) ───
export const getBlooms = (topicId: number) =>
    request<any>(`/api/topics/${topicId}/blooms`);

export const updateBlooms = (topicId: number, distribution: any) =>
    request<any>(`/api/topics/${topicId}/blooms`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(distribution) // distribution is { Knowledge: 10, ... }
    });

// ─── RAG ───
export const getRagStatus = (subjectId: number) =>
    request<any>(`/api/subjects/${subjectId}/rag-status`);

// ─── Rubrics ───
export const getRubrics = () => request<any[]>('/api/rubrics/');

export const createRubric = (data: any) =>
    request<any>('/api/rubrics/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });

export const deleteRubric = (id: number) =>
    request<void>(`/api/rubrics/${id}`, { method: 'DELETE' });

// ─── Generation ───
export const startGeneration = (rubricId: number, subjectId: number) =>
    request<any>('/api/generate/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rubric_id: rubricId, subject_id: subjectId })
    });

export const pollJob = (jobId: number) => request<any>(`/api/generate/job/${jobId}`);

export const getJobQuestions = (jobId: number) => request<any>(`/api/generate/job/${jobId}/questions`);

export const getOllamaStatus = () => request<any>('/api/generate/ollama-status');

// ─── Vetting ───
export const getVettingBatches = () =>
    request<any[]>('/api/vetting/batches');

export const getVettingQueue = (status: string = 'pending', jobId?: number) => {
    let url = `/api/vetting/queue?status=${status}`;
    if (jobId !== undefined) url += `&job_id=${jobId}`;
    return request<any[]>(url);
};

export const getQuestionDetail = (id: number) => request<any>(`/api/vetting/question/${id}`);

export const submitVetting = (data: any) =>
    request<any>('/api/vetting/submit', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });

// ─── Benchmarks ───
export const getBenchmarks = () => request<any[]>('/api/benchmarks/');

export const getJobBenchmarks = (jobId: number) => request<any>(`/api/benchmarks/job/${jobId}`);


export const exportBenchmarks = () => request<any>('/api/benchmarks/export');

// ─── Training & Dataset ───
export const getDatasetStats = (subjectId: number) =>
    request<any>(`/api/vetting/dataset/${subjectId}/stats`);

export const startTraining = (subjectId: number) =>
    request<any>(`/api/training/start/${subjectId}`, { method: 'POST' });

export const getTrainingStatus = (subjectId: number) =>
    request<any>(`/api/training/status/${subjectId}`);

export const getSkillContent = (subjectId: number) =>
    request<any>(`/api/training/skill/${subjectId}`);

