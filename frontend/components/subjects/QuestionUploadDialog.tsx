import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Modal, Platform } from 'react-native';
import { X, FileText, Check, Upload, Download, ChevronDown, ChevronUp } from 'lucide-react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, { FadeInDown } from 'react-native-reanimated';

interface QuestionUploadDialogProps {
    visible: boolean;
    onClose: () => void;
    topicTitle: string;
}

export const QuestionUploadDialog = ({ visible, onClose, topicTitle }: QuestionUploadDialogProps) => {
    const [expandedSection, setExpandedSection] = useState<'MCQ' | 'Essay' | 'Short' | null>('MCQ');
    const [files, setFiles] = useState<{ [key: string]: boolean }>({ MCQ: false, Essay: false, Short: false });

    const toggleSection = (section: 'MCQ' | 'Essay' | 'Short') => {
        setExpandedSection(expandedSection === section ? null : section);
    };

    const handleSimulatedUpload = (type: string) => {
        setFiles(prev => ({ ...prev, [type]: true }));
    };

    return (
        <Modal visible={visible} animationType="slide" transparent={true} onRequestClose={onClose}>
            <View className="flex-1 bg-black/50 justify-end sm:justify-center">
                <View className="bg-white w-full h-[90%] sm:h-[80%] sm:w-[500px] sm:self-center rounded-t-3xl sm:rounded-2xl overflow-hidden shadow-2xl">

                    {/* Header */}
                    <LinearGradient colors={['#3B82F6', '#2563EB']} className="p-6 pb-8">
                        <View className="flex-row justify-between items-start">
                            <View>
                                <Text className="text-white text-xl font-bold">Upload Questions</Text>
                                <Text className="text-white/80 text-sm mt-1">{topicTitle}</Text>
                            </View>
                            <TouchableOpacity onPress={onClose} className="bg-white/20 p-2 rounded-full">
                                <X size={20} color="white" />
                            </TouchableOpacity>
                        </View>
                    </LinearGradient>

                    <ScrollView className="flex-1 -mt-4 bg-gray-50 rounded-t-[24px] px-5 pt-6">

                        {/* Info Banner */}
                        <View className="bg-yellow-50 border border-yellow-200 p-4 rounded-xl mb-6 flex-row gap-3">
                            <FileText size={24} color="#EAB308" className="mt-1" />
                            <View className="flex-1">
                                <Text className="text-yellow-800 font-bold mb-1">OBE Question Upload</Text>
                                <Text className="text-yellow-700 text-xs">
                                    Upload CSV or Excel files containing your question bank. Ensure you follow the templates provided.
                                </Text>
                            </View>
                        </View>

                        {/* Sections */}
                        {[{ id: 'MCQ', color: 'blue', label: 'Multiple Choice Questions' }, { id: 'Essay', color: 'purple', label: 'Essays / Long Answer' }, { id: 'Short', color: 'green', label: 'Short Notes' }].map((item) => (
                            <View key={item.id} className="bg-white rounded-xl border border-gray-200 mb-4 overflow-hidden">
                                <TouchableOpacity
                                    onPress={() => toggleSection(item.id as any)}
                                    className="p-4 flex-row items-center justify-between bg-white active:bg-gray-50"
                                >
                                    <View className="flex-row items-center gap-3">
                                        <View className={`w-10 h-10 rounded-full items-center justify-center bg-${item.color}-100`}>
                                            <Upload size={20} color={item.color === 'blue' ? '#2563EB' : item.color === 'purple' ? '#9333EA' : '#16A34A'} />
                                        </View>
                                        <View>
                                            <Text className="font-bold text-gray-800">{item.id}</Text>
                                            <Text className="text-xs text-gray-500">{item.label}</Text>
                                        </View>
                                    </View>
                                    <View className="flex-row items-center gap-3">
                                        {files[item.id] && <Check size={18} color="#22C55E" />}
                                        {expandedSection === item.id ? <ChevronUp size={20} color="#9CA3AF" /> : <ChevronDown size={20} color="#9CA3AF" />}
                                    </View>
                                </TouchableOpacity>

                                {expandedSection === item.id && (
                                    <View className="p-4 border-t border-gray-100 bg-gray-50/50">
                                        <TouchableOpacity className="flex-row items-center justify-center py-2 px-4 bg-green-100 rounded-lg mb-4 border border-green-200">
                                            <Download size={16} color="#16A34A" className="mr-2" />
                                            <Text className="text-green-700 font-bold text-sm">Download {item.id} Template</Text>
                                        </TouchableOpacity>

                                        <TouchableOpacity
                                            onPress={() => handleSimulatedUpload(item.id)}
                                            className="h-32 border-2 border-dashed border-gray-300 rounded-xl items-center justify-center bg-white mb-4"
                                        >
                                            <Text className="text-gray-400 font-medium text-sm">Tap to pick file</Text>
                                            {files[item.id] && <Text className="text-green-600 font-bold mt-2">File Selected!</Text>}
                                        </TouchableOpacity>

                                        <TouchableOpacity
                                            disabled={!files[item.id]}
                                            className={`py-3 rounded-xl items-center ${files[item.id] ? `bg-${item.color}-600` : 'bg-gray-300'}`}
                                        >
                                            <Text className="text-white font-bold">Upload {item.id} Questions</Text>
                                        </TouchableOpacity>
                                    </View>
                                )}
                            </View>
                        ))}

                        <View className="h-20" />
                    </ScrollView>

                    {/* Footer */}
                    <View className="p-4 border-t border-gray-100 bg-white shadow-lg">
                        <Text className="text-center text-gray-500 font-medium">
                            {Object.values(files).filter(Boolean).length} files ready
                        </Text>
                    </View>

                </View>
            </View>
        </Modal>
    );
};
