import React from 'react';
import { View, StyleSheet, ViewProps } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

export const AppBackground = ({ children, style, ...props }: ViewProps) => {
    return (
        <View style={[{ flex: 1 }, style]} {...props}>
            <View style={StyleSheet.absoluteFill} pointerEvents="none" className="z-0">
                <LinearGradient
                    colors={['#F0F9FF', '#F3E8FF', '#FFF1F2']}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 1 }}
                    style={StyleSheet.absoluteFill}
                />
                {/* Decorative gradients that act as 'blobs' */}
                <LinearGradient
                    colors={['rgba(168, 85, 247, 0.2)', 'transparent']}
                    style={{ position: 'absolute', top: -100, left: -100, width: 300, height: 300, borderRadius: 150 }}
                />
                <LinearGradient
                    colors={['rgba(59, 130, 246, 0.2)', 'transparent']}
                    style={{ position: 'absolute', top: 100, right: -100, width: 300, height: 300, borderRadius: 150 }}
                />
                <LinearGradient
                    colors={['rgba(16, 185, 129, 0.15)', 'transparent']}
                    style={{ position: 'absolute', bottom: 100, left: -50, width: 350, height: 350, borderRadius: 175 }}
                />
            </View>
            {children}
        </View>
    );
};
