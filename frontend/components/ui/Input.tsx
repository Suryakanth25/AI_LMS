import React from 'react';
import { View, TextInput, Text, TextInputProps } from 'react-native';
import clsx from 'clsx';
import { Colors } from '@/constants/Colors';

interface InputProps extends TextInputProps {
    label?: string;
    error?: string;
    icon?: React.ReactNode;
    containerClassName?: string;
}

export function Input({ label, error, icon, containerClassName, className, ...props }: InputProps) {
    return (
        <View className={clsx("w-full", containerClassName)}>
            {label && <Text className="text-gray-700 font-medium mb-1 ml-1">{label}</Text>}
            <View className={clsx(
                "flex-row items-center bg-gray-50 border rounded-lg px-3 py-2",
                error ? "border-red-500" : "border-gray-300",
                "focus:border-blue-500" // Note: focus styles in RN/NativeWind might need explicit handling or 'focus-within' on parent
            )}>
                {icon && <View className="mr-2">{icon}</View>}
                <TextInput
                    className={clsx("flex-1 text-gray-900 text-base", className)}
                    placeholderTextColor={Colors.text.secondary}
                    {...props}
                />
            </View>
            {error && <Text className="text-red-500 text-sm mt-1 ml-1">{error}</Text>}
        </View>
    );
}
