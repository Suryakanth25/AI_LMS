import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, TouchableOpacity, Alert, TextInput, ActivityIndicator, RefreshControl } from 'react-native';
import { ChevronDown, ChevronUp, Check, X, Pencil, ArrowLeft, Clock, FileText, BarChart3, CheckCircle, AlertCircle, Layers, History } from 'lucide-react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AppBackground } from '@/components/ui/AppBackground';
import { getVettingBatches, getVettingQueue, getQuestionDetail, submitVetting, getSubjectDetail } from '@/services/api';
import { useFocusEffect } from '@react-navigation/native';

// ── Utility: strip ALL markdown/special chars and return plain readable text ──
function cleanMarkdown(text: string): string {
    if (!text || typeof text !== 'string') return '';
    return text
        .replace(/```json/gi, '')
        .replace(/```/g, '')
        .replace(/^#{1,6}\s+/gm, '')
        .replace(/\*\*(.*?)\*\*/g, '$1')
        .replace(/^\s*[\*\-]\s+/gm, '• ')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}

function flattenToText(obj: any, depth: number = 0): string {
    if (obj === null || obj === undefined) return '';
    if (typeof obj === 'string') return obj;
    if (typeof obj === 'number' || typeof obj === 'boolean') return String(obj);
    const indent = '  '.repeat(depth);
    const lines: string[] = [];
    if (Array.isArray(obj)) {
        obj.forEach((item) => {
            if (typeof item === 'object' && item !== null) {
                lines.push(flattenToText(item, depth));
            } else {
                lines.push(`${indent}• ${String(item)}`);
            }
        });
    } else if (typeof obj === 'object') {
        for (const [key, value] of Object.entries(obj)) {
            const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            if (value && typeof value === 'object') {
                lines.push(`${indent}${label}:`);
                lines.push(flattenToText(value, depth + 1));
            } else {
                lines.push(`${indent}${label}: ${String(value ?? '')}`);
            }
        }
    }
    return lines.join('\n');
}

function extractQuestionTextFromAny(raw: any): string {
    if (!raw) return 'No question text';
    if (typeof raw === 'string') {
        const trimmed = raw.trim();
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
            try {
                const clean = trimmed.replace(/```json/gi, '').replace(/```/g, '').trim();
                const parsed = JSON.parse(clean);
                return extractQuestionTextFromAny(parsed);
            } catch (e) {
                const match1 = raw.match(/"question_text"\s*:\s*"([^"]+)"/);
                if (match1) return match1[1];
                const match2 = raw.match(/"question"\s*:\s*"([^"]+)"/);
                if (match2) return match2[1];
                const match3 = raw.match(/"text"\s*:\s*"([^"]+)"/);
                if (match3) return match3[1];
            }
        }
        return raw;
    }
    if (typeof raw === 'object' && raw !== null) {
        if (raw.question_text) return extractQuestionTextFromAny(raw.question_text);
        if (raw.question) return extractQuestionTextFromAny(raw.question);
        if (raw.text) return extractQuestionTextFromAny(raw.text);
        for (const key of ['json', 'response', 'selected_question', 'draft', 'result', 'output']) {
            if (raw[key]) return extractQuestionTextFromAny(raw[key]);
        }
        for (const key of ['MCQ', 'Short Notes', 'Essay']) {
            if (raw[key]) return extractQuestionTextFromAny(raw[key]);
        }
        try { return JSON.stringify(raw, null, 2); } catch { }
    }
    return String(raw);
}

function formatParsedJson(obj: any): string {
    if (!obj) return '';
    if (typeof obj === 'string') {
        try {
            const clean = obj.replace(/```json/gi, '').replace(/```/g, '').trim();
            if (clean.startsWith('{') || clean.startsWith('[')) {
                const parsed = JSON.parse(clean);
                if (typeof parsed === 'object') return formatParsedJson(parsed);
            }
        } catch (e) { }
        return obj;
    }
    if (obj.json) return formatParsedJson(obj.json);
    if (obj.response) return formatParsedJson(obj.response);
    if (obj.selected_question) {
        return "--- Selected Question ---\n" + formatParsedJson(obj.selected_question);
    }
    const keys = Object.keys(obj);
    if (keys.length === 1 && ['MCQ', 'Short Notes', 'Essay', 'draft'].includes(keys[0])) {
        return formatParsedJson(obj[keys[0]]);
    }
    const lines: string[] = [];
    const formatQuestion = (q: any) => {
        if (q.question_text || q.question) lines.push(`Question: ${q.question_text || q.question}`);
        if (q.topics) lines.push(`Topic: ${q.topics}`);
        if (q.type) lines.push(`Type: ${q.type}`);
        if (q.options) {
            lines.push('Options:');
            if (Array.isArray(q.options)) { q.options.forEach((opt: string) => lines.push(`  - ${opt}`)); }
            else { lines.push(`  ${String(q.options)}`); }
        }
        if (q.correct_answer) lines.push(`Correct Answer: ${q.correct_answer}`);
        if (q.explanation) lines.push(`Explanation: ${q.explanation}`);
        if (q.key_points) {
            lines.push('Key Points:');
            if (Array.isArray(q.key_points)) { q.key_points.forEach((k: string) => lines.push(`  - ${k}`)); }
            else { lines.push(`  ${String(q.key_points)}`); }
        }
        if (q.expected_structure) {
            lines.push('Expected Structure:');
            if (Array.isArray(q.expected_structure)) { q.expected_structure.forEach((s: string) => lines.push(`  - ${typeof s === 'object' ? JSON.stringify(s) : s}`)); }
            else { lines.push(`  ${String(q.expected_structure)}`); }
        }
        if (q.marks) lines.push(`Marks: ${q.marks}`);
        if (q.word_limit) lines.push(`Word Limit: ${q.word_limit}`);
    };
    const isQuestionLike = obj.question_text || obj.question || obj.key_points || obj.expected_structure || obj.options || obj.explanation || obj.correct_answer;
    if (isQuestionLike) { formatQuestion(obj); }
    for (const [key, value] of Object.entries(obj)) {
        if (isQuestionLike && ['selected_question', 'json', 'response', 'question_text', 'question', 'topics', 'type', 'options', 'correct_answer', 'explanation', 'key_points', 'expected_structure', 'marks', 'word_limit', 'timings', 'models_used'].includes(key)) continue;
        if (['timings', 'models_used', 'selected_from'].includes(key)) continue;
        const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        if (key === 'improved_version_text' || key === 'improved_version') {
            lines.push(`\nImproved Version:\n${String(value)}\n`);
        } else if (key === 'reasoning') {
            lines.push(`\nReasoning:\n${String(value)}\n`);
        } else if (key === 'issues' && Array.isArray(value)) {
            lines.push(`\nIssues Identified:`);
            value.forEach((issue: any) => lines.push(`  - ${String(issue)}`));
        } else if (key === 'factually_grounded') {
            lines.push(`Factually Grounded: ${value ? 'Yes' : 'No'}`);
        } else if (key === 'score') {
            lines.push(`Score: ${value}/10`);
        } else if (value && typeof value === 'object' && !Array.isArray(value)) {
            lines.push(`\n${label}:`);
            lines.push(formatParsedJson(value));
        } else if (Array.isArray(value)) {
            lines.push(`${label}:`);
            value.forEach((item: any) => {
                if (typeof item === 'object') { lines.push(formatParsedJson(item)); }
                else { lines.push(`  - ${String(item)}`); }
            });
        } else {
            lines.push(`${label}: ${String(value ?? '')}`);
        }
    }
    return lines.join('\n').trim();
}

function extractReadableText(raw: any): string {
    if (!raw) return 'No data available';
    let str = typeof raw === 'string' ? raw : JSON.stringify(raw);
    let cleaned = str.replace(/```json/gi, '').replace(/```/g, '').trim();
    try {
        const parsed = JSON.parse(cleaned);
        return formatParsedJson(parsed);
    } catch (e) {
        const start = cleaned.indexOf('{');
        const end = cleaned.lastIndexOf('}');
        if (start !== -1 && end !== -1 && end > start) {
            try {
                const potentialJson = cleaned.substring(start, end + 1);
                const parsed = JSON.parse(potentialJson);
                return formatParsedJson(parsed);
            } catch (e2) { }
        }
    }
    const patterns = {
        question_text: /"question_text"\s*:\s*"([^"]+)"/,
        improved_version: /"improved_version_text"\s*:\s*"([^"]+)"/,
        reasoning: /"reasoning"\s*:\s*"([^"]+)"/,
        issues: /"issues"\s*:\s*\[(.*?)\]/
    };
    let fallback = "";
    const qt = cleaned.match(patterns.question_text);
    if (qt) fallback += `Question Text: ${qt[1]}\n`;
    const iv = cleaned.match(patterns.improved_version);
    if (iv) fallback += `\nImproved Version:\n${iv[1]}\n`;
    const re = cleaned.match(patterns.reasoning);
    if (re) fallback += `\nReasoning:\n${re[1]}\n`;
    const is = cleaned.match(patterns.issues);
    if (is) {
        fallback += `\nIssues Identified:\n${is[1].replace(/"/g, '').split(',').map(i => `  - ${i.trim()}`).join('\n')}`;
    }
    if (fallback) return fallback;
    return cleaned;
}

function formatTimeAgo(isoString: string | null): string {
    if (!isoString) return '';
    const diff = Date.now() - new Date(isoString).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
}


// ═══════════════════════════════════════════════
// BATCH LIST VIEW
// ═══════════════════════════════════════════════
function BatchListView({ onSelectBatch }: { onSelectBatch: (batch: any) => void }) {
    const [batches, setBatches] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [activeTab, setActiveTab] = useState<'active' | 'history'>('active');

    const fetchBatches = async () => {
        try {
            const data = await getVettingBatches();
            setBatches(data);
        } catch (e) { } finally { setLoading(false); setRefreshing(false); }
    };

    useFocusEffect(useCallback(() => { fetchBatches(); }, []));

    const activeBatches = batches.filter(b => b.progress < 100);
    const historyBatches = batches.filter(b => b.progress === 100);

    if (loading) {
        return (
            <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
                <ActivityIndicator size="large" color="#16A34A" />
            </View>
        );
    }

    const displayBatches = activeTab === 'active' ? activeBatches : historyBatches;

    return (
        <ScrollView
            style={{ flex: 1, paddingHorizontal: 16, paddingTop: 16 }}
            contentContainerStyle={{ paddingBottom: 100 }}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchBatches(); }} />}
        >
            {/* Tab Switcher */}
            <View style={{
                flexDirection: 'row',
                backgroundColor: '#F3F4F6',
                borderRadius: 12,
                padding: 4,
                marginBottom: 20,
            }}>
                <TouchableOpacity
                    onPress={() => setActiveTab('active')}
                    style={{
                        flex: 1,
                        flexDirection: 'row',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 6,
                        paddingVertical: 10,
                        borderRadius: 10,
                        backgroundColor: activeTab === 'active' ? 'white' : 'transparent',
                        shadowColor: activeTab === 'active' ? '#000' : 'transparent',
                        shadowOpacity: activeTab === 'active' ? 0.06 : 0,
                        shadowRadius: 4,
                        elevation: activeTab === 'active' ? 2 : 0,
                    }}
                >
                    <Layers size={15} color={activeTab === 'active' ? '#16A34A' : '#9CA3AF'} />
                    <Text style={{
                        fontSize: 13,
                        fontWeight: 'bold',
                        color: activeTab === 'active' ? '#16A34A' : '#9CA3AF',
                    }}>
                        Active ({activeBatches.length})
                    </Text>
                </TouchableOpacity>

                <TouchableOpacity
                    onPress={() => setActiveTab('history')}
                    style={{
                        flex: 1,
                        flexDirection: 'row',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 6,
                        paddingVertical: 10,
                        borderRadius: 10,
                        backgroundColor: activeTab === 'history' ? 'white' : 'transparent',
                        shadowColor: activeTab === 'history' ? '#000' : 'transparent',
                        shadowOpacity: activeTab === 'history' ? 0.06 : 0,
                        shadowRadius: 4,
                        elevation: activeTab === 'history' ? 2 : 0,
                    }}
                >
                    <History size={15} color={activeTab === 'history' ? '#3B82F6' : '#9CA3AF'} />
                    <Text style={{
                        fontSize: 13,
                        fontWeight: 'bold',
                        color: activeTab === 'history' ? '#3B82F6' : '#9CA3AF',
                    }}>
                        History ({historyBatches.length})
                    </Text>
                </TouchableOpacity>
            </View>

            {/* Batch List */}
            {displayBatches.length === 0 ? (
                <View style={{ alignItems: 'center', justifyContent: 'center', paddingVertical: 60 }}>
                    {activeTab === 'active' ? (
                        <>
                            <Layers size={48} color="#D1D5DB" />
                            <Text style={{ color: '#4B5563', fontWeight: 'bold', fontSize: 16, marginTop: 16 }}>No Active Batches</Text>
                            <Text style={{ color: '#9CA3AF', marginTop: 4, fontSize: 13 }}>Generate questions to create batches</Text>
                        </>
                    ) : (
                        <>
                            <History size={48} color="#D1D5DB" />
                            <Text style={{ color: '#4B5563', fontWeight: 'bold', fontSize: 16, marginTop: 16 }}>No History Yet</Text>
                            <Text style={{ color: '#9CA3AF', marginTop: 4, fontSize: 13 }}>Completed batches will appear here</Text>
                        </>
                    )}
                </View>
            ) : (
                displayBatches.map((batch, i) => (
                    <Animated.View key={batch.job_id} entering={FadeInDown.delay(i * 60)}>
                        <TouchableOpacity
                            onPress={() => onSelectBatch(batch)}
                            style={{
                                backgroundColor: 'white',
                                borderRadius: 16,
                                padding: 16,
                                marginBottom: 12,
                                borderWidth: 1,
                                borderColor: '#E5E7EB',
                                shadowColor: '#000', shadowOpacity: 0.04, shadowRadius: 8, shadowOffset: { width: 0, height: 2 },
                                elevation: 2,
                            }}
                        >
                            {/* Top Row: Subject + Time */}
                            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                                <View style={{ flex: 1, marginRight: 8 }}>
                                    <Text style={{ color: '#111827', fontWeight: 'bold', fontSize: 15 }} numberOfLines={1}>
                                        {batch.subject_name}
                                    </Text>
                                    <Text style={{ color: '#6B7280', fontSize: 12, marginTop: 2 }} numberOfLines={1}>
                                        {batch.rubric_name}
                                    </Text>
                                </View>
                                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, opacity: 0.6 }}>
                                    <Clock size={12} color="#9CA3AF" />
                                    <Text style={{ color: '#9CA3AF', fontSize: 11 }}>{formatTimeAgo(batch.created_at)}</Text>
                                </View>
                            </View>

                            {/* Stats Row */}
                            <View style={{ flexDirection: 'row', gap: 8, marginBottom: 10 }}>
                                <View style={{ backgroundColor: '#F3F4F6', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                                    <FileText size={12} color="#6B7280" />
                                    <Text style={{ color: '#4B5563', fontSize: 11, fontWeight: '600' }}>{batch.total_questions} Qs</Text>
                                </View>
                                <View style={{ backgroundColor: batch.pending_count > 0 ? '#FEF3C7' : '#DCFCE7', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                                    {batch.pending_count > 0
                                        ? <AlertCircle size={12} color="#92400E" />
                                        : <CheckCircle size={12} color="#166534" />
                                    }
                                    <Text style={{ color: batch.pending_count > 0 ? '#92400E' : '#166534', fontSize: 11, fontWeight: '600' }}>
                                        {batch.pending_count > 0 ? `${batch.pending_count} Pending` : 'Completed'}
                                    </Text>
                                </View>
                                <View style={{ backgroundColor: '#EFF6FF', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                                    <BarChart3 size={12} color="#2563EB" />
                                    <Text style={{ color: '#2563EB', fontSize: 11, fontWeight: '600' }}>{batch.vetted_count}/{batch.total_questions}</Text>
                                </View>
                            </View>

                            {/* Progress Bar */}
                            <View style={{ height: 6, backgroundColor: '#F3F4F6', borderRadius: 3, overflow: 'hidden' }}>
                                <View
                                    style={{
                                        width: `${batch.progress}%`,
                                        height: '100%',
                                        backgroundColor: batch.progress === 100 ? '#16A34A' : '#3B82F6',
                                        borderRadius: 3,
                                    }}
                                />
                            </View>
                            <Text style={{ color: '#9CA3AF', fontSize: 10, marginTop: 4, textAlign: 'right' }}>
                                {batch.progress}% vetted
                            </Text>
                        </TouchableOpacity>
                    </Animated.View>
                ))
            )}
        </ScrollView>
    );
}


// ═══════════════════════════════════════════════
// QUESTION REVIEW VIEW (scoped to a batch)
// ═══════════════════════════════════════════════
function QuestionReviewView({ batch, onBack }: { batch: any; onBack: () => void }) {
    const isHistory = batch.progress === 100;
    const [queue, setQueue] = useState<any[]>([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [feedback, setFeedback] = useState('');
    const [action, setAction] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [showCouncil, setShowCouncil] = useState(false);
    const [detail, setDetail] = useState<any>(null);
    const [expandedAgent, setExpandedAgent] = useState<string | null>(null);
    const [allReviewed, setAllReviewed] = useState(false);

    const [coList, setCoList] = useState<any[]>([]);
    const [selectedCos, setSelectedCos] = useState<number[]>([]);
    const [coLevels, setCoLevels] = useState<{ [key: number]: string }>({});
    const [bloomsLevel, setBloomsLevel] = useState<string | null>(null);
    const [rejectionReason, setRejectionReason] = useState<string | null>(null);

    const fetchQueue = async () => {
        try {
            // For history batches, fetch approved+rejected questions.
            // For active batches, fetch only pending questions.
            if (isHistory) {
                const approved = await getVettingQueue('approved', batch.job_id);
                const rejected = await getVettingQueue('rejected', batch.job_id);
                const all = [...approved, ...rejected];
                setQueue(all);
                setCurrentIndex(0);
                setAllReviewed(false);
            } else {
                const data = await getVettingQueue('pending', batch.job_id);
                setQueue(data);
                setCurrentIndex(0);
                setAllReviewed(data.length === 0);
            }
        } catch (e) { } finally { setLoading(false); setRefreshing(false); }
    };

    useEffect(() => { fetchQueue(); }, [batch.job_id]);

    const current = queue[currentIndex];

    useEffect(() => {
        if (batch.subject_id) {
            getSubjectDetail(batch.subject_id).then(sub => {
                if (sub && sub.course_outcomes) setCoList(sub.course_outcomes);
            }).catch(() => { });
        }
        setSelectedCos([]);
        setCoLevels({});
        setBloomsLevel(null);
        setRejectionReason(null);
        setFeedback('');
        setAction(null);
        setDetail(null);
    }, [current]);

    const display = current ? {
        text: current.text || current.question_text || current.question || 'No question text',
        explanation: current.explanation,
        options: current.options,
        answer: current.correct_answer,
    } : null;

    const loadDetail = async () => {
        if (!current) return;
        try {
            const data = await getQuestionDetail(current.id);
            setDetail(data);
        } catch (e) { console.error("Failed to load details", e); }
    };

    const toggleCo = (id: number) => {
        if (selectedCos.includes(id)) {
            setSelectedCos(prev => prev.filter(c => c !== id));
            const newLevels = { ...coLevels }; delete newLevels[id]; setCoLevels(newLevels);
        } else {
            setSelectedCos(prev => [...prev, id]);
            setCoLevels(prev => ({ ...prev, [id]: 'moderate' }));
        }
    };

    const setLevel = (id: number, level: string) => {
        if (!selectedCos.includes(id)) return;
        setCoLevels(prev => ({ ...prev, [id]: level }));
    };

    const rejectionReasons = [
        "Incorrect Concept", "Out of Syllabus", "Too Complex",
        "Too Simple", "Grammar/Language Issues", "Duplicate Question", "Other"
    ];

    const handleSubmit = async () => {
        if (!action) { Alert.alert('Select Action', 'Choose Approve, Reject, or Edit'); return; }
        if (selectedCos.length === 0) {
            Alert.alert('Validation Error', 'You must map this question to at least one Course Outcome (CO) before submitting.');
            return;
        }
        if (action === 'reject') {
            if (!rejectionReason) { Alert.alert('Validation Error', 'Please select a Rejection Reason.'); return; }
            if (!feedback || feedback.length < 5) { Alert.alert('Validation Error', 'Please provide constructive feedback for rejection.'); return; }
        }
        setSubmitting(true);
        try {
            await submitVetting({
                question_id: current.id,
                action: action === 'approve' ? 'approved' : action === 'reject' ? 'rejected' : 'edited',
                co_mappings: selectedCos,
                co_mapping_levels: Object.entries(coLevels).reduce((acc: any, [k, v]) => { acc[String(k)] = v; return acc; }, {}),
                blooms_level: bloomsLevel,
                faculty_feedback: feedback.trim() || undefined,
                rejection_reason: rejectionReason,
                edited_text: action === 'edit' ? feedback : undefined,
                reviewed_by: "Faculty User"
            });
            setFeedback(''); setAction(null); setRejectionReason(null);
            setShowCouncil(false); setDetail(null); setExpandedAgent(null);
            setSelectedCos([]); setCoLevels({});
            if (currentIndex < queue.length - 1) {
                const newQueue = [...queue]; newQueue.splice(currentIndex, 1); setQueue(newQueue);
            } else {
                const newQueue = queue.filter((_, i) => i !== currentIndex);
                setQueue(newQueue);
                if (newQueue.length === 0) setAllReviewed(true);
                else setCurrentIndex(Math.max(0, currentIndex - 1));
            }
            Alert.alert('Success', 'Question vetted and saved to dataset.');
        } catch (e: any) {
            Alert.alert('Error', e.message || 'Failed to submit');
        } finally { setSubmitting(false); }
    };

    const getConfidenceColor = (score: number) => {
        if (score >= 7) return { bg: 'bg-green-100', border: 'border-green-300', text: 'text-green-700' };
        if (score >= 4) return { bg: 'bg-yellow-100', border: 'border-yellow-300', text: 'text-yellow-700' };
        return { bg: 'bg-red-100', border: 'border-red-300', text: 'text-red-700' };
    };

    const getAgentField = (key: string) => {
        switch (key) {
            case 'agent_a': return 'agent_a_draft';
            case 'agent_b': return 'agent_b_review';
            case 'agent_c': return 'agent_c_draft';
            case 'chairman': return 'chairman_output';
            default: return key;
        }
    };

    if (loading) {
        return (
            <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
                <ActivityIndicator size="large" color="#16A34A" />
            </View>
        );
    }

    return (
        <ScrollView
            style={{ flex: 1, paddingHorizontal: 16, paddingTop: 8 }}
            contentContainerStyle={{ paddingBottom: 100 }}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchQueue(); }} />}
        >
            {/* Back Button */}
            <TouchableOpacity
                onPress={onBack}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 12, paddingVertical: 4 }}
            >
                <ArrowLeft size={18} color="#3B82F6" />
                <Text style={{ color: '#3B82F6', fontSize: 13, fontWeight: '600' }}>Back to Batches</Text>
            </TouchableOpacity>

            {/* Batch Info Banner */}
            <View style={{ backgroundColor: '#EFF6FF', borderRadius: 12, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: '#DBEAFE' }}>
                <Text style={{ color: '#1E40AF', fontWeight: 'bold', fontSize: 14 }}>{batch.subject_name}</Text>
                <Text style={{ color: '#3B82F6', fontSize: 11, marginTop: 2 }}>
                    {batch.rubric_name} {isHistory ? `- ${batch.total_questions} reviewed` : `- ${queue.length} pending of ${batch.total_questions}`}
                </Text>
            </View>

            {/* History read-only indicator */}
            {isHistory && queue.length > 0 && (
                <View style={{ backgroundColor: '#F0FDF4', borderRadius: 10, padding: 10, marginBottom: 12, flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1, borderColor: '#BBF7D0' }}>
                    <CheckCircle size={16} color="#16A34A" />
                    <Text style={{ color: '#166534', fontSize: 12, fontWeight: '600' }}>Read-only - This batch is fully vetted</Text>
                </View>
            )}

            {!isHistory && (allReviewed || queue.length === 0) ? (
                <View style={{ alignItems: 'center', justifyContent: 'center', paddingVertical: 80 }}>
                    <CheckCircle size={48} color="#D1D5DB" />
                    <Text style={{ color: '#4B5563', fontWeight: 'bold', fontSize: 18, marginTop: 16 }}>All Questions Reviewed</Text>
                    <Text style={{ color: '#9CA3AF', marginTop: 4, fontSize: 13 }}>This batch is fully vetted.</Text>
                    <TouchableOpacity onPress={onBack} style={{ marginTop: 16, backgroundColor: '#3B82F6', paddingHorizontal: 20, paddingVertical: 10, borderRadius: 10 }}>
                        <Text style={{ color: 'white', fontWeight: 'bold', fontSize: 13 }}>Back to Batches</Text>
                    </TouchableOpacity>
                </View>
            ) : queue.length === 0 ? (
                <View style={{ alignItems: 'center', justifyContent: 'center', paddingVertical: 80 }}>
                    <AlertCircle size={48} color="#D1D5DB" />
                    <Text style={{ color: '#4B5563', fontWeight: 'bold', fontSize: 16, marginTop: 16 }}>No Questions Found</Text>
                    <Text style={{ color: '#9CA3AF', marginTop: 4, fontSize: 13 }}>This batch has no questions to display.</Text>
                </View>
            ) : display && (
                <Animated.View entering={FadeInDown}>
                    {/* Progress bar */}
                    <View className="h-2 bg-gray-200 rounded-full overflow-hidden mb-4">
                        <View style={{ width: `${((currentIndex + 1) / queue.length) * 100}%` }}
                            className="h-full bg-green-500 rounded-full" />
                    </View>

                    {/* Status badge for history items */}
                    {isHistory && current.status && (
                        <View style={{ flexDirection: 'row', justifyContent: 'center', marginBottom: 8 }}>
                            <View style={{
                                flexDirection: 'row', alignItems: 'center', gap: 6,
                                backgroundColor: current.status === 'approved' ? '#F0FDF4' : '#FEF2F2',
                                borderWidth: 1,
                                borderColor: current.status === 'approved' ? '#BBF7D0' : '#FECACA',
                                paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8,
                            }}>
                                {current.status === 'approved'
                                    ? <CheckCircle size={14} color="#16A34A" />
                                    : <X size={14} color="#EF4444" />
                                }
                                <Text style={{ fontSize: 12, fontWeight: 'bold', color: current.status === 'approved' ? '#166534' : '#991B1B' }}>
                                    {current.status === 'approved' ? 'Approved' : 'Rejected'}
                                </Text>
                            </View>
                        </View>
                    )}

                    {/* Confidence Badge */}
                    {(() => {
                        const c = getConfidenceColor(current.confidence_score || 0);
                        return (
                            <View className={`items-center mb-4 p-4 rounded-2xl ${c.bg} border ${c.border}`}>
                                <View className={`w-16 h-16 rounded-full items-center justify-center ${c.bg} border-2 ${c.border}`}>
                                    <Text className={`font-bold text-xl ${c.text}`}>{(current.confidence_score || 0).toFixed(1)}</Text>
                                </View>
                                <Text className="text-gray-600 text-xs mt-2 font-bold">Confidence Score</Text>
                                {current.selected_from && (
                                    <Text className="text-gray-400 text-xs mt-0.5">Selected from: {current.selected_from}</Text>
                                )}
                            </View>
                        );
                    })()}

                    {/* Badges row */}
                    <View className="flex-row gap-2 mb-4 justify-center">
                        <View className="bg-purple-100 px-3 py-1 rounded-full">
                            <Text className="text-purple-700 font-bold text-xs">{current.question_type}</Text>
                        </View>
                        <View className="bg-blue-100 px-3 py-1 rounded-full">
                            <Text className="text-blue-700 font-bold text-xs">{(current.generation_time_seconds || 0).toFixed(1)}s</Text>
                        </View>
                        <View className="bg-gray-100 px-3 py-1 rounded-full">
                            <Text className="text-gray-700 font-bold text-xs">{current.marks || 0} marks</Text>
                        </View>
                    </View>

                    {/* Question Card */}
                    <View className="bg-white rounded-xl border border-gray-100 p-4 mb-4 shadow-sm">
                        <Text className="text-gray-800 text-base leading-6 font-medium">
                            {extractQuestionTextFromAny(display?.text)}
                        </Text>
                        {display.explanation ? (
                            <View className="mt-2 bg-blue-50 p-2 rounded-lg">
                                <Text className="text-blue-800 text-xs italic">{display.explanation}</Text>
                            </View>
                        ) : null}
                        {display.options && Array.isArray(display.options) && (
                            <View className="mt-3 gap-2">
                                {display.options.map((opt: string, i: number) => {
                                    const isCorrect = display.answer && opt.startsWith(display.answer);
                                    return (
                                        <View key={i} className={`px-3 py-2 rounded-lg border ${isCorrect ? 'bg-green-50 border-green-300' : 'bg-gray-50 border-gray-200'}`}>
                                            <Text className={`text-sm ${isCorrect ? 'text-green-700 font-bold' : 'text-gray-700'}`}>{opt}</Text>
                                        </View>
                                    );
                                })}
                                {display.answer && <Text className="text-green-600 font-bold text-xs mt-1">Correct: {display.answer}</Text>}
                            </View>
                        )}
                    </View>

                    {/* Council Deliberation */}
                    <TouchableOpacity
                        onPress={() => { setShowCouncil(!showCouncil); if (!showCouncil && !detail) loadDetail(); }}
                        className="flex-row items-center justify-between bg-white rounded-xl border border-gray-100 p-4 mb-4"
                    >
                        <Text className="font-bold text-gray-800 text-sm">View Council Deliberation</Text>
                        {showCouncil ? <ChevronUp size={18} color="#9CA3AF" /> : <ChevronDown size={18} color="#9CA3AF" />}
                    </TouchableOpacity>

                    {showCouncil && detail && (
                        <View className="mb-4">
                            {[
                                { key: 'agent_a', label: 'Agent A (Logician) Draft', color: 'blue' },
                                { key: 'agent_b', label: 'Agent B (Creative) Review', color: 'purple' },
                                { key: 'agent_c', label: 'Agent C (Technician) Draft', color: 'cyan' },
                                { key: 'chairman', label: 'Chairman Decision', color: 'green' },
                            ].map(agent => (
                                <View key={agent.key} className="mb-2">
                                    <TouchableOpacity
                                        onPress={() => setExpandedAgent(expandedAgent === agent.key ? null : agent.key)}
                                        className="flex-row items-center justify-between bg-gray-50 p-3 rounded-lg"
                                    >
                                        <Text className="text-gray-700 font-medium text-xs">{agent.label}</Text>
                                        {expandedAgent === agent.key
                                            ? <ChevronUp size={14} color="#9CA3AF" />
                                            : <ChevronDown size={14} color="#9CA3AF" />}
                                    </TouchableOpacity>
                                    {expandedAgent === agent.key && (
                                        <View className="bg-white border border-gray-100 p-3 rounded-b-lg">
                                            <Text className="text-gray-600 text-xs leading-5">
                                                {extractReadableText(detail[getAgentField(agent.key)])}
                                            </Text>
                                        </View>
                                    )}
                                </View>
                            ))}
                            {detail.rag_context_used && (
                                <View className="mb-2">
                                    <TouchableOpacity
                                        onPress={() => setExpandedAgent(expandedAgent === 'rag' ? null : 'rag')}
                                        className="flex-row items-center justify-between bg-gray-50 p-3 rounded-lg"
                                    >
                                        <Text className="text-gray-700 font-medium text-xs">RAG Context</Text>
                                        {expandedAgent === 'rag' ? <ChevronUp size={14} color="#9CA3AF" /> : <ChevronDown size={14} color="#9CA3AF" />}
                                    </TouchableOpacity>
                                    {expandedAgent === 'rag' && (
                                        <ScrollView className="bg-white border border-gray-100 p-3 rounded-b-lg max-h-96">
                                            <Text className="text-gray-500 text-xs">{detail.rag_context_used}</Text>
                                        </ScrollView>
                                    )}
                                </View>
                            )}
                        </View>
                    )}

                    {/* Only show vetting controls if NOT history */}
                    {!isHistory && (
                        <>
                            {/* CO Mapping Section */}
                            {coList.length > 0 && (
                                <View className="mb-4 bg-white rounded-xl border border-gray-100 p-4">
                                    <Text className="font-bold text-gray-800 text-sm mb-3">Map Course Outcomes (COs)</Text>
                                    <View className="flex-row flex-wrap gap-2">
                                        {coList.map((co) => {
                                            const isSelected = selectedCos.includes(co.id);
                                            const level = coLevels[co.id];
                                            return (
                                                <TouchableOpacity
                                                    key={co.id}
                                                    onPress={() => toggleCo(co.id)}
                                                    className={`px-3 py-2 rounded-lg border ${isSelected ? 'bg-blue-50 border-blue-300' : 'bg-gray-50 border-gray-200'}`}
                                                >
                                                    <View className="flex-row items-center gap-2">
                                                        <Text className={`text-xs font-bold ${isSelected ? 'text-blue-700' : 'text-gray-600'}`}>
                                                            {co.code}
                                                        </Text>
                                                        {isSelected && (
                                                            <View className="bg-blue-200 px-1.5 py-0.5 rounded">
                                                                <Text className="text-[10px] text-blue-800 font-bold">
                                                                    {level === 'high' ? 'H' : level === 'low' ? 'L' : 'M'}
                                                                </Text>
                                                            </View>
                                                        )}
                                                    </View>
                                                </TouchableOpacity>
                                            );
                                        })}
                                    </View>
                                    {selectedCos.length > 0 && (
                                        <View className="mt-3 pt-3 border-t border-gray-100">
                                            <Text className="text-xs text-gray-400 mb-2">Adjust Level (Low/Mod/High)</Text>
                                            {coList.filter(c => selectedCos.includes(c.id)).map(co => (
                                                <View key={co.id} className="flex-row items-center justify-between mb-2">
                                                    <Text className="text-xs text-gray-700 font-medium flex-1 mr-2">{co.code}</Text>
                                                    <View className="flex-row gap-1">
                                                        {['low', 'moderate', 'high'].map((l) => (
                                                            <TouchableOpacity
                                                                key={l}
                                                                onPress={() => setLevel(co.id, l)}
                                                                className={`px-2 py-1 rounded border ${coLevels[co.id] === l ? 'bg-blue-600 border-blue-600' : 'bg-white border-gray-200'}`}
                                                            >
                                                                <Text className={`text-[10px] ${coLevels[co.id] === l ? 'text-white' : 'text-gray-500'}`}>
                                                                    {l.charAt(0).toUpperCase()}
                                                                </Text>
                                                            </TouchableOpacity>
                                                        ))}
                                                    </View>
                                                </View>
                                            ))}
                                        </View>
                                    )}
                                </View>
                            )}

                            {/* Rejection Reason */}
                            {action === 'reject' && (
                                <View className="mb-4 bg-red-50 rounded-xl border border-red-100 p-4">
                                    <Text className="font-bold text-red-800 text-sm mb-3">Rejection Reason</Text>
                                    <View className="flex-row flex-wrap gap-2">
                                        {rejectionReasons.map((r) => (
                                            <TouchableOpacity
                                                key={r}
                                                onPress={() => setRejectionReason(r)}
                                                className={`px-3 py-2 rounded-lg border ${rejectionReason === r ? 'bg-red-200 border-red-400' : 'bg-white border-red-100'}`}
                                            >
                                                <Text className={`text-xs ${rejectionReason === r ? 'text-red-800 font-bold' : 'text-red-500'}`}>{r}</Text>
                                            </TouchableOpacity>
                                        ))}
                                    </View>
                                </View>
                            )}

                            {/* Feedback */}
                            <TextInput
                                placeholder="Faculty feedback (optional)"
                                value={feedback}
                                onChangeText={setFeedback}
                                className="bg-white border border-gray-200 rounded-xl px-4 py-3 mb-4 text-gray-800"
                                placeholderTextColor="#9CA3AF"
                                multiline
                            />

                            {/* Action Buttons */}
                            <View className="flex-row gap-3 mb-3">
                                <TouchableOpacity onPress={() => setAction('reject')} className={`flex-1 py-3 rounded-xl items-center border-2 ${action === 'reject' ? 'bg-red-500 border-red-500' : 'bg-white border-red-200'}`}>
                                    <X size={18} color={action === 'reject' ? 'white' : '#EF4444'} />
                                    <Text className={`font-bold text-xs mt-1 ${action === 'reject' ? 'text-white' : 'text-red-500'}`}>Reject</Text>
                                </TouchableOpacity>
                                <TouchableOpacity onPress={() => setAction('edit')} className={`flex-1 py-3 rounded-xl items-center border-2 ${action === 'edit' ? 'bg-gray-500 border-gray-500' : 'bg-white border-gray-200'}`}>
                                    <Pencil size={18} color={action === 'edit' ? 'white' : '#6B7280'} />
                                    <Text className={`font-bold text-xs mt-1 ${action === 'edit' ? 'text-white' : 'text-gray-500'}`}>Edit</Text>
                                </TouchableOpacity>
                                <TouchableOpacity onPress={() => setAction('approve')} className={`flex-1 py-3 rounded-xl items-center border-2 ${action === 'approve' ? 'bg-green-500 border-green-500' : 'bg-white border-green-200'}`}>
                                    <Check size={18} color={action === 'approve' ? 'white' : '#16A34A'} />
                                    <Text className={`font-bold text-xs mt-1 ${action === 'approve' ? 'text-white' : 'text-green-600'}`}>Approve</Text>
                                </TouchableOpacity>
                            </View>

                            <TouchableOpacity onPress={handleSubmit} disabled={submitting || !action}>
                                <LinearGradient
                                    colors={!action ? ['#d1d5db', '#9ca3af'] : action === 'approve' ? ['#4ade80', '#16A34A'] : action === 'reject' ? ['#f87171', '#DC2626'] : ['#5eb0e5', '#3a8cc7']}
                                    style={{ borderRadius: 16 }} className="py-4 items-center mb-3"
                                >
                                    {submitting ? <ActivityIndicator color="white" /> : <Text className="text-white font-bold text-base">Submit & Next</Text>}
                                </LinearGradient>
                            </TouchableOpacity>
                        </>
                    )}

                    {/* Navigation */}
                    <View className="flex-row gap-3">
                        <TouchableOpacity
                            onPress={() => { if (currentIndex > 0) { setCurrentIndex(currentIndex - 1); setShowCouncil(false); setDetail(null); setExpandedAgent(null); } }}
                            disabled={currentIndex === 0}
                            className={`flex-1 py-3 rounded-xl items-center border border-gray-200 ${currentIndex === 0 ? 'opacity-30' : 'bg-white'}`}
                        >
                            <Text className="text-gray-600 font-bold text-sm">Previous</Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                            onPress={() => { if (currentIndex < queue.length - 1) { setCurrentIndex(currentIndex + 1); setShowCouncil(false); setDetail(null); setExpandedAgent(null); } }}
                            disabled={currentIndex >= queue.length - 1}
                            className={`flex-1 py-3 rounded-xl items-center border border-gray-200 ${currentIndex >= queue.length - 1 ? 'opacity-30' : 'bg-white'}`}
                        >
                            <Text className="text-gray-600 font-bold text-sm">Next</Text>
                        </TouchableOpacity>
                    </View>
                </Animated.View>
            )}
        </ScrollView>
    );
}


// ═══════════════════════════════════════════════
// MAIN VETTING SCREEN
// ═══════════════════════════════════════════════
export default function VettingScreen() {
    const [selectedBatch, setSelectedBatch] = useState<any>(null);

    return (
        <AppBackground>
            <LinearGradient colors={['#8fd36a', '#5cb82a']} style={{ paddingTop: 48, paddingBottom: 24, paddingHorizontal: 24, borderBottomLeftRadius: 24, borderBottomRightRadius: 24, zIndex: 10 }}>
                <SafeAreaView edges={['top']}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                        <View>
                            <Text style={{ color: 'white', fontSize: 20, fontWeight: 'bold' }}>
                                {selectedBatch ? 'Review Questions' : 'Vetting'}
                            </Text>
                            <Text style={{ color: 'rgba(255,255,255,0.8)', fontSize: 13 }}>
                                {selectedBatch ? selectedBatch.subject_name : 'Review generated question batches'}
                            </Text>
                        </View>
                        {selectedBatch && (
                            <View style={{ backgroundColor: 'rgba(255,255,255,0.2)', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999 }}>
                                <Text style={{ color: 'white', fontWeight: 'bold', fontSize: 12 }}>
                                    {selectedBatch.pending_count} pending
                                </Text>
                            </View>
                        )}
                    </View>
                </SafeAreaView>
            </LinearGradient>

            {selectedBatch ? (
                <QuestionReviewView
                    batch={selectedBatch}
                    onBack={() => setSelectedBatch(null)}
                />
            ) : (
                <BatchListView onSelectBatch={setSelectedBatch} />
            )}
        </AppBackground>
    );
}
