import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Modal, TextInput } from 'react-native';
import { X, Book, FileText, Check } from 'lucide-react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Slider from '@react-native-community/slider';

interface SyllabusUploadDialogProps {
    visible: boolean;
    onClose: () => void;
    topicTitle: string;
}

const BLOOM_LEVELS = [
    { id: '1', name: 'Knowledge', color: '#3B82F6', default: 40 },
    { id: '2', name: 'Comprehension', color: '#A855F7', default: 20 },
    { id: '3', name: 'Application', color: '#06B6D4', default: 20 },
    { id: '4', name: 'Analysis', color: '#F59E0B', default: 10 },
    { id: '5', name: 'Synthesis', color: '#22C55E', default: 5 },
    { id: '6', name: 'Evaluation', color: '#EF4444', default: 5 },
];

export const SyllabusUploadDialog = ({ visible, onClose, topicTitle }: SyllabusUploadDialogProps) => {
    const [selectedLOs, setSelectedLOs] = useState<string[]>([]);
    const [weights, setWeights] = useState(BLOOM_LEVELS.reduce((acc, curr) => ({ ...acc, [curr.name]: curr.default }), {}));
    const [fileUploaded, setFileUploaded] = useState(false);

    const toggleLO = (lo: string) => {
        if (selectedLOs.includes(lo)) {
            setSelectedLOs(selectedLOs.filter(l => l !== lo));
        } else {
            setSelectedLOs([...selectedLOs, lo]);
        }
    };

    const updateWeight = (name: string, val: number) => {
        setWeights(prev => ({ ...prev, [name]: val }));
    };

    const totalWeight = Object.values(weights).reduce((a: any, b: any) => a + b, 0);

    return (
        <Modal visible={visible} animationType="slide" transparent={true} onRequestClose={onClose}>
            <View className="flex-1 bg-black/50 justify-end sm:justify-center">
                <View className="bg-white w-full h-[95%] sm:h-[85%] sm:w-[500px] sm:self-center rounded-t-3xl sm:rounded-2xl overflow-hidden shadow-2xl">

                    {/* Header */}
                    <LinearGradient colors={['#059669', '#10B981']} className="p-6 pb-8">
                        <View className="flex-row justify-between items-start">
                            <View>
                                <Text className="text-white text-xl font-bold">Update Syllabus</Text>
                                <Text className="text-white/80 text-sm mt-1">{topicTitle}</Text>
                            </View>
                            <TouchableOpacity onPress={onClose} className="bg-white/20 p-2 rounded-full">
                                <X size={20} color="white" />
                            </TouchableOpacity>
                        </View>
                    </LinearGradient>

                    <ScrollView className="flex-1 -mt-4 bg-gray-50 rounded-t-[24px] px-5 pt-6">

                        {/* File Upload Area */}
                        <TouchableOpacity
                            onPress={() => setFileUploaded(true)}
                            className="h-24 border-2 border-dashed border-gray-300 rounded-xl items-center justify-center bg-white mb-6"
                        >
                            <View className="flex-row items-center gap-2">
                                <FileText size={20} color="#6B7280" />
                                <Text className="text-gray-600 font-medium">
                                    {fileUploaded ? 'syllabus_v1.pdf' : 'Tap to upload Syllabus content'}
                                </Text>
                            </View>
                            {fileUploaded && <Text className="text-green-600 text-xs mt-1">Ready for parsing</Text>}
                        </TouchableOpacity>

                        {/* Learning Outcomes */}
                        <View className="mb-8">
                            <Text className="text-gray-800 font-bold mb-3">Map Learning Outcomes</Text>
                            <View className="flex-row flex-wrap gap-2">
                                {['LO1', 'LO2', 'LO3', 'LO4', 'LO5'].map((lo) => (
                                    <TouchableOpacity
                                        key={lo}
                                        onPress={() => toggleLO(lo)}
                                        className={`px-4 py-2 rounded-full border ${selectedLOs.includes(lo) ? 'bg-blue-100 border-blue-500' : 'bg-white border-gray-200'}`}
                                    >
                                        <View className="flex-row items-center gap-1">
                                            {selectedLOs.includes(lo) && <Check size={14} color="#2563EB" />}
                                            <Text className={`${selectedLOs.includes(lo) ? 'text-blue-700 font-bold' : 'text-gray-600'}`}>{lo}</Text>
                                        </View>
                                    </TouchableOpacity>
                                ))}
                            </View>
                        </View>

                        {/* Cognitive Weightage */}
                        <View className="mb-6">
                            <View className="flex-row justify-between items-center mb-4">
                                <Text className="text-gray-800 font-bold">Cognitive Weightage</Text>
                                <View className={`px-2 py-1 rounded-md ${totalWeight === 100 ? 'bg-green-100' : 'bg-red-100'}`}>
                                    <Text className={`font-bold text-xs ${totalWeight === 100 ? 'text-green-700' : 'text-red-700'}`}>
                                        Total: {totalWeight}%
                                    </Text>
                                </View>
                            </View>

                            {BLOOM_LEVELS.map((level) => (
                                <View key={level.id} className="mb-4">
                                    <View className="flex-row justify-between mb-1">
                                        <Text className="text-gray-600 text-xs font-medium" style={{ color: level.color }}>{level.name}</Text>
                                        <Text className="text-gray-800 text-xs font-bold">{(weights as any)[level.name]}%</Text>
                                    </View>
                                    <Slider
                                        style={{ width: '100%', height: 20 }}
                                        minimumValue={0}
                                        maximumValue={100}
                                        step={5}
                                        value={(weights as any)[level.name]}
                                        onValueChange={(val) => updateWeight(level.name, val)}
                                        minimumTrackTintColor={level.color}
                                        maximumTrackTintColor="#E5E7EB"
                                        thumbTintColor={level.color}
                                    />
                                </View>
                            ))}
                        </View>

                        <View className="h-24" />

                    </ScrollView>

                    {/* Footer */}
                    <View className="p-4 border-t border-gray-100 bg-white shadow-lg">
                        <TouchableOpacity
                            disabled={totalWeight !== 100}
                            className={`py-4 rounded-xl items-center shadow-sm ${totalWeight === 100 ? 'bg-emerald-600' : 'bg-gray-300'}`}
                            onPress={onClose}
                        >
                            <Text className="text-white font-bold text-lg">Save Mapping</Text>
                        </TouchableOpacity>
                    </View>

                </View>
            </View>
        </Modal>
    );
};
