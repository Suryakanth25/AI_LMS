import React from 'react';
import { View, StyleSheet, Dimensions } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

const { width, height } = Dimensions.get('window');

export const VisionBackground = () => {
    return (
        <View style={StyleSheet.absoluteFill} pointerEvents="none" className="z-0 bg-[#0f172a]">
            {/* Deep Base Gradient (Night Sky / Deep Ocean) */}
            <LinearGradient
                colors={['#0284c7', '#0f172a', '#1e1b4b']} // Sky-600 -> Slate-900 -> Indigo-950
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={StyleSheet.absoluteFill}
            />

            {/* Ambient Glows/Orbs to create depth behind the glass */}

            {/* Top Right Orb (Cyan/Teal) */}
            <LinearGradient
                colors={['rgba(56, 189, 248, 0.4)', 'transparent']}
                style={{
                    position: 'absolute',
                    top: -100,
                    right: -50,
                    width: width * 1.2,
                    height: width * 1.2,
                    borderRadius: width * 0.6,
                    opacity: 0.6,
                }}
            />

            {/* Bottom Left Orb (Purple/Indigo) */}
            <LinearGradient
                colors={['rgba(129, 140, 248, 0.3)', 'transparent']}
                style={{
                    position: 'absolute',
                    bottom: -100,
                    left: -100,
                    width: width * 1.5,
                    height: width * 1.5,
                    borderRadius: width * 0.75,
                    opacity: 0.5,
                }}
            />

            {/* Subtle Mesh Overlay (Optional, simulating noise/texture if needed easily, skipping for now) */}
        </View>
    );
};
