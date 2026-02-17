import React, { useState, useEffect, useCallback, useRef } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, ScrollView, Alert, Modal } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Brain, Check, X, Play, RefreshCw, FileText, ChartBar, Clock } from 'lucide-react-native';
import Animated, { FadeInDown, FadeInUp } from 'react-native-reanimated';
import { getDatasetStats, getTrainingStatus, startTraining, getSkillContent } from '@/services/api';
import { GradientCard } from '@/components/ui/GradientCard';

interface TrainingDashboardProps {
    subjectId: number;
}

export function TrainingDashboard({ subjectId }: TrainingDashboardProps) {
    const [stats, setStats] = useState<any>(null);
    const [status, setStatus] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [starting, setStarting] = useState(false);
    const [skillModal, setSkillModal] = useState(false);
    const [skillContent, setSkillContent] = useState('');
    const [elapsed, setElapsed] = useState(0);
    const timerStart = useRef<number | null>(null);
    const timerInterval = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetchData = useCallback(async () => {
        try {
            const [sStats, sStatus] = await Promise.all([
                getDatasetStats(subjectId),
                getTrainingStatus(subjectId)
            ]);
            setStats(sStats);
            setStatus(sStatus);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, [subjectId]);

    useEffect(() => {
        fetchData();
        // Poll status if active
        const interval = setInterval(() => {
            if (status && ['generating', 'evaluating_baseline', 'evaluating_skill'].includes(status.status)) {
                getTrainingStatus(subjectId).then(setStatus).catch(() => { });
            }
        }, 3000);
        return () => clearInterval(interval);
    }, [fetchData, status?.status]);

    // ── Elapsed Time Timer ──
    useEffect(() => {
        const isActive = status?.status && ['generating', 'evaluating_baseline', 'evaluating_skill'].includes(status.status);

        if (isActive) {
            if (!timerStart.current) {
                // Training just started — begin counting
                timerStart.current = Date.now();
                setElapsed(0);
            }
            // Always (re)start interval when active
            if (timerInterval.current) clearInterval(timerInterval.current);
            timerInterval.current = setInterval(() => {
                if (timerStart.current) {
                    setElapsed(Math.floor((Date.now() - timerStart.current) / 1000));
                }
            }, 1000);
        } else {
            // Training ended — stop the timer but keep the final value
            if (timerInterval.current) {
                clearInterval(timerInterval.current);
                timerInterval.current = null;
            }
            timerStart.current = null;
        }

        return () => {
            if (timerInterval.current) clearInterval(timerInterval.current);
        };
    }, [status?.status]);

    const formatElapsed = (secs: number) => {
        const m = Math.floor(secs / 60).toString().padStart(2, '0');
        const s = (secs % 60).toString().padStart(2, '0');
        return `${m}:${s}`;
    };

    const handleStartTraining = async () => {
        setStarting(true);
        try {
            await startTraining(subjectId);
            await fetchData();
        } catch (e: any) {
            Alert.alert('Error', e.message || 'Failed to start training');
        } finally {
            setStarting(false);
        }
    };

    const handleViewSkill = async () => {
        try {
            const skill = await getSkillContent(subjectId);
            if (skill) {
                setSkillContent(skill.skill_content);
                setSkillModal(true);
            } else {
                Alert.alert('Info', 'No skill content found.');
            }
        } catch (e) { Alert.alert('Error', 'Failed to load skill'); }
    };

    if (loading) return <ActivityIndicator color="#3B82F6" />;

    const isTraining = status?.status && ['generating', 'evaluating_baseline', 'evaluating_skill'].includes(status.status);
    const isComplete = status?.status === 'complete';
    const progress = status?.progress || 0;

    return (
        <View style={{ flex: 1, padding: 16 }}>
            {/* Header Stats */}
            <View style={{ flexDirection: 'row', gap: 12, marginBottom: 24 }}>
                <View style={{ flex: 1, padding: 16, alignItems: 'center', borderColor: '#A7F3D0', borderWidth: 1, backgroundColor: '#ECFDF5', borderRadius: 12 }}>
                    <Check size={24} color="#10B981" style={{ marginBottom: 8 }} />
                    <Text style={{ color: '#065F46', fontSize: 20, fontWeight: 'bold' }}>{stats?.approved || 0}</Text>
                    <Text style={{ color: '#047857', fontSize: 12 }}>Approved</Text>
                </View>
                <View style={{ flex: 1, padding: 16, alignItems: 'center', borderColor: '#FECACA', borderWidth: 1, backgroundColor: '#FEF2F2', borderRadius: 12 }}>
                    <X size={24} color="#EF4444" style={{ marginBottom: 8 }} />
                    <Text style={{ color: '#991B1B', fontSize: 20, fontWeight: 'bold' }}>{stats?.rejected || 0}</Text>
                    <Text style={{ color: '#B91C1C', fontSize: 12 }}>Rejected</Text>
                </View>
            </View>

            {/* Training Control */}
            <View style={{ padding: 20, marginBottom: 24, borderColor: '#E5E7EB', borderWidth: 1, backgroundColor: 'white', borderRadius: 12, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 2 }}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                    <View>
                        <Text style={{ color: '#1F2937', fontSize: 18, fontWeight: 'bold' }}>Model Training</Text>
                        <Text style={{ color: status?.is_active === false ? '#EF4444' : '#6B7280', fontSize: 12 }}>
                            {status?.version > 0
                                ? `Version ${status.version} ${status?.is_active === false ? '(Inactive)' : 'Active'}`
                                : 'No active skill'}
                        </Text>
                    </View>
                    <Brain size={32} color={isTraining ? '#F59E0B' : isComplete ? (status?.is_active === false ? '#EF4444' : '#10B981') : '#9CA3AF'} />
                </View>

                {isTraining ? (
                    <View>
                        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                            <Text style={{ color: '#3B82F6', fontWeight: '600' }}>
                                {status.status === 'generating' ? 'Generating Skill Guide...' :
                                    status.status === 'evaluating_baseline' ? 'Running Baseline Tests...' :
                                        'Verifying Improvements...'}
                            </Text>
                            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#FEF3C7', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 }}>
                                    <Clock size={12} color="#D97706" />
                                    <Text style={{ color: '#D97706', fontSize: 13, fontWeight: 'bold', fontFamily: 'monospace' }}>{formatElapsed(elapsed)}</Text>
                                </View>
                                <Text style={{ color: '#4B5563', fontWeight: 'bold' }}>{progress}%</Text>
                            </View>
                        </View>
                        <View style={{ height: 6, backgroundColor: '#E5E7EB', borderRadius: 3, overflow: 'hidden' }}>
                            <View style={{ width: `${progress}%`, height: '100%', backgroundColor: '#3B82F6' }} />
                        </View>
                        <Text style={{ color: '#6B7280', fontSize: 10, marginTop: 8, fontFamily: 'monospace' }}>
                            {status?.training_log?.split('\n').pop() || 'Initializing...'}
                        </Text>
                    </View>
                ) : (
                    <View>
                        <View style={{ flexDirection: 'row', gap: 12 }}>
                            <TouchableOpacity
                                onPress={handleStartTraining}
                                disabled={starting || !stats?.ready_for_training}
                                style={{
                                    flex: 1,
                                    backgroundColor: stats?.ready_for_training ? '#3B82F6' : '#E5E7EB',
                                    padding: 12, borderRadius: 8,
                                    flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 8
                                }}
                            >
                                {starting ? <ActivityIndicator color="white" /> : <Play size={16} color={stats?.ready_for_training ? "white" : "#9CA3AF"} />}
                                <Text style={{ color: stats?.ready_for_training ? 'white' : '#9CA3AF', fontWeight: 'bold' }}>{status?.version > 0 ? 'Retrain Model' : 'Start Training'}</Text>
                            </TouchableOpacity>

                            {status?.version > 0 && (
                                <TouchableOpacity
                                    onPress={handleViewSkill}
                                    style={{ backgroundColor: '#F3F4F6', padding: 12, borderRadius: 8, justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: '#E5E7EB' }}
                                >
                                    <FileText size={20} color="#4B5563" />
                                </TouchableOpacity>
                            )}
                        </View>
                        {!stats?.ready_for_training && (
                            <Text style={{ color: '#EF4444', fontSize: 12, marginTop: 8 }}>
                                Need 5 approved questions to start (Current: {stats?.approved || 0})
                            </Text>
                        )}
                    </View>
                )}
            </View>

            {/* Deactivation Warning */}
            {status?.auto_deactivated && (
                <View style={{ padding: 14, marginBottom: 16, backgroundColor: '#FEF2F2', borderColor: '#FECACA', borderWidth: 1, borderRadius: 10 }}>
                    <Text style={{ color: '#991B1B', fontWeight: 'bold', fontSize: 13, marginBottom: 4 }}>⚠️ Version Not Activated</Text>
                    <Text style={{ color: '#B91C1C', fontSize: 12, lineHeight: 18 }}>
                        {status.deactivation_reason || 'New version scored lower than the previous active version.'}
                    </Text>
                </View>
            )}

            {/* Performance Metrics */}
            {status?.version > 0 && (
                <View>
                    <Text style={{ color: '#374151', fontWeight: 'bold', marginBottom: 12 }}>Performance Metrics</Text>
                    <View style={{ flexDirection: 'row', gap: 12 }}>
                        <View style={{ flex: 1, backgroundColor: 'white', padding: 16, borderRadius: 12, borderColor: '#E5E7EB', borderWidth: 1 }}>
                            <Text style={{ color: '#6B7280', fontSize: 12, marginBottom: 4 }}>Baseline</Text>
                            <Text style={{ color: '#1F2937', fontSize: 24, fontWeight: 'bold' }}>{(status.baseline_score * 100).toFixed(0)}%</Text>
                        </View>
                        <View style={{ flex: 1, backgroundColor: 'white', padding: 16, borderRadius: 12, borderColor: '#E5E7EB', borderWidth: 1 }}>
                            <Text style={{ color: '#6B7280', fontSize: 12, marginBottom: 4 }}>After Training</Text>
                            <Text style={{ color: '#10B981', fontSize: 24, fontWeight: 'bold' }}>{(status.trained_score * 100).toFixed(0)}%</Text>
                        </View>
                        <View style={{ flex: 1, backgroundColor: '#EFF6FF', padding: 16, borderRadius: 12, borderColor: '#3B82F6', borderWidth: 1, alignItems: 'center', justifyContent: 'center' }}>
                            <Text style={{ color: '#2563EB', fontSize: 12 }}>Impact</Text>
                            <Text style={{ color: '#2563EB', fontSize: 20, fontWeight: 'bold' }}>
                                {status.improvement_pct > 0 ? '+' : ''}{status.improvement_pct.toFixed(0)} pts
                            </Text>
                        </View>
                    </View>
                </View>
            )}

            {/* Skill Modal */}
            <Modal visible={skillModal} animationType="slide" transparent>
                <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', padding: 20, justifyContent: 'center' }}>
                    <View style={{ backgroundColor: 'white', borderRadius: 16, maxHeight: '80%', borderColor: '#E5E7EB', borderWidth: 1, shadowColor: '#000', shadowOpacity: 0.1, shadowRadius: 10, elevation: 5 }}>
                        <View style={{ padding: 16, borderBottomWidth: 1, borderBottomColor: '#E5E7EB', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Text style={{ color: '#1F2937', fontSize: 18, fontWeight: 'bold' }}>Generated Skill Guide</Text>
                            <TouchableOpacity onPress={() => setSkillModal(false)}>
                                <X color="#6B7280" />
                            </TouchableOpacity>
                        </View>
                        <ScrollView style={{ padding: 16 }}>
                            <Text style={{ color: '#374151', fontFamily: 'monospace', fontSize: 12 }}>{skillContent}</Text>
                        </ScrollView>
                    </View>
                </View>
            </Modal>
        </View>
    );
}
