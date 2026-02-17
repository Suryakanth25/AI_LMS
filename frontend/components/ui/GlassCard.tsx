import React from 'react';
import { View, Text, ViewProps } from 'react-native';
import { BlurView } from 'expo-blur';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface GlassCardProps extends ViewProps {
    className?: string;
    variant?: 'light' | 'dark';
    intensity?: number;
}

export function GlassCard({ children, className, variant = 'light', intensity = 0, ...props }: GlassCardProps) {
    const containerClasses = twMerge(
        clsx(
            "rounded-xl overflow-hidden border",
            variant === 'light' ? "border-white/40 bg-white/70 shadow-sm" : "border-gray-700/40 bg-black/20",
            className
        )
    );

    return (
        <View className={containerClasses} {...props}>
            {intensity > 0 ? (
                <BlurView
                    intensity={intensity}
                    tint={variant === 'light' ? 'light' : 'dark'}
                    className="flex-1"
                >
                    <View className="flex-1">
                        {children}
                    </View>
                </BlurView>
            ) : (
                <View className="flex-1">
                    {children}
                </View>
            )}
        </View>
    );
}
