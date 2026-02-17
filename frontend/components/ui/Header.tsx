import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { ChevronLeft } from 'lucide-react-native';
import { Colors } from '@/constants/Colors';

interface HeaderProps {
    title: string;
    subtitle?: string;
    showBack?: boolean;
    rightElement?: React.ReactNode;
}

export function Header({ title, subtitle, showBack = false, rightElement }: HeaderProps) {
    const router = useRouter();

    return (
        <View className="flex-row items-center justify-between px-4 py-3 bg-white border-b border-gray-200">
            <View className="flex-row items-center flex-1">
                {showBack && (
                    <TouchableOpacity
                        onPress={() => router.back()}
                        className="mr-3 p-1 rounded-full bg-gray-100/50"
                    >
                        <ChevronLeft size={24} color={Colors.text.primary} />
                    </TouchableOpacity>
                )}
                <View className="flex-1">
                    <Text className="text-lg font-bold text-gray-900" numberOfLines={1}>{title}</Text>
                    {subtitle && (
                        <Text className="text-sm text-gray-500" numberOfLines={1}>{subtitle}</Text>
                    )}
                </View>
            </View>
            {rightElement && (
                <View className="ml-2">
                    {rightElement}
                </View>
            )}
        </View>
    );
}
