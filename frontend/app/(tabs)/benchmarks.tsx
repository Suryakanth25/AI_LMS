import React, { useState, useCallback } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl, LayoutAnimation, Platform, UIManager } from 'react-native';
import { ChartBar, Clock, Target, Sparkles, ChevronDown, ChevronUp, TrendingUp, Layers } from 'lucide-react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AppBackground } from '@/components/ui/AppBackground';
import { getBenchmarks } from '@/services/api';
import { useFocusEffect } from '@react-navigation/native';

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
    UIManager.setLayoutAnimationEnabledExperimental(true);
}

export default function BenchmarksScreen() {
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [expandedSection, setExpandedSection] = useState<string | null>(null);

    const fetchBenchmarks = async () => {
        try {
            const d = await getBenchmarks();
            setData(d);
        } catch (e) { } finally { setLoading(false); setRefreshing(false); }
    };

    useFocusEffect(useCallback(() => { fetchBenchmarks(); }, []));

    const toggleSection = (section: string) => {
        LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
        setExpandedSection(expandedSection === section ? null : section);
    };

    const renderAccordionHeader = (id: string, title: string, icon: React.ReactNode, color: string, borderColor: string) => (
        <TouchableOpacity
            onPress={() => toggleSection(id)}
            className={`flex-row items-center justify-between p-4 bg-white rounded-xl border ${borderColor} mb-3 shadow-sm active:bg-gray-50`}
        >
            <View className="flex-row items-center gap-3">
                <View className={`w-10 h-10 rounded-full items-center justify-center ${color}`}>
                    {icon}
                </View>
                <Text className="font-bold text-gray-800 text-base">{title}</Text>
            </View>
            {expandedSection === id ? <ChevronUp size={20} color="#9CA3AF" /> : <ChevronDown size={20} color="#9CA3AF" />}
        </TouchableOpacity>
    );

    if (loading) {
        return (
            <AppBackground>
                <View className="flex-1 items-center justify-center">
                    <ActivityIndicator size="large" color="#F97316" />
                    <Text className="text-gray-500 mt-3">Loading benchmarks...</Text>
                </View>
            </AppBackground>
        );
    }

    // Handle case when no benchmarks exist yet
    if (!data || !data.overall_stats || data.overall_stats.total_jobs === 0) {
        return (
            <AppBackground>
                <LinearGradient colors={['#FFA85C', '#F97316']} className="pt-12 pb-6 px-6 rounded-b-[24px] shadow-sm z-10">
                    <SafeAreaView edges={['top']}>
                        <Text className="text-white text-xl font-bold">Benchmarks</Text>
                        <Text className="text-white/80 text-sm">Council performance analytics</Text>
                    </SafeAreaView>
                </LinearGradient>
                <View className="flex-1 items-center justify-center">
                    <Text className="text-gray-300 text-6xl mb-4">📊</Text>
                    <Text className="text-gray-600 font-bold text-lg">No Benchmarks Yet</Text>
                    <Text className="text-gray-400 mt-1">Generate questions to see performance data</Text>
                </View>
            </AppBackground>
        );
    }

    const stats = data.overall_stats;
    const phaseTimings = data.phase_timings || {};
    const councilEffectiveness = data.council_effectiveness || {};
    const questionTypeStats = data.question_type_stats || [];

    return (
        <AppBackground>
            <LinearGradient colors={['#FFA85C', '#F97316']} className="pt-12 pb-6 px-6 rounded-b-[24px] shadow-sm z-10">
                <SafeAreaView edges={['top']}>
                    <Text className="text-white text-xl font-bold">Benchmarks</Text>
                    <Text className="text-white/80 text-sm">Council performance analytics</Text>
                </SafeAreaView>
            </LinearGradient>

            <ScrollView
                className="flex-1 px-4 pt-6"
                contentContainerStyle={{ paddingBottom: 100 }}
                refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchBenchmarks(); }} />}
            >
                {/* Overview Cards */}
                <View className="flex-row gap-3 mb-6">
                    <Animated.View entering={FadeInDown.delay(100)} className="flex-1 bg-white p-3 rounded-xl border border-gray-100 shadow-sm">
                        <Text className="text-gray-500 text-[10px] font-bold uppercase mb-1">Total Jobs</Text>
                        <Text className="text-xl font-bold text-gray-800">{stats.total_jobs || 0}</Text>
                        <View className="flex-row items-center mt-1">
                            <TrendingUp size={12} color="#22C55E" className="mr-1" />
                            <Text className="text-green-500 text-[10px] font-bold">Complete</Text>
                        </View>
                    </Animated.View>

                    <Animated.View entering={FadeInDown.delay(200)} className="flex-1 bg-white p-3 rounded-xl border border-gray-100 shadow-sm">
                        <Text className="text-gray-500 text-[10px] font-bold uppercase mb-1">Questions</Text>
                        <Text className="text-xl font-bold text-gray-800">{stats.total_questions || 0}</Text>
                        <View className="flex-row items-center mt-1">
                            <Sparkles size={12} color="#7C3AED" className="mr-1" />
                            <Text className="text-purple-500 text-[10px] font-bold">Generated</Text>
                        </View>
                    </Animated.View>

                    <Animated.View entering={FadeInDown.delay(300)} className="flex-1 bg-white p-3 rounded-xl border border-gray-100 shadow-sm">
                        <Text className="text-gray-500 text-[10px] font-bold uppercase mb-1">Avg Conf.</Text>
                        <Text className="text-xl font-bold text-gray-800">{(stats.avg_confidence || 0).toFixed(1)}/10</Text>
                        <View className="flex-row items-center mt-1">
                            <View className={`w-2 h-2 rounded-full mr-1 ${stats.avg_confidence > 7 ? 'bg-green-500' : 'bg-yellow-500'}`} />
                            <Text className={`text-[10px] font-bold ${stats.avg_confidence > 7 ? 'text-green-500' : 'text-yellow-600'}`}>
                                {stats.avg_confidence > 7 ? 'High' : 'Med'}
                            </Text>
                        </View>
                    </Animated.View>
                </View>

                {/* Section A: Performance */}
                {renderAccordionHeader('A', 'Performance', <Clock size={20} color="#3B82F6" />, 'bg-blue-100', 'border-blue-200')}
                {expandedSection === 'A' && (
                    <Animated.View entering={FadeInDown} className="bg-white p-4 rounded-xl border-t-0 border-x border-b border-blue-200 -mt-3 mb-3 rounded-t-none">
                        <View className="gap-3">
                            <View className="flex-row justify-between">
                                <Text className="text-gray-600 text-sm">Avg. Time / Question</Text>
                                <Text className="font-bold text-gray-800 text-sm">{(stats.avg_time_per_question || 0).toFixed(1)}s</Text>
                            </View>
                            <View className="flex-row justify-between">
                                <Text className="text-gray-600 text-sm">Total Time (All Jobs)</Text>
                                <Text className="font-bold text-gray-800 text-sm">{(stats.total_time || 0).toFixed(1)}s</Text>
                            </View>
                            <View className="flex-row justify-between">
                                <Text className="text-gray-600 text-sm">Fastest Question</Text>
                                <Text className="font-bold text-green-700 text-sm">{(stats.fastest_question || 0).toFixed(1)}s</Text>
                            </View>
                            <View className="flex-row justify-between">
                                <Text className="text-gray-600 text-sm">Slowest Question</Text>
                                <Text className="font-bold text-red-700 text-sm">{(stats.slowest_question || 0).toFixed(1)}s</Text>
                            </View>
                        </View>
                    </Animated.View>
                )}

                {/* Section B: Phase Timings */}
                {renderAccordionHeader('B', 'Phase Timings', <Layers size={20} color="#16A34A" />, 'bg-green-100', 'border-green-200')}
                {expandedSection === 'B' && (
                    <Animated.View entering={FadeInDown} className="bg-white p-4 rounded-xl border-t-0 border-x border-b border-green-200 -mt-3 mb-3 rounded-t-none">
                        <View className="gap-3">
                            {[
                                { label: 'Phase 1 (Agent A Draft)', value: phaseTimings.avg_phase_1, color: '#3B82F6' },
                                { label: 'Phase 2 (Agent B Review)', value: phaseTimings.avg_phase_2, color: '#8B5CF6' },
                                { label: 'Phase 3 (Agent C Draft)', value: phaseTimings.avg_phase_3, color: '#EC4899' },
                                { label: 'Phase 4 (Chairman Pick)', value: phaseTimings.avg_phase_4, color: '#F97316' },
                            ].map((phase, i) => (
                                <View key={i}>
                                    <View className="flex-row justify-between mb-1">
                                        <Text className="text-gray-600 text-xs">{phase.label}</Text>
                                        <Text className="font-bold text-gray-800 text-xs">{(phase.value || 0).toFixed(2)}s</Text>
                                    </View>
                                    <View className="h-2 bg-gray-100 rounded-full overflow-hidden">
                                        <View
                                            style={{
                                                width: `${Math.min(((phase.value || 0) / Math.max(phaseTimings.avg_phase_1 || 1, phaseTimings.avg_phase_2 || 1, phaseTimings.avg_phase_3 || 1, phaseTimings.avg_phase_4 || 1)) * 100, 100)}%`,
                                                backgroundColor: phase.color,
                                            }}
                                            className="h-full rounded-full"
                                        />
                                    </View>
                                </View>
                            ))}
                        </View>
                    </Animated.View>
                )}

                {/* Section C: Council Effectiveness */}
                {renderAccordionHeader('C', 'Council Effectiveness', <Target size={20} color="#7C3AED" />, 'bg-purple-100', 'border-purple-200')}
                {expandedSection === 'C' && (
                    <Animated.View entering={FadeInDown} className="bg-white p-4 rounded-xl border-t-0 border-x border-b border-purple-200 -mt-3 mb-3 rounded-t-none">
                        <View className="gap-3">
                            <View className="flex-row justify-between">
                                <Text className="text-gray-600 text-sm">Agent A Selected</Text>
                                <Text className="font-bold text-blue-700 text-sm">{councilEffectiveness.agent_a_selected || 0}</Text>
                            </View>
                            <View className="flex-row justify-between">
                                <Text className="text-gray-600 text-sm">Agent C Selected</Text>
                                <Text className="font-bold text-pink-700 text-sm">{councilEffectiveness.agent_c_selected || 0}</Text>
                            </View>
                            <View className="flex-row justify-between">
                                <Text className="text-gray-600 text-sm">Vetting Approved</Text>
                                <Text className="font-bold text-green-700 text-sm">{councilEffectiveness.approved || 0}</Text>
                            </View>
                            <View className="flex-row justify-between">
                                <Text className="text-gray-600 text-sm">Vetting Rejected</Text>
                                <Text className="font-bold text-red-700 text-sm">{councilEffectiveness.rejected || 0}</Text>
                            </View>
                            <View className="flex-row justify-between">
                                <Text className="text-gray-600 text-sm">Pending</Text>
                                <Text className="font-bold text-yellow-700 text-sm">{councilEffectiveness.pending || 0}</Text>
                            </View>
                        </View>
                    </Animated.View>
                )}

                {/* Section D: Question Type Stats */}
                {questionTypeStats.length > 0 && (
                    <>
                        {renderAccordionHeader('D', 'By Question Type', <ChartBar size={20} color="#D97706" />, 'bg-amber-100', 'border-amber-200')}
                        {expandedSection === 'D' && (
                            <Animated.View entering={FadeInDown} className="bg-white p-4 rounded-xl border-t-0 border-x border-b border-amber-200 -mt-3 mb-3 rounded-t-none">
                                <View className="gap-3">
                                    {questionTypeStats.map((qt: any, idx: number) => (
                                        <View key={idx} className="bg-gray-50 rounded-lg p-3">
                                            <View className="flex-row items-center justify-between mb-2">
                                                <Text className="font-bold text-gray-800 text-sm capitalize">{qt.type}</Text>
                                                <Text className="text-gray-500 text-xs">{qt.count} questions</Text>
                                            </View>
                                            <View className="flex-row gap-4">
                                                <View>
                                                    <Text className="text-gray-400 text-[10px]">Avg. Time</Text>
                                                    <Text className="font-bold text-gray-700 text-sm">{(qt.avg_time || 0).toFixed(1)}s</Text>
                                                </View>
                                                <View>
                                                    <Text className="text-gray-400 text-[10px]">Avg. Conf.</Text>
                                                    <Text className="font-bold text-gray-700 text-sm">{(qt.avg_confidence || 0).toFixed(1)}</Text>
                                                </View>
                                            </View>
                                        </View>
                                    ))}
                                </View>
                            </Animated.View>
                        )}
                    </>
                )}
            </ScrollView>
        </AppBackground>
    );
}
