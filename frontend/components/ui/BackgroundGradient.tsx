import React from 'react';
import { View, StyleSheet, Dimensions } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

const { width, height } = Dimensions.get('window');

export const BackgroundGradient = () => {
    return (
        <View style={StyleSheet.absoluteFill} pointerEvents="none" className="z-0">
            {/* Main Background Base */}
            <LinearGradient
                colors={['#F0F9FF', '#F3E8FF', '#FFF1F2']}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={StyleSheet.absoluteFill}
            />

            {/* Decorative Blobs */}
            <LinearGradient
                colors={['rgba(168, 85, 247, 0.15)', 'transparent']}
                style={{
                    position: 'absolute',
                    top: -100,
                    left: -100,
                    width: width * 0.8,
                    height: width * 0.8,
                    borderRadius: width * 0.4,
                }}
            />

            <LinearGradient
                colors={['rgba(59, 130, 246, 0.15)', 'transparent']}
                style={{
                    position: 'absolute',
                    top: height * 0.2,
                    right: -50,
                    width: width * 0.7,
                    height: width * 0.7,
                    borderRadius: width * 0.35,
                }}
            />

            <LinearGradient
                colors={['rgba(16, 185, 129, 0.1)', 'transparent']}
                style={{
                    position: 'absolute',
                    bottom: -50,
                    left: -50,
                    width: width * 0.9,
                    height: width * 0.9,
                    borderRadius: width * 0.45,
                }}
            />
        </View>
    );
};
