import React, { useEffect } from 'react';
import { View } from 'react-native';
import { Brain } from 'lucide-react-native';
import Animated, { 
    useAnimatedStyle, 
    withRepeat, 
    withTiming, 
    withSequence, 
    useSharedValue,
    Easing,
    interpolate
} from 'react-native-reanimated';

interface TheCouncilUltimateLogoProps {
    size?: number;
    primaryColor?: string;
    accentColor?: string;
}

export default function TheCouncilUltimateLogo({ 
    size = 80, 
    primaryColor = '#8B5CF6', 
    accentColor = '#06B6D4' 
}: TheCouncilUltimateLogoProps) {
    const pulse = useSharedValue(1);
    const rotation = useSharedValue(0);

    useEffect(() => {
        pulse.value = withRepeat(
            withSequence(
                withTiming(1.1, { duration: 2500 }),
                withTiming(1, { duration: 2500 })
            ),
            -1,
            true
        );

        rotation.value = withRepeat(
            withTiming(360, { duration: 20000, easing: Easing.linear }),
            -1,
            false
        );
    }, []);

    const coreStyle = useAnimatedStyle(() => ({
        transform: [{ scale: pulse.value }],
    }));

    const systemStyle = useAnimatedStyle(() => ({
        transform: [{ rotate: `${rotation.value}deg` }],
    }));

    // A simpler, more robust way to render the 7 nodes
    const renderAgents = () => {
        return [0, 1, 2, 3, 4, 5, 6].map((i) => {
            const angle = (i * 360) / 7;
            const radius = size * 0.42;
            
            return (
                <View 
                    key={i}
                    style={{
                        position: 'absolute',
                        width: size,
                        height: size,
                        alignItems: 'center',
                        justifyContent: 'center',
                        transform: [{ rotate: `${angle}deg` }]
                    }}
                >
                    <View 
                        style={{
                            width: size * 0.08,
                            height: size * 0.08,
                            borderRadius: size * 0.04,
                            backgroundColor: i % 2 === 0 ? primaryColor : accentColor,
                            transform: [{ translateY: -radius }]
                        }}
                    />
                </View>
            );
        });
    };

    return (
        <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
            {/* Background Glow */}
            <Animated.View 
                style={[
                    coreStyle,
                    { 
                        position: 'absolute', 
                        width: size * 0.8, 
                        height: size * 0.8, 
                        borderRadius: size, 
                        backgroundColor: primaryColor,
                        opacity: 0.15,
                    }
                ]} 
            />

            {/* Rotating Agent System */}
            <Animated.View style={[systemStyle, { position: 'absolute', width: size, height: size }]}>
                {renderAgents()}
                
                {/* Orbital Ring */}
                <View style={{ 
                    position: 'absolute',
                    top: size * 0.08,
                    left: size * 0.08,
                    width: size * 0.84, 
                    height: size * 0.84, 
                    borderRadius: size, 
                    borderWidth: 1, 
                    borderColor: primaryColor, 
                    borderStyle: 'dashed',
                    opacity: 0.2 
                }} />
            </Animated.View>

            {/* The Intelligence Core */}
            <Animated.View style={[coreStyle, { zIndex: 10, alignItems: 'center', justifyContent: 'center' }]}>
                <View style={{ 
                    position: 'absolute', 
                    width: size * 0.45, 
                    height: size * 0.45, 
                    borderRadius: size * 0.22, 
                    backgroundColor: accentColor, 
                    opacity: 0.2 
                }} />
                <Brain 
                    size={size * 0.4} 
                    color={primaryColor} 
                    strokeWidth={2.5} 
                />
            </Animated.View>
        </View>
    );
}
