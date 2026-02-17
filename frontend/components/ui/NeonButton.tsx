import React from 'react';
import { Text, TouchableOpacity, ActivityIndicator, View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring, withTiming } from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';
import { clsx } from 'clsx';

interface NeonButtonProps {
    onPress: () => void;
    title: string;
    icon?: React.ReactNode;
    loading?: boolean;
    disabled?: boolean;
    colors?: string[]; // [primary, secondary]
    className?: string;
    textClassName?: string;
    glowColor?: string;
}

const AnimatedTouchable = Animated.createAnimatedComponent(TouchableOpacity);

export function NeonButton({
    onPress,
    title,
    icon,
    loading = false,
    disabled = false,
    colors = ['#8B5CF6', '#C026D3'], // Violet to Fuchsia default
    className,
    textClassName,
    glowColor = '#8B5CF6'
}: NeonButtonProps) {
    const scale = useSharedValue(1);
    const opacity = useSharedValue(1);

    const animatedStyle = useAnimatedStyle(() => ({
        transform: [{ scale: scale.value }],
        opacity: opacity.value,
    }));

    const handlePressIn = () => {
        scale.value = withSpring(0.95);
        opacity.value = withTiming(0.8, { duration: 100 });
    };

    const handlePressOut = () => {
        scale.value = withSpring(1);
        opacity.value = withTiming(1, { duration: 100 });
    };

    return (
        <AnimatedTouchable
            onPress={onPress}
            onPressIn={handlePressIn}
            onPressOut={handlePressOut}
            disabled={disabled || loading}
            style={[
                animatedStyle,
                {
                    shadowColor: colors[0],
                    shadowOffset: { width: 0, height: 2 },
                    shadowOpacity: 0.2,
                    shadowRadius: 4,
                    elevation: 3,
                }
            ]}
            className={clsx("rounded-xl", className)}
        >
            <LinearGradient
                colors={disabled ? ['#9CA3AF', '#6B7280'] : (colors as [string, string, ...string[]])}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                className="px-6 py-3.5 rounded-xl flex-row items-center justify-center space-x-2"
            >
                {loading ? (
                    <ActivityIndicator color="white" />
                ) : (
                    <>
                        {icon}
                        <Text className={clsx("text-white font-bold text-sm tracking-wide uppercase", textClassName)}>
                            {title}
                        </Text>
                    </>
                )}
            </LinearGradient>
        </AnimatedTouchable>
    );
}
