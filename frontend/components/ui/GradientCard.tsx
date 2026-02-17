import React from 'react';
import { View, ViewStyle, StyleProp } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Colors } from '@/constants/Colors';

interface GradientCardProps {
    children: React.ReactNode;
    variant?: 'default' | 'elevated';
    className?: string;
    style?: StyleProp<ViewStyle>;
    colors?: readonly [string, string, ...string[]];
}

export function GradientCard({
    children,
    variant = 'default',
    className = '',
    style,
    colors = Colors.card.background
}: GradientCardProps) {
    return (
        <LinearGradient
            colors={colors as [string, string, ...string[]]}
            start={{ x: 0, y: 0 }}
            end={{ x: 0, y: 1 }}
            className={`rounded-lg border border-gray-400 p-4 ${className}`}
            style={[
                {
                    shadowColor: Colors.card.shadow,
                    shadowOffset: { width: 0, height: 2 },
                    shadowOpacity: 0.2,
                    shadowRadius: 6,
                    elevation: 4,
                },
                style
            ]}
        >
            {/* Inset top highlight overlay */}
            <View className="absolute top-0 left-0 right-0 h-[1px] bg-white opacity-90 rounded-t-lg" />
            {children}
        </LinearGradient>
    );
}
