import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, TouchableOpacity, Alert, TextInput, ActivityIndicator, Modal as RNModal, RefreshControl, Platform } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { ArrowLeft, Upload, Trash, ChevronDown, ChevronUp, Plus, FileText, Database, BookOpen, Info, X, Save, Pencil, Brain, Eye } from 'lucide-react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AppBackground } from '@/components/ui/AppBackground';
import Animated, { FadeInDown } from 'react-native-reanimated';
import Modal from 'react-native-modal';
import * as DocumentPicker from 'expo-document-picker';
import Slider from '@react-native-community/slider';
import {
    getSubjectDetail, getMaterials, uploadMaterial, deleteMaterial, getRagStatus,
    createUnit, deleteUnit, createTopic, deleteTopic,
    updateTopicSyllabus, uploadSampleQuestions, deleteSampleQuestion, getSampleQuestions,
    createLO, deleteLO, createCO, deleteCO, updateUnitCOMapping, getUnitCOMapping,
    updateLO, updateCO,
} from '@/services/api';
import { GradientCard } from '@/components/ui/GradientCard';
import { TrainingDashboard } from '@/components/TrainingDashboard';

export default function SubjectDetailScreen() {
    const { subjectId } = useLocalSearchParams<{ subjectId: string }>();
    const router = useRouter();
    const numId = parseInt(subjectId || '0');

    const [activeTab, setActiveTab] = useState<'content' | 'training'>('content');

    // Data State
    const [subject, setSubject] = useState<any>(null);
    const [materials, setMaterials] = useState<any[]>([]); // All subject materials
    const [ragStatus, setRagStatus] = useState<any>(null);

    // UI State
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [uploadingTopicId, setUploadingTopicId] = useState<number | null>(null);
    const [expandedUnits, setExpandedUnits] = useState<Set<number>>(new Set());
    const [expandedTopics, setExpandedTopics] = useState<Set<number>>(new Set());
    const [expandedLOs, setExpandedLOs] = useState<Set<number>>(new Set()); // Dropdown for LOs inside Units
    const [coExpanded, setCoExpanded] = useState(false); // Dropdown for Subject COs

    // --- Modals State ---
    const [unitModal, setUnitModal] = useState(false);
    const [unitName, setUnitName] = useState('');
    const [unitNumber, setUnitNumber] = useState('');

    const [topicCreateModal, setTopicCreateModal] = useState(false);
    const [activeUnitId, setActiveUnitId] = useState<number | null>(null);
    const [topicTitle, setTopicTitle] = useState('');

    // Syllabus & Outcomes State
    const [syllabusModal, setSyllabusModal] = useState(false); // Now mainly for Bloom's
    const [activeTopicForSyllabus, setActiveTopicForSyllabus] = useState<any>(null);
    const [bloomDistribution, setBloomDistribution] = useState<Record<string, number>>({
        "Knowledge": 40, "Comprehension": 20, "Application": 20, "Analysis": 10, "Synthesis": 5, "Evaluation": 5
    });

    // LO/CO Modals
    const [loModal, setLoModal] = useState(false);
    const [activeUnitForLo, setActiveUnitForLo] = useState<any>(null);
    const [loText, setLoText] = useState('');
    const [loCode, setLoCode] = useState('');
    const [editingLoId, setEditingLoId] = useState<number | null>(null);

    const [coModal, setCoModal] = useState(false);
    // Remove activeTopicForCo, COs are now subject-level
    const [coText, setCoText] = useState('');
    const [coCode, setCoCode] = useState('');
    const [coBlooms, setCoBlooms] = useState<string[]>(['Knowledge']);
    const [editingCoId, setEditingCoId] = useState<number | null>(null);

    // Mapping Modal
    const [mappingModal, setMappingModal] = useState(false);
    const [activeUnitForMapping, setActiveUnitForMapping] = useState<any>(null);
    const [selectedCOs, setSelectedCOs] = useState<Set<number>>(new Set());
    // Sample Question Modal
    const [topicQuestions, setTopicQuestions] = useState<Record<number, any[]>>({}); // Cache questions
    const [uploadingSqTopicId, setUploadingSqTopicId] = useState<number | null>(null); // Track which topic is uploading

    useEffect(() => { fetchAll(); }, [numId]);

    const fetchAll = async () => {
        try {
            const [subj, mats, rag] = await Promise.all([
                getSubjectDetail(numId),
                getMaterials(numId),
                getRagStatus(numId),
            ]);
            setSubject(subj);
            setMaterials(mats);
            setRagStatus(rag);

            // Refresh sample questions for expanded topics if needed
            // For now, we accept they might be stale until re-expanded or page refresh
        } catch (e) {
            // Alert.alert('Error', 'Failed to load subject data');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    // Helper
    const countMaterials = () => materials ? materials.length : 0;

    const handleDeleteUnit = (id: number) => {
        if (Platform.OS === 'web') {
            if (window.confirm('Delete Unit? Cannot undo.')) {
                deleteUnit(id).then(fetchAll).catch(console.error);
            }
            return;
        }
        Alert.alert('Delete Unit', 'Cannot undo.', [
            { text: 'Cancel' },
            {
                text: 'Delete', style: 'destructive', onPress: async () => {
                    await deleteUnit(id);
                    fetchAll();
                }
            }
        ]);
    };

    const handleDeleteTopic = (id: number) => {
        if (Platform.OS === 'web') {
            if (window.confirm('Delete Topic? Cannot undo.')) {
                deleteTopic(id).then(fetchAll).catch(console.error);
            }
            return;
        }
        Alert.alert('Delete Topic', 'Cannot undo.', [
            { text: 'Cancel' },
            {
                text: 'Delete', style: 'destructive', onPress: async () => {
                    await deleteTopic(id);
                    fetchAll();
                }
            }
        ]);
    };


    // --- Accordion Logic ---
    const toggleUnit = (unitId: number) => {
        const next = new Set(expandedUnits);
        next.has(unitId) ? next.delete(unitId) : next.add(unitId);
        setExpandedUnits(next);
    };

    const toggleLO = (unitId: number) => {
        const next = new Set(expandedLOs);
        next.has(unitId) ? next.delete(unitId) : next.add(unitId);
        setExpandedLOs(next);
    };

    const toggleTopic = async (topicId: number) => {
        const next = new Set(expandedTopics);
        if (next.has(topicId)) {
            next.delete(topicId);
        } else {
            next.add(topicId);
            // Fetch sample questions when expanding
            fetchSampleQuestions(topicId);
        }
        setExpandedTopics(next);
    };

    const fetchSampleQuestions = async (topicId: number) => {
        try {
            const qs = await getSampleQuestions(topicId);
            setTopicQuestions(prev => ({ ...prev, [topicId]: qs }));
        } catch (e) { console.error(e); }
    };

    // --- Actions ---

    const handleUploadMaterial = async (topicId: number) => {
        try {
            const result = await DocumentPicker.getDocumentAsync({
                type: ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'],
            });
            if (result.canceled) return;

            const file = result.assets[0];
            setUploadingTopicId(topicId);

            // Web-specific fix: Use the raw File object if available
            let formFile: any;
            if (Platform.OS === 'web' && (file as any).file) {
                formFile = (file as any).file;
            } else {
                formFile = { uri: file.uri, name: file.name, type: file.mimeType || 'application/octet-stream' } as any;
            }

            await uploadMaterial(numId, formFile, topicId); // Pass topicId

            await fetchAll();
        } catch (e) {
            Alert.alert('Error', 'Upload failed');
        } finally {
            setUploadingTopicId(null);
        }
    };

    const handleDeleteMaterial = (matId: number, name: string) => {
        if (Platform.OS === 'web') {
            if (window.confirm(`Remove material "${name}"?`)) {
                deleteMaterial(matId).then(fetchAll).catch(() => Alert.alert('Error', 'Failed to delete'));
            }
            return;
        }
        Alert.alert('Delete Material', `Remove "${name}"?`, [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Delete', style: 'destructive', onPress: async () => { await deleteMaterial(matId); fetchAll(); } },
        ]);
    };

    // --- Syllabus (Bloom's) Actions ---
    const openSyllabusModal = (topic: any) => {
        setActiveTopicForSyllabus(topic);
        const data = topic.syllabus_data || {};
        // Ensure bloom_distribution is initialized if missing
        const bloom = data.bloom_distribution || {
            "Knowledge": 40, "Comprehension": 20, "Application": 20, "Analysis": 10, "Synthesis": 5, "Evaluation": 5
        };
        setBloomDistribution({ ...bloom });
        setSyllabusModal(true);
    };

    const handleSaveSyllabus = async () => {
        if (!activeTopicForSyllabus) return;
        try {
            await updateTopicSyllabus(activeTopicForSyllabus.id,
                { ...activeTopicForSyllabus.syllabus_data, bloom_distribution: bloomDistribution }
            );
            setSyllabusModal(false);
            fetchAll();
            Alert.alert('Success', 'Bloom\'s taxonomy saved');
        } catch (e) {
            Alert.alert('Error', 'Failed to save');
        }
    };

    // --- LO/CO Actions ---
    const handleCreateLO = async () => {
        if (!activeUnitForLo) return;
        try {
            if (editingLoId) {
                await updateLO(editingLoId, { description: loText, code: loCode });
            } else {
                await createLO(activeUnitForLo.id, { description: loText, code: loCode });
            }
            setLoModal(false); setLoText(''); setLoCode(''); setEditingLoId(null);
            fetchAll();
        } catch (e) { Alert.alert('Error', 'Failed to save LO'); }
    };

    const openLoModal = (unit: any, lo?: any) => {
        setActiveUnitForLo(unit);
        if (lo) {
            setEditingLoId(lo.id);
            setLoText(lo.description || '');
            setLoCode(lo.code || '');
        } else {
            setEditingLoId(null);
            setLoText('');
            setLoCode('');
        }
        setLoModal(true);
    };

    const handleDeleteLO = async (id: number) => {
        if (Platform.OS === 'web') {
            if (window.confirm('Delete LO? This cannot be undone.')) {
                deleteLO(id).then(fetchAll).catch(console.error);
            }
            return;
        }
        Alert.alert('Delete LO?', 'This cannot be undone.', [
            { text: 'Cancel' },
            { text: 'Delete', style: 'destructive', onPress: async () => { await deleteLO(id); fetchAll(); } }
        ]);
    };

    const handleCreateCO = async () => {
        // Code is encouraged but description is optional
        if (!coCode.trim() && !coText.trim()) {
            Alert.alert('Error', 'Please provide at least a Code or Description');
            return;
        }
        if (coBlooms.length === 0) {
            Alert.alert('Error', 'Please select at least one Bloom\'s Level');
            return;
        }
        try {
            if (editingCoId) {
                await updateCO(editingCoId, { description: coText, code: coCode, blooms_levels: coBlooms });
            } else {
                await createCO(numId, { description: coText, code: coCode, blooms_levels: coBlooms });
            }
            setCoModal(false); setCoText(''); setCoCode(''); setCoBlooms(['Knowledge']); setEditingCoId(null);
            fetchAll();
        } catch (e) { Alert.alert('Error', 'Failed to save CO'); }
    };

    const openCoModal = (co?: any) => {
        if (co) {
            setEditingCoId(co.id);
            setCoText(co.description || '');
            setCoCode(co.code || '');
            setCoBlooms(co.blooms_levels || (co.blooms_level ? [co.blooms_level] : ['Knowledge']));
        } else {
            setEditingCoId(null);
            setCoText('');
            setCoCode('');
            setCoBlooms(['Knowledge']);
        }
        setCoModal(true);
    };

    const handleDeleteCO = async (id: number) => {
        if (Platform.OS === 'web') {
            if (window.confirm('Delete CO? This cannot be undone.')) {
                deleteCO(id).then(fetchAll).catch(console.error);
            }
            return;
        }
        Alert.alert('Delete CO?', 'This cannot be undone.', [
            { text: 'Cancel' },
            { text: 'Delete', style: 'destructive', onPress: async () => { await deleteCO(id); fetchAll(); } }
        ]);
    };

    // --- Sample Questions Actions ---
    const handleUploadSampleQuestions = async (topicId: number) => {
        try {
            const result = await DocumentPicker.getDocumentAsync({
                type: '*/*',
            });
            if (result.canceled) return;

            const file = result.assets[0];
            setUploadingSqTopicId(topicId);

            let formFile: any;
            if (Platform.OS === 'web' && (file as any).file) {
                formFile = (file as any).file;
            } else {
                formFile = { uri: file.uri, name: file.name, type: file.mimeType || 'application/octet-stream' } as any;
            }

            const res = await uploadSampleQuestions(topicId, formFile);
            Alert.alert('Success', res.message || `Imported ${res.count} questions`);
            fetchSampleQuestions(topicId);
        } catch (e: any) {
            Alert.alert('Error', e?.message || 'Failed to upload sample questions');
        } finally {
            setUploadingSqTopicId(null);
        }
    };

    // --- Mapping Actions ---
    const openMappingModal = (unit: any) => {
        setActiveUnitForMapping(unit);
        // Pre-select currently mapped COs
        const currentIds = new Set<number>(unit.mapped_cos?.map((c: any) => c.id as number) || []);
        setSelectedCOs(currentIds);
        setMappingModal(true);
    };

    const toggleCOSelection = (coId: number) => {
        const next = new Set(selectedCOs);
        if (next.has(coId)) next.delete(coId);
        else next.add(coId);
        setSelectedCOs(next);
    };

    const handleSaveMapping = async () => {
        if (!activeUnitForMapping) return;
        try {
            await updateUnitCOMapping(activeUnitForMapping.id, Array.from(selectedCOs));
            setMappingModal(false);
            fetchAll();
        } catch (e) { Alert.alert('Error', 'Failed to save mapping'); }
    };

    // --- Creation Handlers ---
    const handleCreateUnit = async () => {
        if (!unitName.trim() || !unitNumber.trim()) return;
        try {
            await createUnit(numId, unitName.trim(), parseInt(unitNumber));
            setUnitName(''); setUnitNumber(''); setUnitModal(false);
            fetchAll();
        } catch (e) { Alert.alert('Error', 'Failed to create unit'); }
    };

    const handleCreateTopic = async () => {
        if (!topicTitle.trim() || !activeUnitId) return;
        try {
            await createTopic(activeUnitId, topicTitle.trim());
            setTopicTitle(''); setTopicCreateModal(false); setActiveUnitId(null);
            fetchAll();
        } catch (e) { Alert.alert('Error', 'Failed to create topic'); }
    };


    if (loading) return <View className="flex-1 items-center justify-center"><ActivityIndicator color="#8B5CF6" /></View>;

    return (
        <AppBackground>
            <LinearGradient colors={['#3B82F6', '#2563EB']} className="pt-12 pb-6 px-6 rounded-b-[24px] shadow-sm z-10">
                <SafeAreaView edges={['top']}>
                    <View className="flex-row items-center mb-1">
                        <TouchableOpacity onPress={() => router.back()} className="mr-3 p-1">
                            <ArrowLeft size={24} color="white" />
                        </TouchableOpacity>
                        <View className="flex-1">
                            <Text className="text-white text-xl font-bold">{subject?.name}</Text>
                            <Text className="text-white/80 text-sm">{subject?.code}</Text>
                        </View>
                    </View>
                </SafeAreaView>
            </LinearGradient>

            {/* --- Tabs --- */}
            <View style={{ flexDirection: 'row', paddingHorizontal: 16, marginTop: 16, marginBottom: 16, gap: 12 }}>
                <TouchableOpacity
                    onPress={() => setActiveTab('content')}
                    style={{
                        flex: 1, padding: 12, borderRadius: 8, alignItems: 'center',
                        backgroundColor: activeTab === 'content' ? '#3B82F6' : '#F3F4F6',
                        borderWidth: 1, borderColor: activeTab === 'content' ? '#3B82F6' : '#E5E7EB'
                    }}
                >
                    <Text style={{ color: activeTab === 'content' ? 'white' : '#4B5563', fontWeight: 'bold' }}>Study Content</Text>
                </TouchableOpacity>
                <TouchableOpacity
                    onPress={() => setActiveTab('training')}
                    style={{
                        flex: 1, padding: 12, borderRadius: 8, alignItems: 'center',
                        backgroundColor: activeTab === 'training' ? '#3B82F6' : '#F3F4F6',
                        borderWidth: 1, borderColor: activeTab === 'training' ? '#3B82F6' : '#E5E7EB'
                    }}
                >
                    <Text style={{ color: activeTab === 'training' ? 'white' : '#4B5563', fontWeight: 'bold' }}>AI Training</Text>
                </TouchableOpacity>
            </View>

            {activeTab === 'training' ? (
                <TrainingDashboard subjectId={numId} />
            ) : (
                <ScrollView
                    refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchAll(); }} tintColor="#3B82F6" />}
                    contentContainerStyle={{ paddingBottom: 100 }}
                    style={{ paddingHorizontal: 16 }}
                >
                    {/* Status Cards */}
                    <View style={{ flexDirection: 'row', gap: 12, marginBottom: 24 }}>
                        <View style={{ flex: 1, padding: 16, borderRadius: 12, backgroundColor: 'white', borderColor: '#E5E7EB', borderWidth: 1, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 2 }}>
                            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                                <Database color="#3B82F6" size={20} />
                                <Text style={{ color: '#6B7280', fontSize: 12 }}>Study Material</Text>
                            </View>
                            <Text style={{ color: '#1F2937', fontSize: 24, fontWeight: 'bold' }}>{countMaterials()}</Text>
                            <Text style={{ color: '#9CA3AF', fontSize: 10 }}>Documents Uploaded</Text>
                        </View>

                        <View style={{ flex: 1, padding: 16, borderRadius: 12, backgroundColor: 'white', borderColor: '#E5E7EB', borderWidth: 1, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 2 }}>
                            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                                <Brain color={ragStatus?.ready ? "#10B981" : "#EF4444"} size={20} />
                                <Text style={{ color: '#6B7280', fontSize: 12 }}>RAG Status</Text>
                            </View>
                            <Text style={{ color: '#1F2937', fontSize: 14, fontWeight: 'bold' }}>
                                {ragStatus?.chunks > 0 ? `${ragStatus.chunks} Chunks` : 'No Context'}
                            </Text>
                            <Text style={{ color: ragStatus?.ready ? "#10B981" : "#EF4444", fontSize: 10 }}>
                                {ragStatus?.ready ? 'Ready for Gen' : 'Needs Upload'}
                            </Text>
                        </View>
                    </View>

                    {/* Added: Study Materials List */}
                    <View style={{ marginBottom: 24, backgroundColor: 'white', borderRadius: 12, padding: 16, borderWidth: 1, borderColor: '#E5E7EB', shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 2 }}>
                        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                            <FileText size={20} color="#3B82F6" />
                            <Text style={{ color: '#1F2937', fontSize: 16, fontWeight: 'bold' }}>Study Materials</Text>
                        </View>
                        {materials && materials.length > 0 ? (
                            materials.map((mat: any) => (
                                <View key={mat.id} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#F3F4F6' }}>
                                    <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                                        <View style={{ backgroundColor: '#DBEAFE', padding: 6, borderRadius: 8 }}>
                                            <FileText size={14} color="#2563EB" />
                                        </View>
                                        <View style={{ flex: 1 }}>
                                            <Text numberOfLines={1} style={{ color: '#374151', fontSize: 13, fontWeight: '500' }}>{mat.filename}</Text>
                                            <Text style={{ color: '#9CA3AF', fontSize: 10 }}>{mat.file_type.toUpperCase()} • {mat.chunk_count} chunks</Text>
                                        </View>
                                    </View>
                                    <TouchableOpacity onPress={() => handleDeleteMaterial(mat.id, mat.filename)} style={{ padding: 8 }}>
                                        <Trash size={16} color="#EF4444" />
                                    </TouchableOpacity>
                                </View>
                            ))
                        ) : (
                            <Text style={{ color: '#9CA3AF', fontSize: 12, textAlign: 'center', paddingVertical: 10 }}>No documents uploaded yet.</Text>
                        )}
                    </View>

                    {/* --- OBE MAPPING (Subject Level) --- */}
                    <View
                        style={{ padding: 16, marginBottom: 20, backgroundColor: 'white', borderRadius: 12, borderColor: '#E5E7EB', borderWidth: 1, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 2 }}
                    >
                        <TouchableOpacity
                            onPress={() => setCoExpanded(!coExpanded)}
                            style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}
                        >
                            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                                <BookOpen size={20} color="#3B82F6" />
                                <Text style={{ color: '#1F2937', fontSize: 16, fontWeight: 'bold' }}>Course Outcomes (COs)</Text>
                            </View>
                            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                                <TouchableOpacity onPress={() => openCoModal()} style={{ backgroundColor: '#F3F4F6', padding: 6, borderRadius: 6 }}>
                                    <Plus size={16} color="#4B5563" />
                                </TouchableOpacity>
                                {coExpanded ? <ChevronUp color="#4B5563" size={20} /> : <ChevronDown color="#4B5563" size={20} />}
                            </View>
                        </TouchableOpacity>

                        {coExpanded && (
                            <View style={{ marginTop: 12, borderTopWidth: 1, borderTopColor: '#F3F4F6', paddingTop: 12 }}>
                                {subject?.course_outcomes && subject.course_outcomes.length > 0 ? (
                                    subject.course_outcomes.map((co: any) => (
                                        <View key={co.id} style={{
                                            marginBottom: 10,
                                            backgroundColor: '#F9FAFB',
                                            borderRadius: 12,
                                            padding: 12,
                                            borderWidth: 1,
                                            borderColor: '#F3F4F6'
                                        }}>
                                            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                                                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                                                    <View style={{ width: 3, height: 14, backgroundColor: '#3B82F6', borderRadius: 2 }} />
                                                    <Text style={{ color: '#111827', fontWeight: 'bold', fontSize: 13 }}>{co.code}</Text>
                                                    <TouchableOpacity
                                                        onPress={() => Alert.alert(co.code, co.description || "No description provided")}
                                                        style={{ marginLeft: 4 }}
                                                    >
                                                        <Eye size={14} color="#6B7280" />
                                                    </TouchableOpacity>
                                                </View>

                                                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                                                    <TouchableOpacity onPress={() => openCoModal(co)}>
                                                        <Pencil size={14} color="#3B82F6" />
                                                    </TouchableOpacity>
                                                    <TouchableOpacity onPress={() => handleDeleteCO(co.id)}>
                                                        <Trash size={14} color="#EF4444" />
                                                    </TouchableOpacity>
                                                </View>
                                            </View>

                                            {/* Bloom's levels as small chips */}
                                            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4 }}>
                                                {(co.blooms_levels || (co.blooms_level ? [co.blooms_level] : [])).map((level: string) => (
                                                    <View key={level} style={{ backgroundColor: '#EFF6FF', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, borderWidth: 1, borderColor: '#DBEAFE' }}>
                                                        <Text style={{ color: '#2563EB', fontSize: 9, fontWeight: '600' }}>{level}</Text>
                                                    </View>
                                                ))}
                                            </View>
                                        </View>
                                    ))
                                ) : (
                                    <Text style={{ color: '#9CA3AF', fontSize: 11, fontStyle: 'italic', textAlign: 'center' }}>No COs defined. Add COs to enable mapping.</Text>
                                )}
                            </View>
                        )}
                    </View>

                    {/* Units Accordion */}
                    <Text style={{ color: '#4B5563', fontSize: 18, fontWeight: 'bold', marginBottom: 12 }}>Syllabus & Units</Text>

                    {subject?.units && subject.units.map((unit: any) => {
                        const isExpanded = expandedUnits.has(unit.id);
                        return (
                            <View key={unit.id} style={{ marginBottom: 12, backgroundColor: 'white', borderRadius: 8, overflow: 'hidden', borderWidth: 1, borderColor: '#E5E7EB', shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 2, elevation: 1 }}>
                                <TouchableOpacity
                                    onPress={() => toggleUnit(unit.id)}
                                    style={{ flexDirection: 'row', alignItems: 'center', padding: 16, backgroundColor: isExpanded ? '#F9FAFB' : 'white' }}
                                >
                                    <View style={{ flex: 1 }}>
                                        <Text style={{ color: '#1F2937', fontWeight: 'bold' }}>Unit {unit.unit_number}: {unit.name}</Text>
                                        <Text style={{ color: '#6B7280', fontSize: 11 }}>{unit.learning_outcomes?.length || 0} LOs • {unit.topics?.length || 0} Topics</Text>
                                    </View>
                                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                                        <TouchableOpacity onPress={() => openMappingModal(unit)}>
                                            <Database size={16} color={unit.mapped_cos?.length ? "#10B981" : "#9CA3AF"} />
                                        </TouchableOpacity>
                                        <TouchableOpacity onPress={() => handleDeleteUnit(unit.id)}>
                                            <Trash size={16} color="#EF4444" />
                                        </TouchableOpacity>
                                        {isExpanded ? <ChevronUp color="#4B5563" /> : <ChevronDown color="#4B5563" />}
                                    </View>
                                </TouchableOpacity>

                                {isExpanded && (
                                    <Animated.View entering={FadeInDown} style={{ padding: 12, borderTopWidth: 1, borderTopColor: '#F3F4F6' }}>
                                        {/* LO Section */}
                                        <View style={{ marginBottom: 16, backgroundColor: '#F3F4F6', borderRadius: 12, overflow: 'hidden' }}>
                                            <TouchableOpacity
                                                onPress={() => toggleLO(unit.id)}
                                                style={{ flexDirection: 'row', justifyContent: 'space-between', padding: 12, alignItems: 'center' }}
                                            >
                                                <Text style={{ color: '#3B82F6', fontSize: 11, fontWeight: 'bold' }}>Learning Outcomes (LOs)</Text>
                                                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                                                    <TouchableOpacity onPress={() => openLoModal(unit)}><Plus size={14} color="#3B82F6" /></TouchableOpacity>
                                                    {expandedLOs.has(unit.id) ? <ChevronUp size={14} color="#3B82F6" /> : <ChevronDown size={14} color="#3B82F6" />}
                                                </View>
                                            </TouchableOpacity>

                                            {expandedLOs.has(unit.id) && (
                                                <View style={{ paddingHorizontal: 12, paddingBottom: 12 }}>
                                                    {unit.learning_outcomes?.map((lo: any) => (
                                                        <View key={lo.id} style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4, backgroundColor: 'white', padding: 6, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: '#E5E7EB' }}>
                                                            <Text style={{ color: '#4B5563', fontSize: 10, flex: 1, lineHeight: 14 }}>
                                                                {lo.code && <Text style={{ color: '#2563EB', fontWeight: 'bold' }}>{lo.code}: </Text>}
                                                                {lo.description}
                                                            </Text>
                                                            <View style={{ flexDirection: 'row', gap: 6, marginLeft: 8 }}>
                                                                <TouchableOpacity onPress={() => openLoModal(unit, lo)}><Pencil size={10} color="#9CA3AF" /></TouchableOpacity>
                                                                <TouchableOpacity onPress={() => handleDeleteLO(lo.id)}><Trash size={10} color="#EF4444" /></TouchableOpacity>
                                                            </View>
                                                        </View>
                                                    ))}
                                                    {(!unit.learning_outcomes || unit.learning_outcomes.length === 0) && (
                                                        <Text style={{ color: '#9CA3AF', fontSize: 10, textAlign: 'center', fontStyle: 'italic' }}>No LOs defined for this unit.</Text>
                                                    )}
                                                </View>
                                            )}
                                        </View>

                                        {/* Topics List */}
                                        {unit.topics?.map((topic: any) => (
                                            <View key={topic.id} style={{ marginBottom: 12, paddingLeft: 8, borderLeftWidth: 2, borderLeftColor: '#E5E7EB' }}>
                                                <TouchableOpacity onPress={() => toggleTopic(topic.id)} style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 }}>
                                                    <Text style={{ color: '#374151', fontWeight: 'bold', fontSize: 13 }}>{topic.title}</Text>
                                                    <View style={{ flexDirection: 'row', gap: 12 }}>
                                                        <TouchableOpacity onPress={() => handleUploadMaterial(topic.id)}>
                                                            <Upload size={14} color="#10B981" />
                                                        </TouchableOpacity>
                                                        <TouchableOpacity onPress={() => handleDeleteTopic(topic.id)}>
                                                            <Trash size={14} color="#EF4444" />
                                                        </TouchableOpacity>
                                                    </View>
                                                </TouchableOpacity>

                                                {/* Topic Actions Bar */}
                                                {expandedTopics.has(topic.id) && (
                                                    <View style={{ marginTop: 8 }}>
                                                        <View style={{ marginBottom: 12 }}>
                                                            <TouchableOpacity onPress={() => openSyllabusModal(topic)} style={{ backgroundColor: '#DBEAFE', padding: 8, borderRadius: 6, alignItems: 'center', marginBottom: 8 }}>
                                                                <Text style={{ color: '#2563EB', fontSize: 11, fontWeight: 'bold' }}>Configure Bloom's Taxonomy</Text>
                                                            </TouchableOpacity>

                                                            {/* Upload Sample Questions File */}
                                                            <TouchableOpacity
                                                                onPress={() => handleUploadSampleQuestions(topic.id)}
                                                                disabled={uploadingSqTopicId === topic.id}
                                                                style={{ backgroundColor: uploadingSqTopicId === topic.id ? '#9CA3AF' : '#10B981', padding: 8, borderRadius: 6, alignItems: 'center', flexDirection: 'row', justifyContent: 'center', gap: 6 }}
                                                            >
                                                                <Upload size={14} color="white" />
                                                                <Text style={{ color: 'white', fontSize: 11, fontWeight: 'bold' }}>
                                                                    {uploadingSqTopicId === topic.id ? 'Uploading...' : 'Upload Sample Questions (PDF, DOCX, CSV, Excel)'}
                                                                </Text>
                                                            </TouchableOpacity>
                                                        </View>

                                                        {/* Display Uploaded Sample Question Files */}
                                                        {topicQuestions[topic.id] && topicQuestions[topic.id].length > 0 && (
                                                            <View style={{ padding: 8, backgroundColor: '#F9FAFB', borderRadius: 4, borderWidth: 1, borderColor: '#F3F4F6' }}>
                                                                <Text style={{ color: '#9CA3AF', fontSize: 10, marginBottom: 4 }}>Sample Questions ({topicQuestions[topic.id].length})</Text>
                                                                {[...new Set(topicQuestions[topic.id].map((sq: any) => sq.source_file).filter(Boolean))].map((fname, i) => (
                                                                    <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 2 }}>
                                                                        <FileText size={12} color="#6B7280" />
                                                                        <Text numberOfLines={1} style={{ color: '#4B5563', fontSize: 11 }}>{fname as string}</Text>
                                                                    </View>
                                                                ))}
                                                            </View>
                                                        )}
                                                    </View>
                                                )}
                                            </View>
                                        ))}

                                        <TouchableOpacity
                                            onPress={() => { setActiveUnitId(unit.id); setTopicCreateModal(true); }}
                                            style={{ marginTop: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: 8, borderStyle: 'dashed', borderWidth: 1, borderColor: '#D1D5DB', borderRadius: 6 }}
                                        >
                                            <Plus size={14} color="#9CA3AF" />
                                            <Text style={{ color: '#6B7280', fontSize: 12, marginLeft: 6 }}>Add Topic</Text>
                                        </TouchableOpacity>
                                    </Animated.View>
                                )}
                            </View>
                        );
                    })}

                    <TouchableOpacity
                        onPress={() => setUnitModal(true)}
                        style={{ backgroundColor: '#3B82F6', padding: 16, borderRadius: 8, flexDirection: 'row', justifyContent: 'center', alignItems: 'center', marginTop: 12 }}
                    >
                        <Plus color="white" style={{ marginRight: 8 }} />
                        <Text style={{ color: 'white', fontWeight: 'bold' }}>Add New Unit</Text>
                    </TouchableOpacity>

                </ScrollView>
            )}



            {/* Syllabus (Bloom's) Modal */}
            <Modal isVisible={syllabusModal} onBackdropPress={() => setSyllabusModal(false)} style={{ margin: 0 }}>
                <View className="flex-1 bg-white mt-12 rounded-t-[32px] overflow-hidden">
                    <LinearGradient colors={['#5eb0e5', '#3a8cc7']} className="p-6 flex-row justify-between items-center">
                        <View>
                            <Text className="text-xl font-bold text-white">Bloom's Taxonomy</Text>
                            <Text className="text-sm text-white/80">{activeTopicForSyllabus?.title}</Text>
                        </View>
                        <TouchableOpacity onPress={() => setSyllabusModal(false)} className="p-2 bg-white/20 rounded-full">
                            <X size={20} color="white" />
                        </TouchableOpacity>
                    </LinearGradient>
                    <ScrollView className="p-4" contentContainerStyle={{ paddingBottom: 40 }}>
                        <Text className="font-bold text-gray-700 mb-3">Cognitive Weightage</Text>
                        {Object.keys(bloomDistribution).map((level) => (
                            <View key={level} className="mb-4">
                                <View className="flex-row justify-between mb-1">
                                    <Text className="text-sm font-medium text-gray-700">{level}</Text>
                                    <Text className="text-sm font-bold text-blue-600">{bloomDistribution[level]}%</Text>
                                </View>
                                <Slider
                                    minimumValue={0} maximumValue={100} step={5}
                                    value={bloomDistribution[level]}
                                    onValueChange={(val) => setBloomDistribution(prev => ({ ...prev, [level]: val }))}
                                    minimumTrackTintColor="#3B82F6" maximumTrackTintColor="#E5E7EB" thumbTintColor="#3B82F6"
                                />
                            </View>
                        ))}
                    </ScrollView>
                    <View className="p-4 border-t border-gray-100">
                        <TouchableOpacity onPress={handleSaveSyllabus} className="bg-green-600 py-3 rounded-xl flex-row justify-center items-center">
                            <Save size={18} color="white" />
                            <Text className="text-white font-bold ml-2">Save Configuration</Text>
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>




            {/* Unit Create Modal (Centered) */}
            <Modal isVisible={unitModal} onBackdropPress={() => setUnitModal(false)} animationIn="fadeIn" animationOut="fadeOut">
                <View className="bg-white rounded-2xl mx-4 overflow-hidden shadow-lg">
                    <LinearGradient colors={['#8B5CF6', '#7C3AED']} className="px-6 py-4 flex-row justify-between items-center">
                        <Text className="text-white text-lg font-bold">Add Unit</Text>
                        <TouchableOpacity onPress={() => setUnitModal(false)}>
                            <X size={20} color="white" />
                        </TouchableOpacity>
                    </LinearGradient>
                    <View className="p-6">
                        <TextInput placeholder="Unit Name" value={unitName} onChangeText={setUnitName}
                            className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 mb-3 text-gray-800" />
                        <TextInput placeholder="Unit Number" value={unitNumber} onChangeText={setUnitNumber} keyboardType="numeric"
                            className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 mb-4 text-gray-800" />
                        <TouchableOpacity onPress={handleCreateUnit}>
                            <LinearGradient colors={['#8B5CF6', '#7C3AED']} className="py-3 rounded-lg items-center">
                                <Text className="text-white font-bold">Create</Text>
                            </LinearGradient>
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>

            {/* Topic Create Modal (Centered) */}
            <Modal isVisible={topicCreateModal} onBackdropPress={() => setTopicCreateModal(false)} animationIn="fadeIn" animationOut="fadeOut">
                <View className="bg-white rounded-2xl mx-4 overflow-hidden shadow-lg">
                    <LinearGradient colors={['#3B82F6', '#2563EB']} className="px-6 py-4 flex-row justify-between items-center">
                        <Text className="text-white text-lg font-bold">Add Topic</Text>
                        <TouchableOpacity onPress={() => setTopicCreateModal(false)}>
                            <X size={20} color="white" />
                        </TouchableOpacity>
                    </LinearGradient>
                    <View className="p-6">
                        <TextInput placeholder="Topic Title" value={topicTitle} onChangeText={setTopicTitle}
                            className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 mb-4 text-gray-800" />
                        <TouchableOpacity onPress={handleCreateTopic}>
                            <LinearGradient colors={['#3B82F6', '#2563EB']} className="py-3 rounded-lg items-center">
                                <Text className="text-white font-bold">Create</Text>
                            </LinearGradient>
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>

            {/* LO Create Modal (Centered) */}
            <Modal isVisible={loModal} onBackdropPress={() => setLoModal(false)} animationIn="fadeIn" animationOut="fadeOut">
                <View className="bg-white rounded-2xl mx-4 overflow-hidden shadow-lg">
                    <LinearGradient colors={['#A855F7', '#9333EA']} className="px-6 py-4 flex-row justify-between items-center">
                        <Text className="text-white text-lg font-bold">{editingLoId ? 'Edit LO' : 'Add Learning Outcome'}</Text>
                        <TouchableOpacity onPress={() => setLoModal(false)}>
                            <X size={20} color="white" />
                        </TouchableOpacity>
                    </LinearGradient>
                    <View className="p-6">
                        <Text className="text-gray-500 text-xs mb-1 font-medium">{activeUnitForLo?.name}</Text>
                        <TextInput placeholder="Code (e.g. LO-1)" value={loCode} onChangeText={setLoCode}
                            className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 mb-3 text-gray-800" />
                        <TextInput placeholder="Description" value={loText} onChangeText={setLoText} multiline numberOfLines={3}
                            className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 mb-4 text-gray-800 h-20 align-top" />
                        <TouchableOpacity onPress={handleCreateLO}>
                            <LinearGradient colors={['#A855F7', '#9333EA']} className="py-3 rounded-lg items-center">
                                <Text className="text-white font-bold">{editingLoId ? 'Save Changes' : 'Add LO'}</Text>
                            </LinearGradient>
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>

            {/* CO Create Modal (Centered) */}
            <Modal isVisible={coModal} onBackdropPress={() => setCoModal(false)} animationIn="fadeIn" animationOut="fadeOut">
                <View className="bg-white rounded-2xl mx-4 overflow-hidden shadow-lg">
                    <LinearGradient colors={['#2563EB', '#1D4ED8']} className="px-6 py-4 flex-row justify-between items-center">
                        <Text className="text-white text-lg font-bold">{editingCoId ? 'Edit CO' : 'Add Course Outcome'}</Text>
                        <TouchableOpacity onPress={() => setCoModal(false)}>
                            <X size={20} color="white" />
                        </TouchableOpacity>
                    </LinearGradient>
                    <View className="p-6">
                        <Text className="text-gray-500 text-xs mb-1 font-medium">{subject?.name}</Text>
                        <TextInput placeholder="Code (e.g. CO-1)" value={coCode} onChangeText={setCoCode}
                            className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 mb-3 text-gray-800" />

                        <Text className="text-xs font-bold text-gray-500 mb-1">Bloom's Levels (Select Multiple)</Text>
                        <ScrollView horizontal showsHorizontalScrollIndicator={false} className="mb-3">
                            {["Knowledge", "Comprehension", "Application", "Analysis", "Synthesis", "Evaluation"].map(level => {
                                const isSelected = coBlooms.includes(level);
                                return (
                                    <TouchableOpacity key={level} onPress={() => {
                                        if (isSelected) {
                                            if (coBlooms.length > 1) {
                                                setCoBlooms(coBlooms.filter(b => b !== level));
                                            } else {
                                                Alert.alert('Required', 'At least one Bloom\'s Level is required.');
                                            }
                                        } else {
                                            setCoBlooms([...coBlooms, level]);
                                        }
                                    }}
                                        className={`mr-2 px-3 py-1.5 rounded-full border ${isSelected ? 'bg-blue-100 border-blue-500' : 'bg-gray-50 border-gray-200'}`}>
                                        <Text className={`text-xs ${isSelected ? 'text-blue-700 font-bold' : 'text-gray-600'}`}>{level}</Text>
                                    </TouchableOpacity>
                                );
                            })}
                        </ScrollView>

                        <TextInput placeholder="Description" value={coText} onChangeText={setCoText} multiline numberOfLines={3}
                            className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 mb-4 text-gray-800 h-20 align-top" />
                        <TouchableOpacity onPress={handleCreateCO}>
                            <LinearGradient colors={['#2563EB', '#1D4ED8']} className="py-3 rounded-lg items-center">
                                <Text className="text-white font-bold">{editingCoId ? 'Save Changes' : 'Add CO'}</Text>
                            </LinearGradient>
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>
            {/* Mapping Modal (Centered) */}
            <Modal isVisible={mappingModal} onBackdropPress={() => setMappingModal(false)} animationIn="fadeIn" animationOut="fadeOut">
                <View className="bg-white rounded-2xl mx-4 overflow-hidden shadow-lg h-[80%]">
                    <LinearGradient colors={['#3B82F6', '#2563EB']} className="px-6 py-4 flex-row justify-between items-center">
                        <Text className="text-white text-lg font-bold">Map Course Outcomes</Text>
                        <TouchableOpacity onPress={() => setMappingModal(false)}>
                            <X size={20} color="white" />
                        </TouchableOpacity>
                    </LinearGradient>
                    <View className="p-4 bg-gray-50 border-b border-gray-100">
                        <Text className="text-gray-600 text-xs font-medium">Select COs to map to: <Text className="font-bold text-gray-800">{activeUnitForMapping?.name}</Text></Text>
                    </View>
                    <ScrollView className="flex-1 p-4">
                        {(!subject?.course_outcomes || subject.course_outcomes.length === 0) ? (
                            <Text className="text-gray-400 text-center italic py-10">No Course Outcomes available. Please add COs to the subject first.</Text>
                        ) : (
                            subject.course_outcomes.map((co: any) => {
                                const isSelected = selectedCOs.has(co.id);
                                return (
                                    <TouchableOpacity key={co.id} onPress={() => toggleCOSelection(co.id)}
                                        className={`mb-3 p-3 rounded-xl border ${isSelected ? 'bg-blue-50 border-blue-300' : 'bg-white border-gray-100'} flex-row items-center`}>
                                        <View className={`w-5 h-5 rounded border mr-3 items-center justify-center ${isSelected ? 'bg-blue-600 border-blue-600' : 'bg-white border-gray-300'}`}>
                                            {isSelected && <View className="w-2.5 h-2.5 rounded-sm bg-white" />}
                                        </View>
                                        <View className="flex-1">
                                            <View className="flex-row items-center mb-1">
                                                <Text className={`font-bold text-xs mr-2 ${isSelected ? 'text-blue-700' : 'text-gray-700'}`}>{co.code}</Text>
                                                <View className="bg-gray-100 px-1.5 py-0.5 rounded">
                                                    <Text className="text-[10px] text-gray-500">
                                                        {co.blooms_levels?.join('/') || co.blooms_level}
                                                    </Text>
                                                </View>
                                            </View>
                                            <Text className="text-sm text-gray-600">{co.description}</Text>
                                        </View>
                                    </TouchableOpacity>
                                );
                            })
                        )}
                    </ScrollView>
                    <View className="p-4 border-t border-gray-100 bg-white">
                        <TouchableOpacity onPress={handleSaveMapping}>
                            <LinearGradient colors={['#3B82F6', '#2563EB']} className="py-3 rounded-lg items-center">
                                <Text className="text-white font-bold">Save Mapping</Text>
                            </LinearGradient>
                        </TouchableOpacity>
                    </View>
                </View>
            </Modal>
        </AppBackground >
    );
}
