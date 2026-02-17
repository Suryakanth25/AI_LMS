import React from 'react';
import { View, ViewProps, Platform } from 'react-native';
import { BlurView } from 'expo-blur';
import { LinearGradient } from 'expo-linear-gradient';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface VisionGlassCardProps extends ViewProps {
    className?: string;
    intensity?: number;
    gradientColors?: [string, string, ...string[]];
}

export function VisionGlassCard({
    children,
    className,
    intensity = 40,
    gradientColors = ['rgba(255,255,255,0.2)', 'rgba(255,255,255,0.05)'], // Subtle top-to-bottom fade
    ...props
}: VisionGlassCardProps) {

    const containerClasses = twMerge(
        clsx(
            "rounded-[30px] overflow-hidden border border-white/30",
            className
        )
    );

    return (
        <View className={containerClasses} {...props}>
            {/* Gradient Overlay for "Sheen" */}
            <LinearGradient
                colors={gradientColors}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={{ position: 'absolute', width: '100%', height: '100%' }}
            />

            {/* Blur Effect */}
            {Platform.OS === 'ios' ? (
                <BlurView
                    intensity={intensity}
                    tint="light"
                    className="flex-1"
                >
                    <View className="flex-1 p-4">
                        {children}
                    </View>
                </BlurView>
            ) : (
                /* Android Fallback: Solid semi-transparent background since BlurView can be unstable */
                <View className="flex-1 p-4 bg-white/10 backdrop-blur-md">
                    {children}
                </View>
            )}
        </View>
    );
}
