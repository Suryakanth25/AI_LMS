export interface Subject {
    id: string | number;
    code: string;
    name: string;
    description?: string;
    topicsCount?: number;
    questionsCount?: number;
    syllabusCoverage?: number; // 0-100
}

export interface Topic {
    id: string | number;
    subjectId: string | number; // Foreign key-ish
    title: string;
    syllabusUploaded: boolean;
    questionsCount: number;
    learningOutcomes?: string[];
}

export type QuestionType = 'mcq' | 'essay' | 'shortNotes' | 'MCQ' | 'Essay' | 'ShortValues' | 'ShortNotes'; // Updated to match usage

export interface Question {
    id: string | number;
    text: string;
    type?: QuestionType; // api returns question_type
    question_type?: QuestionType;
    options?: string[];
    correct?: string;
    correct_answer?: string;
    marks?: number;
    bloomsLevel?: string; // api: blooms_level
    blooms_level?: string;
    topicId?: string | number;
    status?: string;
    confidenceScore?: number; // 1-10
    confidence_score?: number; // raw from api
    generatedBy?: string;
    generated_by?: string;
}

export interface LearningOutcome {
    id: string;
    code: string; // e.g., "LO1"
    description: string;
}

export interface CognitiveLevel {
    id: string;
    name: string; // e.g., "Knowledge", "Comprehension"
    percentage: number;
    color: string; // Hex code
}

export interface Rubric {
    id: string | number;
    name: string;
    subjectId: string | number;
    questionTypeMap: {
        [key: string]: { count: number; marksEach: number };
    };
    difficulty: 'Easy' | 'Medium' | 'Hard' | 'medium';
    taxonomy: 'Bloom' | 'SOLO' | 'blooms';
}

export interface VettingItem {
    id: string | number;
    title?: string; // questions don't really have titles, maybe use text snippet
    text?: string;
    status: string;
    date?: string;
    questions?: number;
    subjectId?: string;
}

export interface ReportOverview {
    totalGenerated: number;
    totalApproved: number;
    totalRejected: number;
    totalPending: number;
    approvalRate: number;
    avgConfidence?: number;
}

export interface ReportData {
    overview: ReportOverview;
    learningOutcomes: {
        id: string;
        code: string;
        name: string;
        questionsCount: number;
        targetCount: number;
        color: string;
    }[];
    cognitiveLevels: {
        id: string;
        name: string;
        questionsCount: number;
        percentage: number;
        color: string;
    }[];
    syllabusCoverage: {
        topicName: string;
        coveragePercentage: number;
        questionsCount: number;
    }[];
    subjectsBreakdown: {
        name: string;
        questions: number;
        generated: number;
        vetted: number;
        color: string;
    }[];
}
