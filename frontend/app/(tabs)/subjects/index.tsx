import React, { useState, useCallback } from 'react';
import { View, Text, ScrollView, TouchableOpacity, Alert, TextInput, ActivityIndicator, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import { Plus, Trash, FileText, Database } from 'lucide-react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AppBackground } from '@/components/ui/AppBackground';
import Modal from 'react-native-modal';
import { getSubjects, createSubject, deleteSubject } from '@/services/api';
import { useFocusEffect } from '@react-navigation/native';

export default function SubjectsScreen() {
    const router = useRouter();
    const [subjects, setSubjects] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [modalVisible, setModalVisible] = useState(false);
    const [newName, setNewName] = useState('');
    const [newCode, setNewCode] = useState('');
    const [creating, setCreating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchSubjects = async () => {
        try {
            setError(null);
            const data = await getSubjects();
            setSubjects(data);
        } catch (e: any) {
            setError('Could not connect to server');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useFocusEffect(
        useCallback(() => {
            fetchSubjects();
        }, [])
    );

    const onRefresh = () => {
        setRefreshing(true);
        fetchSubjects();
    };

    const handleCreate = async () => {
        if (!newName.trim() || !newCode.trim()) {
            Alert.alert('Error', 'Name and code are required');
            return;
        }
        setCreating(true);
        try {
            await createSubject(newName.trim(), newCode.trim());
            setNewName('');
            setNewCode('');
            setModalVisible(false);
            fetchSubjects();
        } catch (e) {
            Alert.alert('Error', 'Failed to create subject');
        } finally {
            setCreating(false);
        }
    };

    const handleDelete = (id: number, name: string) => {
        Alert.alert('Delete Subject', `Delete "${name}" and all its data?`, [
            { text: 'Cancel', style: 'cancel' },
            {
                text: 'Delete', style: 'destructive', onPress: async () => {
                    try {
                        await deleteSubject(id);
                        fetchSubjects();
                    } catch (e) {
                        Alert.alert('Error', 'Failed to delete');
                    }
                }
            },
        ]);
    };

    return (
        <AppBackground>
            <LinearGradient
                colors={['#3B82F6', '#2563EB']}
                className="pt-12 pb-6 px-6 rounded-b-[24px] shadow-sm z-10"
            >
                <SafeAreaView edges={['top']}>
                    <View className="flex-row items-center justify-between">
                        <View>
                            <Text className="text-white text-xl font-bold">Subjects</Text>
                            <Text className="text-white/80 text-sm">Manage courses & materials</Text>
                        </View>
                        <TouchableOpacity
                            onPress={() => setModalVisible(true)}
                            className="w-10 h-10 rounded-full bg-white/20 items-center justify-center"
                        >
                            <Plus size={22} color="white" />
                        </TouchableOpacity>
                    </View>
                </SafeAreaView>
            </LinearGradient>

            <ScrollView
                className="flex-1 px-4 pt-4"
                contentContainerStyle={{ paddingBottom: 100 }}
                refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
            >
                {loading ? (
                    <View className="flex-1 items-center justify-center py-20">
                        <ActivityIndicator size="large" color="#3a8cc7" />
                        <Text className="text-gray-500 mt-3">Loading subjects...</Text>
                    </View>
                ) : error ? (
                    <View className="flex-1 items-center justify-center py-20">
                        <Text className="text-red-500 font-bold text-lg">⚠️ Connection Error</Text>
                        <Text className="text-gray-500 mt-2 text-center">{error}</Text>
                        <TouchableOpacity onPress={fetchSubjects} className="mt-4 bg-blue-500 px-6 py-2 rounded-lg">
                            <Text className="text-white font-bold">Retry</Text>
                        </TouchableOpacity>
                    </View>
                ) : subjects.length === 0 ? (
                    <View className="flex-1 items-center justify-center py-20">
                        <Text className="text-gray-400 text-6xl mb-4">📚</Text>
                        <Text className="text-gray-600 font-bold text-lg">No Subjects Yet</Text>
                        <Text className="text-gray-400 mt-1">Tap + to create your first subject</Text>
                    </View>
                ) : (
                    subjects.map((subject, idx) => (
                        <Animated.View key={subject.id} entering={FadeInDown.delay(idx * 80)}>
                            <TouchableOpacity
                                onPress={() => router.push(`/(tabs)/subjects/${subject.id}`)}
                                onLongPress={() => handleDelete(subject.id, subject.name)}
                                className="bg-white rounded-xl border border-gray-100 shadow-sm mb-3 overflow-hidden"
                            >
                                <View className="p-4">
                                    <View className="flex-row items-center justify-between mb-2">
                                        <View className="flex-1">
                                            <Text className="font-bold text-gray-800 text-base">{subject.name}</Text>
                                            <Text className="text-gray-500 text-xs mt-0.5">{subject.code}</Text>
                                        </View>
                                        <TouchableOpacity
                                            onPress={() => handleDelete(subject.id, subject.name)}
                                            className="p-2"
                                        >
                                            <Trash size={16} color="#EF4444" />
                                        </TouchableOpacity>
                                    </View>
                                    <View className="flex-row gap-2 mt-1">
                                        <View className="flex-row items-center bg-blue-50 px-2.5 py-1 rounded-full">
                                            <FileText size={12} color="#3B82F6" />
                                            <Text className="text-blue-600 font-medium text-xs ml-1">
                                                Materials: {subject.material_count || 0}
                                            </Text>
                                        </View>
                                        <View className="flex-row items-center bg-purple-50 px-2.5 py-1 rounded-full">
                                            <Database size={12} color="#8B5CF6" />
                                            <Text className="text-purple-600 font-medium text-xs ml-1">
                                                Units: {subject.unit_count || 0}
                                            </Text>
                                        </View>
                                        <View className="flex-row items-center bg-green-50 px-2.5 py-1 rounded-full">
                                            <Text className="text-green-600 font-medium text-xs">
                                                Topics: {subject.topic_count || 0}
                                            </Text>
                                        </View>
                                    </View>
                                </View>
                            </TouchableOpacity>
                        </Animated.View>
                    ))
                )}
            </ScrollView>

            {/* Create Subject Modal */}
            <Modal isVisible={modalVisible} onBackdropPress={() => setModalVisible(false)} backdropOpacity={0.5} style={{ margin: 0 }}>
                <View className="flex-1 justify-end">
                    <View className="bg-white rounded-t-[32px] overflow-hidden">
                        <LinearGradient colors={['#5eb0e5', '#3a8cc7']} className="px-6 py-4 flex-row justify-between items-center">
                            <Text className="text-white text-xl font-bold">New Subject</Text>
                            <TouchableOpacity onPress={() => setModalVisible(false)} className="p-2 bg-white/20 rounded-full">
                                <Plus size={20} color="white" style={{ transform: [{ rotate: '45deg' }] }} />
                            </TouchableOpacity>
                        </LinearGradient>

                        <View className="p-6">
                            <Text className="text-gray-500 text-sm mb-1 ml-1 font-medium">Subject Name</Text>
                            <TextInput
                                placeholder="e.g., Data Structures"
                                value={newName}
                                onChangeText={setNewName}
                                className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3.5 mb-4 text-gray-800 text-base"
                                placeholderTextColor="#9CA3AF"
                            />

                            <Text className="text-gray-500 text-sm mb-1 ml-1 font-medium">Subject Code</Text>
                            <TextInput
                                placeholder="e.g., CS301"
                                value={newCode}
                                onChangeText={setNewCode}
                                className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3.5 mb-6 text-gray-800 text-base"
                                placeholderTextColor="#9CA3AF"
                                autoCapitalize="characters"
                            />

                            <TouchableOpacity onPress={handleCreate} disabled={creating}>
                                <LinearGradient
                                    colors={['#3B82F6', '#2563EB']}
                                    style={{ borderRadius: 16 }} className="py-4 items-center shadow-md shadow-blue-200"
                                >
                                    {creating ? (
                                        <ActivityIndicator color="white" />
                                    ) : (
                                        <Text className="text-white font-bold text-lg">Create Subject</Text>
                                    )}
                                </LinearGradient>
                            </TouchableOpacity>
                            <View className="h-6" />
                        </View>
                    </View>
                </View>
            </Modal>
        </AppBackground>
    );
}
