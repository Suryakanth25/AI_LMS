import React from 'react';
import { Text, TouchableOpacity, ActivityIndicator, ViewStyle, StyleProp } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Colors } from '@/constants/Colors';
import clsx from 'clsx';

interface GradientButtonProps {
    onPress?: () => void;
    title: string;
    colors?: readonly [string, string, ...string[]];
    disabled?: boolean;
    loading?: boolean;
    className?: string;
    textClassName?: string;
    icon?: React.ReactNode;
    style?: StyleProp<ViewStyle>;
}

export function GradientButton({
    onPress,
    title,
    colors = Colors.primary,
    disabled = false,
    loading = false,
    className = '',
    textClassName = '',
    icon,
    style,
}: GradientButtonProps) {
    const activeColors = disabled ? ['#d1d5db', '#9ca3af', '#6b7280'] : colors;

    return (
        <TouchableOpacity
            onPress={onPress}
            disabled={disabled || loading}
            activeOpacity={0.8}
            className={clsx("rounded-lg", className)}
            style={[
                {
                    shadowColor: "#000",
                    shadowOffset: { width: 0, height: 2 },
                    shadowOpacity: 0.25,
                    shadowRadius: 3.84,
                    elevation: 5,
                },
                style
            ]}
        >
            <LinearGradient
                colors={activeColors as [string, string, ...string[]]}
                start={{ x: 0, y: 0 }}
                end={{ x: 0, y: 1 }} // Top to bottom gradient
                className="px-6 py-3 rounded-lg border border-white/20 items-center flex-row justify-center space-x-2"
            >
                {/* Inset top highlight */}
                <View className="absolute top-0 left-0 right-0 h-[1px] bg-white/40 rounded-t-lg" />

                {loading ? (
                    <ActivityIndicator color="white" />
                ) : (
                    <>
                        {icon}
                        <Text
                            className={clsx("text-white font-bold uppercase tracking-wider text-center", textClassName)}
                            style={{ textShadowColor: 'rgba(0, 0, 0, 0.2)', textShadowOffset: { width: 0, height: 1 }, textShadowRadius: 2 }}
                        >
                            {title}
                        </Text>
                    </>
                )}
            </LinearGradient>
        </TouchableOpacity>
    );
}

// Helper View for inset highlight, since I used it inside. 
// Actually I need to import View.
import { View } from 'react-native'; 
