import React, { useState, useCallback } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { LogOut, Layout, Database, BookOpen, Sparkles, User } from 'lucide-react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, { FadeInDown, FadeInUp } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AppBackground } from '@/components/ui/AppBackground';
import { useAuth } from '@/context/AuthContext';
import { useFocusEffect } from '@react-navigation/native';
import { getProfile } from '@/services/api';
import TheCouncilUltimateLogo from '@/components/TheCouncilUltimateLogo';

export default function HomeScreen() {
    const { signOut } = useAuth();
    const router = useRouter();
    const [profile, setProfile] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchProfile = async () => {
        try {
            setError(null);
            const data = await getProfile();
            setProfile(data);
        } catch (e: any) {
            setError('Could not connect to server');
        } finally {
            setLoading(false);
        }
    };

    useFocusEffect(
        useCallback(() => {
            fetchProfile();
        }, [])
    );

    const handleLogout = () => {
        Alert.alert('Sign Out', 'Are you sure you want to log out?', [
            { text: 'Cancel', style: 'cancel' },
            { 
                text: 'Log Out', 
                style: 'destructive', 
                onPress: () => {
                    signOut();
                } 
            },
        ]);
    };

    const getGreeting = () => {
        const hour = new Date().getHours();
        if (hour < 12) return 'Good Morning';
        if (hour < 17) return 'Good Afternoon';
        return 'Good Evening';
    };

    return (
        <AppBackground>
            <LinearGradient
                colors={['#0D9488', '#0F766E']}
                className="pt-12 pb-6 px-6 rounded-b-[24px] shadow-sm z-10"
            >
                <SafeAreaView edges={['top']}>
                    <View className="flex-row items-center justify-between">
                        {profile ? (
                            <Animated.View entering={FadeInDown}>
                                <Text className="text-teal-100 text-xs font-medium">
                                    {getGreeting()},
                                </Text>
                                <Text className="text-white text-xl font-bold">
                                    Prof. {profile.name.split(' ')[0]}
                                </Text>
                            </Animated.View>
                        ) : (
                            <View>
                                <Text className="text-white text-xl font-bold">Home</Text>
                                <Text className="text-white/80 text-sm">Welcome to The Council</Text>
                            </View>
                        )}
                        <TouchableOpacity
                            onPress={handleLogout}
                            className="w-10 h-10 rounded-full bg-white/20 items-center justify-center"
                        >
                            <LogOut size={20} color="white" />
                        </TouchableOpacity>
                    </View>
                </SafeAreaView>
            </LinearGradient>

            <ScrollView className="flex-1 px-4 pt-6" contentContainerStyle={{ paddingBottom: 100 }}>
                {loading ? (
                    <View className="flex-1 items-center justify-center py-20">
                        <ActivityIndicator size="large" color="#0D9488" />
                    </View>
                ) : error ? (
                    <View className="flex-1 items-center justify-center py-20">
                        <Text className="text-red-500 font-bold text-lg">⚠️ Connection Error</Text>
                        <Text className="text-gray-500 mt-2 text-center">{error}</Text>
                        <TouchableOpacity onPress={fetchProfile} className="mt-4 bg-teal-600 px-6 py-2 rounded-lg">
                            <Text className="text-white font-bold">Retry</Text>
                        </TouchableOpacity>
                    </View>
                ) : profile && (
                    <>
                        <Text className="text-gray-800 font-bold text-lg mb-4 ml-2">Quick Stats</Text>
                        
                        <View className="flex-row gap-4 mb-8">
                            <Animated.View entering={FadeInUp.delay(100)} className="flex-1 bg-white rounded-2xl p-5 shadow-sm border border-teal-50 items-center">
                                <View className="w-12 h-12 bg-teal-50 rounded-xl items-center justify-center mb-3">
                                    <BookOpen size={24} color="#0D9488" />
                                </View>
                                <Text className="text-3xl font-bold text-gray-900">{profile.total_subjects}</Text>
                                <Text className="text-gray-500 text-xs mt-1">Subjects</Text>
                            </Animated.View>

                            <Animated.View entering={FadeInUp.delay(200)} className="flex-1 bg-white rounded-2xl p-5 shadow-sm border border-teal-50 items-center">
                                <View className="w-12 h-12 bg-amber-50 rounded-xl items-center justify-center mb-3">
                                    <Sparkles size={24} color="#D97706" />
                                </View>
                                <Text className="text-3xl font-bold text-gray-900">{profile.total_questions_generated}</Text>
                                <Text className="text-gray-500 text-xs mt-1 text-center">Questions</Text>
                            </Animated.View>
                        </View>

                        <Text className="text-gray-800 font-bold text-lg mb-4 ml-2">Account Info</Text>

                        <Animated.View entering={FadeInUp.delay(300)} className="bg-white rounded-3xl p-5 shadow-sm border border-gray-100 mb-8">
                            <View className="flex-row items-center">
                                <View className="w-14 h-14 bg-teal-50 rounded-2xl items-center justify-center">
                                    <TheCouncilUltimateLogo size={45} primaryColor="#0D9488" accentColor="#06B6D4" />
                                </View>
                                <View className="ml-4">
                                    <Text className="text-gray-900 font-bold text-base">{profile.name}</Text>
                                    <Text className="text-gray-500 text-sm">{profile.email}</Text>
                                </View>
                            </View>
                        </Animated.View>
                    </>
                )}
            </ScrollView>
        </AppBackground>
    );
}
