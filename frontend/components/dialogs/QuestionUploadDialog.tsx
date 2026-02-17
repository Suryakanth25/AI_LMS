import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import Modal from 'react-native-modal';
import { X, Download, Upload, ChevronDown, ChevronUp, FileText } from 'lucide-react-native';
import * as DocumentPicker from 'expo-document-picker';
import { Colors } from '@/constants/Colors';
import { GradientButton } from '@/components/ui/GradientButton';

interface QuestionUploadDialogProps {
    isVisible: boolean;
    onClose: () => void;
    topicName?: string;
    onUpload: (files: { type: string, file: any }[]) => void;
}

export function QuestionUploadDialog({ isVisible, onClose, topicName, onUpload }: QuestionUploadDialogProps) {
    const [expandedSection, setExpandedSection] = useState<string | null>('MCQ');
    const [files, setFiles] = useState<{ [key: string]: DocumentPicker.DocumentPickerAsset | null }>({
        MCQ: null,
        Essay: null,
        Short: null
    });

    const questionTypes = ['MCQ', 'Essay', 'Short Note'];

    const pickDocument = async (type: string) => {
        try {
            const result = await DocumentPicker.getDocumentAsync({
                type: ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/csv'], // Excel/CSV for questions typically
            });

            if (!result.canceled && result.assets && result.assets.length > 0) {
                setFiles(prev => ({ ...prev, [type]: result.assets![0] }));
            }
        } catch (err) {
            console.log('Document picker error', err);
        }
    };

    const handleUpload = () => {
        const filesToUpload = Object.entries(files)
            .filter(([_, file]) => file !== null)
            .map(([type, file]) => ({ type, file }));

        if (filesToUpload.length > 0) {
            onUpload(filesToUpload);
            onClose();
            setFiles({ MCQ: null, Essay: null, Short: null }); // Reset
        }
    };

    const toggleSection = (type: string) => {
        setExpandedSection(expandedSection === type ? null : type);
    };

    const totalFilesReady = Object.values(files).filter(f => f !== null).length;

    return (
        <Modal
            isVisible={isVisible}
            onBackdropPress={onClose}
            onBackButtonPress={onClose}
            style={{ margin: 0, justifyContent: 'flex-end' }}
            avoidKeyboard
        >
            <View className="bg-white rounded-t-3xl p-6 h-[70%]">
                <View className="flex-row justify-between items-center mb-4">
                    <View>
                        <Text className="text-xl font-bold text-gray-900">Upload Questions</Text>
                        {topicName && <Text className="text-gray-500 text-sm">Topic: {topicName}</Text>}
                    </View>
                    <TouchableOpacity onPress={onClose} className="p-2 bg-gray-100 rounded-full">
                        <X size={20} color={Colors.text.primary} />
                    </TouchableOpacity>
                </View>

                <View className="bg-blue-50 p-3 rounded-lg mb-4 border border-blue-100">
                    <Text className="text-blue-700 text-xs">
                        Download templates for each question type, fill them, and upload here.
                    </Text>
                </View>

                <ScrollView className="flex-1" showsVerticalScrollIndicator={false}>
                    {questionTypes.map((type) => (
                        <View key={type} className="mb-4 border border-gray-200 rounded-xl overflow-hidden">
                            <TouchableOpacity
                                className="flex-row items-center justify-between p-4 bg-gray-50"
                                onPress={() => toggleSection(type)}
                            >
                                <Text className="font-bold text-gray-800">{type} Questions</Text>
                                {expandedSection === type ? <ChevronUp size={20} color="gray" /> : <ChevronDown size={20} color="gray" />}
                            </TouchableOpacity>

                            {expandedSection === type && (
                                <View className="p-4 bg-white">
                                    <TouchableOpacity
                                        className="flex-row items-center mb-4"
                                        onPress={() => alert(`${type} Template Downloaded`)}
                                    >
                                        <Download size={16} color={Colors.primary[1]} className="mr-2" />
                                        <Text className="text-blue-600 font-medium text-sm">Download {type} Template</Text>
                                    </TouchableOpacity>

                                    <TouchableOpacity
                                        onPress={() => pickDocument(type)}
                                        className="h-24 border border-dashed border-gray-300 rounded-lg items-center justify-center bg-gray-50"
                                    >
                                        {files[type] ? (
                                            <View className="items-center flex-row">
                                                <FileText size={24} color={Colors.success[1]} className="mr-2" />
                                                <View>
                                                    <Text className="text-gray-900 font-medium text-sm" numberOfLines={1}>{files[type]?.name}</Text>
                                                </View>
                                                <TouchableOpacity onPress={() => setFiles(prev => ({ ...prev, [type]: null }))} className="ml-2">
                                                    <X size={16} color="red" />
                                                </TouchableOpacity>
                                            </View>
                                        ) : (
                                            <View className="items-center flex-row">
                                                <Upload size={20} color={Colors.text.secondary} className="mr-2" />
                                                <Text className="text-gray-400 text-sm">Upload File</Text>
                                            </View>
                                        )}
                                    </TouchableOpacity>
                                </View>
                            )}
                        </View>
                    ))}
                </ScrollView>

                <View className="mt-4 pt-4 border-t border-gray-100 safe-mb">
                    <Text className="text-center text-gray-500 text-xs mb-2">{totalFilesReady} files ready to upload</Text>
                    <GradientButton
                        title="Upload Questions"
                        onPress={handleUpload}
                        disabled={totalFilesReady === 0}
                        colors={Colors.primary}
                    />
                </View>
            </View>
        </Modal>
    );
}
