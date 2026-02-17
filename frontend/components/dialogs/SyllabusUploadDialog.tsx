import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import Modal from 'react-native-modal';
import { X, Download, Upload, FileText } from 'lucide-react-native';
import * as DocumentPicker from 'expo-document-picker';
import { Colors } from '@/constants/Colors';
import { GradientButton } from '@/components/ui/GradientButton';

interface SyllabusUploadDialogProps {
    isVisible: boolean;
    onClose: () => void;
    onUpload: (file: any) => void;
}

export function SyllabusUploadDialog({ isVisible, onClose, onUpload }: SyllabusUploadDialogProps) {
    const [selectedFile, setSelectedFile] = useState<DocumentPicker.DocumentPickerAsset | null>(null);

    const pickDocument = async () => {
        try {
            const result = await DocumentPicker.getDocumentAsync({
                type: ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
            });

            if (!result.canceled && result.assets && result.assets.length > 0) {
                setSelectedFile(result.assets[0]);
            }
        } catch (err) {
            console.log('Document picker error', err);
        }
    };

    const handleUpload = () => {
        if (selectedFile) {
            onUpload(selectedFile);
            onClose();
            setSelectedFile(null); // Reset after upload
        }
    };

    return (
        <Modal
            isVisible={isVisible}
            onBackdropPress={onClose}
            onBackButtonPress={onClose}
            style={{ margin: 0, justifyContent: 'flex-end' }}
            avoidKeyboard
        >
            <View className="bg-white rounded-t-3xl p-6 min-h-[50%]">
                <View className="flex-row justify-between items-center mb-6">
                    <Text className="text-xl font-bold text-gray-900">Upload Syllabus</Text>
                    <TouchableOpacity onPress={onClose} className="p-2 bg-gray-100 rounded-full">
                        <X size={20} color={Colors.text.primary} />
                    </TouchableOpacity>
                </View>

                <ScrollView className="flex-1">
                    <View className="bg-blue-50 p-4 rounded-lg mb-6 border border-blue-100">
                        <Text className="text-blue-800 font-medium mb-1">Requirements</Text>
                        <Text className="text-blue-600 text-sm">
                            Upload the syllabus document (PDF, DOCX) to define the scope for question generation.
                        </Text>
                    </View>

                    <TouchableOpacity
                        activeOpacity={0.7}
                        className="flex-row items-center justify-center p-4 border border-gray-300 rounded-lg mb-6 bg-gray-50 border-dashed"
                        onPress={() => { /* Mock download */ alert('Template Downloaded'); }}
                    >
                        <Download size={20} color={Colors.primary[1]} className="mr-2" />
                        <Text className="text-gray-700 font-medium">Download Template</Text>
                    </TouchableOpacity>

                    <View className="mb-6">
                        <Text className="text-gray-700 font-medium mb-2">Select File</Text>
                        <TouchableOpacity
                            onPress={pickDocument}
                            className="h-32 border-2 border-dashed border-gray-300 rounded-xl items-center justify-center bg-gray-50"
                        >
                            {selectedFile ? (
                                <View className="items-center">
                                    <FileText size={40} color={Colors.primary[1]} className="mb-2" />
                                    <Text className="text-gray-900 font-medium">{selectedFile.name}</Text>
                                    <Text className="text-gray-500 text-xs">{(selectedFile.size! / 1024).toFixed(1)} KB</Text>
                                </View>
                            ) : (
                                <View className="items-center">
                                    <Upload size={32} color={Colors.text.secondary} className="mb-2" />
                                    <Text className="text-gray-500">Tap to browse files</Text>
                                </View>
                            )}
                        </TouchableOpacity>
                    </View>
                </ScrollView>

                <View className="mt-4 safe-mb">
                    <GradientButton
                        title="Upload Syllabus"
                        onPress={handleUpload}
                        disabled={!selectedFile}
                        colors={Colors.success} // Green gradient for syllabus/update as requested (or yellow for update)
                    // Request said: "Upload Syllabus or Update Syllabus yellow or green gradient"
                    />
                </View>
            </View>
        </Modal>
    );
}
