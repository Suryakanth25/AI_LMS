import React, { useEffect } from 'react';
import { View } from 'react-native';
import { Brain, Cpu } from 'lucide-react-native';
import Animated, { 
    useAnimatedStyle, 
    withRepeat, 
    withTiming, 
    withSequence, 
    useSharedValue,
    withDelay,
} from 'react-native-reanimated';

interface TheCouncilLogoProps {
    size?: number;
    color?: string;
    secondaryColor?: string;
}

export default function TheCouncilLogo({ 
    size = 60, 
    color = '#0D9488', 
    secondaryColor = '#2DD4BF' 
}: TheCouncilLogoProps) {
    const pulse = useSharedValue(1);
    const rotation1 = useSharedValue(0);
    const rotation2 = useSharedValue(0);
    const glow = useSharedValue(0.4);
    const auraScale = useSharedValue(1);

    useEffect(() => {
        // Breathing pulse effect
        pulse.value = withRepeat(
            withSequence(
                withTiming(1.08, { duration: 2500 }),
                withTiming(1, { duration: 2500 })
            ),
            -1,
            true
        );

        // Subtler, larger aura pulse
        auraScale.value = withRepeat(
            withSequence(
                withTiming(1.3, { duration: 4000 }),
                withTiming(1.1, { duration: 4000 })
            ),
            -1,
            true
        );

        // Orbit 1: clockwise
        rotation1.value = withRepeat(
            withTiming(360, { duration: 12000 }),
            -1,
            false
        );

        // Orbit 2: counter-clockwise
        rotation2.value = withRepeat(
            withTiming(-360, { duration: 18000 }),
            -1,
            false
        );

        // Flickering glow effect
        glow.value = withRepeat(
            withSequence(
                withTiming(0.6, { duration: 2000 }),
                withTiming(0.3, { duration: 2000 })
            ),
            -1,
            true
        );
    }, []);

    const brainStyle = useAnimatedStyle(() => ({
        transform: [{ scale: pulse.value }],
    }));

    const ringStyle1 = useAnimatedStyle(() => ({
        transform: [{ rotate: `${rotation1.value}deg` }],
    }));

    const ringStyle2 = useAnimatedStyle(() => ({
        transform: [{ rotate: `${rotation2.value}deg` }],
    }));

    const glowStyle = useAnimatedStyle(() => ({
        opacity: glow.value,
        transform: [{ scale: auraScale.value }],
    }));

    const innerSize = size * 0.65;
    const ringSize = size * 1.2;
    const innerRingSize = size * 0.95;

    return (
        <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
            {/* Inner Glow Core */}
            <Animated.View 
                style={[
                    { 
                        position: 'absolute', 
                        width: size * 0.7, 
                        height: size * 0.7, 
                        borderRadius: size, 
                        backgroundColor: color,
                        opacity: 0.15,
                    }
                ]} 
            />

            {/* Outer Aura */}
            <Animated.View 
                style={[
                    glowStyle,
                    { 
                        position: 'absolute', 
                        width: size, 
                        height: size, 
                        borderRadius: size, 
                        backgroundColor: secondaryColor,
                    }
                ]} 
            />

            {/* Outer Orbit (Dashed) */}
            <Animated.View style={[ringStyle1, { position: 'absolute' }]}>
                <View style={{ 
                    width: ringSize, 
                    height: ringSize, 
                    borderRadius: ringSize, 
                    borderWidth: 1, 
                    borderColor: color, 
                    borderStyle: 'dashed',
                    opacity: 0.3 
                }} />
                <View style={{ 
                    position: 'absolute', 
                    top: -3, 
                    left: ringSize/2 - 3, 
                    width: 6, 
                    height: 6, 
                    borderRadius: 3, 
                    backgroundColor: color 
                }} />
            </Animated.View>

            {/* Inner Orbit (Thin Line) */}
            <Animated.View style={[ringStyle2, { position: 'absolute' }]}>
                <View style={{ 
                    width: innerRingSize, 
                    height: innerRingSize, 
                    borderRadius: innerRingSize, 
                    borderWidth: 0.5, 
                    borderColor: secondaryColor,
                    opacity: 0.4
                }} />
                <View style={{ 
                    position: 'absolute', 
                    right: -2, 
                    top: innerRingSize/2 - 2, 
                    width: 4, 
                    height: 4, 
                    borderRadius: 2, 
                    backgroundColor: secondaryColor 
                }} />
            </Animated.View>

            {/* Central Brain Icon */}
            <Animated.View style={[brainStyle, { zIndex: 10 }]}>
                <Brain size={innerSize} color={color} strokeWidth={2.5} />
            </Animated.View>
        </View>
    );
}
