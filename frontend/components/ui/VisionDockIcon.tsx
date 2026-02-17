import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { VisionGlassCard } from './VisionGlassCard';

interface VisionDockIconProps {
    icon: React.ReactNode;
    label: string;
    delay: number;
    onPress: () => void;
}

export function VisionDockIcon({ icon, label, delay, onPress }: VisionDockIconProps) {
    return (
        <Animated.View
            entering={FadeInDown.delay(delay).springify()}
            className="items-center gap-3"
        >
            <TouchableOpacity
                onPress={onPress}
                activeOpacity={0.7}
                className="items-center group"
            >
                {/* Glass Icon Container */}
                <View className="w-20 h-20 rounded-[24px] overflow-hidden border border-white/40 shadow-lg bg-white/20">
                    <LinearGradient
                        colors={['rgba(255,255,255,0.4)', 'rgba(255,255,255,0.1)']}
                        className="flex-1 items-center justify-center"
                    >
                        {icon}
                    </LinearGradient>
                </View>

                {/* Label with Shadow for Readability */}
                <Text
                    className="text-[13px] font-semibold text-white mt-2 tracking-wide text-center"
                    style={{ textShadowColor: 'rgba(0,0,0,0.3)', textShadowOffset: { width: 0, height: 1 }, textShadowRadius: 4 }}
                >
                    {label}
                </Text>
            </TouchableOpacity>
        </Animated.View>
    );
}
