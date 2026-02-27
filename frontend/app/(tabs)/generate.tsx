import React, { useState, useEffect, useRef } from 'react';
import { View, Text, ScrollView, TouchableOpacity, Alert, TextInput, ActivityIndicator, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { Sparkles, Trash, Check, Plus, Clock, Target, FileText } from 'lucide-react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AppBackground } from '@/components/ui/AppBackground';
import Slider from '@react-native-community/slider';
import { getSubjects, getRubrics, createRubric, deleteRubric, getOllamaStatus, startGeneration, pollJob } from '@/services/api';

type ViewMode = 'select' | 'create' | 'generating' | 'complete';

export default function GenerateScreen() {
    const router = useRouter();
    const [view, setView] = useState<ViewMode>('select');
    const [rubrics, setRubrics] = useState<any[]>([]);
    const [subjects, setSubjects] = useState<any[]>([]);
    const [ollamaStatus, setOllamaStatus] = useState<any>(null);
    const [selectedRubric, setSelectedRubric] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    // Create Rubric form
    const [rubricName, setRubricName] = useState('');
    // Subject no longer needed for Rubric creation
    const [selectedSubject, setSelectedSubject] = useState<any>(null);
    const [difficulty, setDifficulty] = useState('Medium');
    const [examType, setExamType] = useState('midterm');
    const [duration, setDuration] = useState('60');
    const [mcqCount, setMcqCount] = useState(5);
    const [mcqMarks, setMcqMarks] = useState('2');
    const [shortCount, setShortCount] = useState(3);
    const [shortMarks, setShortMarks] = useState('5');
    const [essayCount, setEssayCount] = useState(2);
    const [essayMarks, setEssayMarks] = useState('10');

    // Generation state
    const [jobId, setJobId] = useState<number | null>(null);
    const [jobData, setJobData] = useState<any>(null);
    const [elapsed, setElapsed] = useState(0);
    const pollRef = useRef<any>(null);
    const timerRef = useRef<any>(null);

    const fetchData = async () => {
        try {
            const [rubs, subjs, ollama] = await Promise.all([
                getRubrics(),
                getSubjects(),
                getOllamaStatus().catch(() => ({ available: false, models: [] })),
            ]);
            setRubrics(rubs);
            setSubjects(subjs);
            setOllamaStatus(ollama);
        } catch (e) { } finally { setLoading(false); }
    };

    useEffect(() => { fetchData(); }, []);

    useEffect(() => {
        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, []);

    const totalQuestions = mcqCount + shortCount + essayCount;
    const totalMarks = mcqCount * parseInt(mcqMarks || '0') + shortCount * parseInt(shortMarks || '0') + essayCount * parseInt(essayMarks || '0');

    const handleCreateRubric = async () => {
        if (!rubricName.trim()) {
            Alert.alert('Error', 'Rubric name is required');
            return;
        }
        try {
            await createRubric({
                name: rubricName.trim(),
                exam_type: examType,
                duration: parseInt(duration || '60'),
                mcq_count: mcqCount,
                mcq_marks_each: parseInt(mcqMarks || '2'),
                short_count: shortCount,
                short_marks_each: parseInt(shortMarks || '5'),
                essay_count: essayCount,
                essay_marks_each: parseInt(essayMarks || '10'),
            });
            setView('select');
            fetchData();
        } catch (e) {
            Alert.alert('Error', 'Failed to create rubric');
        }
    };

    const handleGenerate = async () => {
        if (!selectedRubric) return;
        if (!selectedSubject) {
            Alert.alert('Error', 'Please select a subject first');
            return;
        }
        // Removed material_count check here, allowing fallback to Sample Questions
        try {
            const result = await startGeneration(selectedRubric.id, selectedSubject.id, difficulty);
            setJobId(result.job_id);
            setJobData({ status: 'pending', progress: 0, total_questions_requested: result.total_questions_requested });
            setElapsed(0);
            setView('generating');

            // Start polling
            pollRef.current = setInterval(async () => {
                try {
                    const job = await pollJob(result.job_id);
                    setJobData(job);
                    if (job.status === 'completed') {
                        clearInterval(pollRef.current);
                        clearInterval(timerRef.current);
                        setView('complete');
                    } else if (job.status === 'failed') {
                        clearInterval(pollRef.current);
                        clearInterval(timerRef.current);
                    }
                } catch (e) { }
            }, 2000);

            // Start timer
            timerRef.current = setInterval(() => {
                setElapsed(prev => prev + 1);
            }, 1000);
        } catch (e) {
            Alert.alert('Error', 'Failed to start generation');
        }
    };

    const getStatusText = (progress: number) => {
        if (progress < 10) return 'Initializing...';
        if (progress < 30) return 'Retrieving study material context...';
        if (progress < 50) return 'Council is deliberating...';
        if (progress < 80) return 'Generating questions...';
        if (progress < 100) return 'Finalizing...';
        return 'Complete!';
    };

    const handleDeleteRubric = (id: number) => {
        if (Platform.OS === 'web') {
            if (window.confirm('Remove this rubric?')) {
                deleteRubric(id).then(fetchData).catch(() => Alert.alert('Error', 'Failed to delete'));
            }
            return;
        }

        Alert.alert('Delete Rubric', 'Remove this rubric?', [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Delete', style: 'destructive', onPress: async () => { await deleteRubric(id); fetchData(); } },
        ]);
    };

    // ─── VIEW: Select Rubric ───
    if (view === 'select') {
        return (
            <AppBackground>
                <LinearGradient colors={['#a78bfa', '#7c3aed']} className="pt-12 pb-6 px-6 rounded-b-[24px] shadow-sm z-10">
                    <SafeAreaView edges={['top']}>
                        <Text className="text-white text-xl font-bold">Generate Questions</Text>
                        <Text className="text-white/80 text-sm">Select a subject and rubric to start</Text>
                    </SafeAreaView>
                </LinearGradient>

                <ScrollView className="flex-1 px-4 pt-4" contentContainerStyle={{ paddingBottom: 100 }}>
                    {/* Ollama Status */}

                    <View className={`flex-row items-center px-4 py-3 rounded-xl border ${ollamaStatus?.available ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                        <View className={`w-3 h-3 rounded-full mr-2 ${ollamaStatus?.available ? 'bg-green-500' : 'bg-red-500'}`} />
                        <Text className={`font-medium text-sm ${ollamaStatus?.available ? 'text-green-700' : 'text-red-700'}`}>
                            {ollamaStatus?.available
                                ? `Ollama Running — ${(() => { const all = ollamaStatus.models || []; const council = all.filter((m: string) => /^(phi3|gemma2|qwen2\.5)/.test(m)); return council.length > 0 ? council.join(', ') : all.slice(0, 3).join(', '); })()}`
                                : 'Ollama Not Running — Start Ollama first'}
                        </Text>
                    </View>
                    {/* Subject Selector */}
                    <Text className="text-gray-600 font-bold text-xs uppercase mb-2 ml-1">Select Subject</Text>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} className="mb-4">
                        <View className="flex-row gap-2">
                            {subjects.map((s: any) => (
                                <TouchableOpacity key={s.id} onPress={() => setSelectedSubject(selectedSubject?.id === s.id ? null : s)}
                                    className={`px-4 py-2 rounded-xl border ${selectedSubject?.id === s.id ? 'bg-purple-500 border-purple-500' : 'bg-white border-gray-200'}`}>
                                    <Text className={`font-medium text-sm ${selectedSubject?.id === s.id ? 'text-white' : 'text-gray-700'}`}>{s.name}</Text>
                                </TouchableOpacity>
                            ))}
                            {subjects.length === 0 && <Text className="text-gray-400 text-sm italic">No subjects available</Text>}
                        </View>
                    </ScrollView>


                    {/* Create Rubric Button */}
                    <TouchableOpacity onPress={() => setView('create')}>
                        <LinearGradient colors={['#a78bfa', '#7c3aed']} style={{ borderRadius: 16 }} className="py-3 flex-row items-center justify-center mb-4">
                            <Plus size={18} color="white" />
                            <Text className="text-white font-bold ml-2">Create New Rubric</Text>
                        </LinearGradient>
                    </TouchableOpacity>

                    {loading ? (
                        <ActivityIndicator size="large" color="#7c3aed" className="py-10" />
                    ) : rubrics.length === 0 ? (
                        <View className="items-center py-10">
                            <Text className="text-gray-400 text-4xl mb-3">📋</Text>
                            <Text className="text-gray-500 font-medium">No rubrics yet. Create one to start.</Text>
                        </View>
                    ) : (
                        rubrics.map((rubric, idx) => (
                            <Animated.View key={rubric.id} entering={FadeInDown.delay(idx * 60)}>
                                <TouchableOpacity
                                    onPress={() => setSelectedRubric(selectedRubric?.id === rubric.id ? null : rubric)}
                                    className={`bg-white rounded-xl border-2 p-4 mb-3 ${selectedRubric?.id === rubric.id ? 'border-purple-500' : 'border-gray-100'}`}
                                >
                                    <View className="flex-row items-center justify-between mb-2">
                                        <Text className="font-bold text-gray-800 text-base flex-1">{rubric.name}</Text>
                                        <View className="flex-row items-center">
                                            {selectedRubric?.id === rubric.id && (
                                                <View className="w-6 h-6 rounded-full bg-purple-500 items-center justify-center mr-2">
                                                    <Check size={14} color="white" />
                                                </View>
                                            )}
                                            <TouchableOpacity onPress={() => handleDeleteRubric(rubric.id)} className="p-1">
                                                <Trash size={16} color="#EF4444" />
                                            </TouchableOpacity>
                                        </View>
                                    </View>

                                    <Text className="text-gray-500 text-xs mb-2">{rubric.exam_type}</Text>
                                    <View className="flex-row gap-2 flex-wrap">
                                        <View className="bg-blue-50 px-2 py-1 rounded-full">
                                            <Text className="text-blue-700 text-[10px] font-bold">MCQ: {rubric.mcq_count}</Text>
                                        </View>
                                        <View className="bg-green-50 px-2 py-1 rounded-full">
                                            <Text className="text-green-700 text-[10px] font-bold">Short: {rubric.short_count}</Text>
                                        </View>
                                        <View className="bg-purple-50 px-2 py-1 rounded-full">
                                            <Text className="text-purple-700 text-[10px] font-bold">Essay: {rubric.essay_count}</Text>
                                        </View>
                                        <View className="bg-gray-100 px-2 py-1 rounded-full">
                                            <Text className="text-gray-700 text-[10px] font-bold">{rubric.total_marks} marks • {rubric.duration}min</Text>
                                        </View>
                                    </View>
                                </TouchableOpacity>
                            </Animated.View>
                        ))
                    )}

                    {/* Difficulty Selector */}
                    {selectedRubric && selectedSubject && ollamaStatus?.available && (
                        <View className="mt-2 mb-2">
                            <Text className="text-gray-600 font-bold text-xs uppercase mb-2 ml-1">Select Difficulty Preference</Text>
                            <View className="flex-row gap-2">
                                {['Easy', 'Medium', 'Hard'].map(level => (
                                    <TouchableOpacity
                                        key={level}
                                        onPress={() => setDifficulty(level)}
                                        className={`flex-1 py-3 rounded-xl border items-center shadow-sm ${difficulty === level ? 'bg-indigo-500 border-indigo-500' : 'bg-white border-gray-200'}`}
                                    >
                                        <Text className={`font-bold text-sm ${difficulty === level ? 'text-white' : 'text-gray-700'}`}>{level}</Text>
                                    </TouchableOpacity>
                                ))}
                            </View>
                        </View>
                    )}

                    {/* Generate Button */}
                    <TouchableOpacity
                        onPress={handleGenerate}
                        disabled={!selectedRubric || !selectedSubject || !ollamaStatus?.available}
                        className="mt-4"
                    >
                        <LinearGradient
                            colors={!selectedRubric || !selectedSubject || !ollamaStatus?.available ? ['#d1d5db', '#9ca3af'] : ['#a78bfa', '#7c3aed']}
                            style={{ borderRadius: 16 }} className="py-4 flex-row items-center justify-center"
                        >
                            <Sparkles size={20} color="white" />
                            <Text className="text-white font-bold text-base ml-2">Generate Questions</Text>
                        </LinearGradient>
                    </TouchableOpacity>
                </ScrollView>
            </AppBackground>
        );
    }

    // ─── VIEW: Create Rubric ───
    if (view === 'create') {
        return (
            <AppBackground>
                <LinearGradient colors={['#a78bfa', '#7c3aed']} className="pt-12 pb-6 px-6 rounded-b-[24px] shadow-sm z-10">
                    <SafeAreaView edges={['top']}>
                        <View className="flex-row items-center">
                            <TouchableOpacity onPress={() => setView('select')} className="mr-3">
                                <Text className="text-white text-2xl">←</Text>
                            </TouchableOpacity>
                            <Text className="text-white text-xl font-bold">Create Rubric</Text>
                        </View>
                    </SafeAreaView>
                </LinearGradient>

                <ScrollView className="flex-1 px-4 pt-4" contentContainerStyle={{ paddingBottom: 100 }}>
                    <TextInput placeholder="Rubric Name" value={rubricName} onChangeText={setRubricName}
                        className="bg-white border border-gray-200 rounded-xl px-4 py-3 mb-3 text-gray-800" placeholderTextColor="#9CA3AF" />

                    <TextInput placeholder="Rubric Name" value={rubricName} onChangeText={setRubricName}
                        className="bg-white border border-gray-200 rounded-xl px-4 py-3 mb-3 text-gray-800" placeholderTextColor="#9CA3AF" />

                    {/* Exam Type */}
                    <Text className="text-gray-600 font-bold text-xs uppercase mb-2 ml-1">Exam Type</Text>
                    <View className="flex-row gap-2 mb-4">
                        {['final', 'midterm', 'quiz'].map(t => (
                            <TouchableOpacity key={t} onPress={() => setExamType(t)}
                                className={`flex-1 py-2 rounded-xl border items-center ${examType === t ? 'bg-purple-500 border-purple-500' : 'bg-white border-gray-200'}`}>
                                <Text className={`font-bold text-sm capitalize ${examType === t ? 'text-white' : 'text-gray-700'}`}>{t}</Text>
                            </TouchableOpacity>
                        ))}
                    </View>

                    {/* Duration */}
                    <TextInput placeholder="Duration (minutes)" value={duration} onChangeText={setDuration}
                        className="bg-white border border-gray-200 rounded-xl px-4 py-3 mb-4 text-gray-800" placeholderTextColor="#9CA3AF" keyboardType="number-pad" />

                    {/* Question Distribution */}
                    <View className="bg-white rounded-xl border border-gray-100 p-4 mb-4">
                        <Text className="font-bold text-gray-800 mb-3">Question Distribution</Text>

                        <Text className="text-gray-600 text-xs font-bold mb-1">MCQ: {mcqCount}</Text>
                        <Slider minimumValue={0} maximumValue={30} step={1} value={mcqCount} onValueChange={setMcqCount}
                            minimumTrackTintColor="#3B82F6" maximumTrackTintColor="#E5E7EB" />
                        <TextInput placeholder="Marks each" value={mcqMarks} onChangeText={setMcqMarks}
                            className="border border-gray-100 rounded-lg px-3 py-2 mb-3 text-gray-800 text-sm" keyboardType="number-pad" />

                        <Text className="text-gray-600 text-xs font-bold mb-1">Short Notes: {shortCount}</Text>
                        <Slider minimumValue={0} maximumValue={15} step={1} value={shortCount} onValueChange={setShortCount}
                            minimumTrackTintColor="#16A34A" maximumTrackTintColor="#E5E7EB" />
                        <TextInput placeholder="Marks each" value={shortMarks} onChangeText={setShortMarks}
                            className="border border-gray-100 rounded-lg px-3 py-2 mb-3 text-gray-800 text-sm" keyboardType="number-pad" />

                        <Text className="text-gray-600 text-xs font-bold mb-1">Essay: {essayCount}</Text>
                        <Slider minimumValue={0} maximumValue={10} step={1} value={essayCount} onValueChange={setEssayCount}
                            minimumTrackTintColor="#7C3AED" maximumTrackTintColor="#E5E7EB" />
                        <TextInput placeholder="Marks each" value={essayMarks} onChangeText={setEssayMarks}
                            className="border border-gray-100 rounded-lg px-3 py-2 text-gray-800 text-sm" keyboardType="number-pad" />
                    </View>

                    {/* Summary */}
                    <View className="bg-purple-50 rounded-xl p-4 mb-4 border border-purple-100">
                        <Text className="text-purple-800 font-bold text-center text-lg">
                            Total: {totalQuestions} Questions • {totalMarks} Marks
                        </Text>
                    </View>

                    <TouchableOpacity onPress={handleCreateRubric}>
                        <LinearGradient colors={['#a78bfa', '#7c3aed']} style={{ borderRadius: 16 }} className="py-4 items-center">
                            <Text className="text-white font-bold text-base">Save Rubric</Text>
                        </LinearGradient>
                    </TouchableOpacity>
                </ScrollView>
            </AppBackground>
        );
    }

    // ─── VIEW: Generating ───
    if (view === 'generating') {
        const progress = jobData?.progress || 0;
        const isFailed = jobData?.status === 'failed';
        return (
            <AppBackground>
                <View className="flex-1 items-center justify-center px-6">
                    {isFailed ? (
                        <View className="items-center">
                            <Text className="text-red-500 text-5xl mb-4">❌</Text>
                            <Text className="text-red-600 font-bold text-xl mb-2">Generation Failed</Text>
                            <Text className="text-gray-500 text-center mb-6">{jobData?.error_message || 'An error occurred'}</Text>
                            <TouchableOpacity onPress={() => { setView('select'); clearInterval(pollRef.current); clearInterval(timerRef.current); }}>
                                <LinearGradient colors={['#EF4444', '#DC2626']} className="px-8 py-3 rounded-xl">
                                    <Text className="text-white font-bold">Try Again</Text>
                                </LinearGradient>
                            </TouchableOpacity>
                        </View>
                    ) : (
                        <View className="items-center w-full">
                            <ActivityIndicator size="large" color="#7c3aed" className="mb-6" />
                            <Text className="text-gray-800 font-bold text-xl mb-2">The Council is Working</Text>
                            <Text className="text-gray-500 text-sm mb-6">{getStatusText(progress)}</Text>

                            {/* Progress bar */}
                            <View className="w-full h-3 bg-gray-200 rounded-full overflow-hidden mb-4">
                                <LinearGradient
                                    colors={['#a78bfa', '#7c3aed']}
                                    start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
                                    style={{ width: `${Math.max(progress, 3)}%`, height: '100%', borderRadius: 999 }}
                                />
                            </View>
                            <Text className="text-purple-600 font-bold text-lg mb-4">{progress}%</Text>

                            <View className="flex-row gap-6 mb-4">
                                <View className="items-center">
                                    <Text className="text-gray-500 text-xs">Questions</Text>
                                    <Text className="text-gray-800 font-bold text-lg">{jobData?.total_questions_generated || 0} / {jobData?.total_questions_requested || '?'}</Text>
                                </View>
                                <View className="items-center">
                                    <Text className="text-gray-500 text-xs">Elapsed</Text>
                                    <Text className="text-gray-800 font-bold text-lg">{Math.floor(elapsed / 60)}:{(elapsed % 60).toString().padStart(2, '0')}</Text>
                                </View>
                            </View>
                        </View>
                    )}
                </View>
            </AppBackground>
        );
    }

    // ─── VIEW: Complete ───
    return (
        <AppBackground>
            <View className="flex-1 items-center justify-center px-6">
                <Animated.View entering={FadeInDown} className="items-center w-full">
                    <View className="w-20 h-20 rounded-full bg-green-100 items-center justify-center mb-4">
                        <Check size={40} color="#16A34A" />
                    </View>
                    <Text className="text-gray-800 font-bold text-2xl mb-2">{jobData?.total_questions_generated || 0} Questions Generated!</Text>

                    <View className="flex-row gap-4 mb-6">
                        <View className="bg-white rounded-xl p-4 flex-1 border border-gray-100 items-center">
                            <Clock size={20} color="#7C3AED" />
                            <Text className="text-gray-500 text-xs mt-1">Total Time</Text>
                            <Text className="text-gray-800 font-bold">{(jobData?.total_time_seconds || 0).toFixed(0)}s</Text>
                        </View>
                        <View className="bg-white rounded-xl p-4 flex-1 border border-gray-100 items-center">
                            <Target size={20} color="#3B82F6" />
                            <Text className="text-gray-500 text-xs mt-1">Avg / Question</Text>
                            <Text className="text-gray-800 font-bold">{(jobData?.avg_time_per_question || 0).toFixed(1)}s</Text>
                        </View>
                        <View className="bg-white rounded-xl p-4 flex-1 border border-gray-100 items-center">
                            <Sparkles size={20} color="#16A34A" />
                            <Text className="text-gray-500 text-xs mt-1">Confidence</Text>
                            <Text className="text-gray-800 font-bold">{(jobData?.avg_confidence_score || 0).toFixed(1)}/10</Text>
                        </View>
                    </View>

                    <TouchableOpacity onPress={() => router.push('/(tabs)/vetting')} className="w-full mb-3">
                        <LinearGradient colors={['#8fd36a', '#5cb82a']} className="py-4 rounded-xl items-center">
                            <Text className="text-white font-bold text-base">Review in Vetting Queue</Text>
                        </LinearGradient>
                    </TouchableOpacity>

                    <TouchableOpacity onPress={() => router.push('/(tabs)/benchmarks')} className="w-full mb-3">
                        <LinearGradient colors={['#FFA85C', '#F97316']} className="py-4 rounded-xl items-center">
                            <Text className="text-white font-bold text-base">View Benchmarks</Text>
                        </LinearGradient>
                    </TouchableOpacity>

                    <TouchableOpacity onPress={() => { setView('select'); setSelectedRubric(null); setSelectedSubject(null); fetchData(); }} className="w-full">
                        <View className="py-4 rounded-xl items-center border border-gray-200 bg-white">
                            <Text className="text-gray-700 font-bold text-base">Generate Another</Text>
                        </View>
                    </TouchableOpacity>
                </Animated.View>
            </View>
        </AppBackground>
    );
}
