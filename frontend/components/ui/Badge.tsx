import React from 'react';
import { View, Text } from 'react-native';
import clsx from 'clsx';
import { Colors } from '@/constants/Colors';

interface BadgeProps {
    label: string | number;
    color?: string; // bg color class or hex? Let's use Tailwind bg classes or style
    icon?: React.ReactNode;
    className?: string;
    variant?: 'default' | 'outline' | 'ghost';
}

export function Badge({ label, icon, className, variant = 'default' }: BadgeProps) {
    // Determine styles based on variant
    const containerClasses = clsx(
        "flex-row items-center px-3 py-1 rounded-full",
        variant === 'default' && "bg-gray-200",
        variant === 'outline' && "border border-gray-300",
        className
    );

    return (
        <View className={containerClasses}>
            {icon && <View className="mr-1">{icon}</View>}
            <Text className="text-gray-700 font-medium text-xs">{label}</Text>
        </View>
    );
}
