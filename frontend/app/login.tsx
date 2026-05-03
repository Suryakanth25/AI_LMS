import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, KeyboardAvoidingView, Platform, ScrollView, ActivityIndicator } from 'react-native';
import { useAuth } from '../context/AuthContext';
import { Lock, Mail, User, ArrowRight, BookOpen } from 'lucide-react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, { FadeInUp, FadeInDown } from 'react-native-reanimated';

// Auto-detect the backend IP from Expo's dev server exactly like api.ts
import Constants from 'expo-constants';
function getApiBase(): string {
    const debuggerHost = Constants.expoConfig?.hostUri || (Constants as any).manifest?.debuggerHost || (Constants as any).manifest2?.extra?.expoGo?.debuggerHost;
    if (debuggerHost) {
        const ip = debuggerHost.split(':')[0];
        return `http://${ip}:8000`;
    }
    if (Platform.OS === 'web') return 'http://localhost:8000';
    return 'http://10.0.2.2:8000';
}
const API_BASE = getApiBase();

import TheCouncilUltimateLogo from '../components/TheCouncilUltimateLogo';

export default function LoginScreen() {
    const { signIn } = useAuth();
    const [isLogin, setIsLogin] = useState(true);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [name, setName] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async () => {
        setError('');
        if (!email || !password || (!isLogin && !name)) {
            setError('Please fill in all fields');
            return;
        }

        setLoading(true);
        try {
            if (isLogin) {
                // Login
                const formData = new URLSearchParams();
                formData.append('username', email);
                formData.append('password', password);

                const res = await fetch(`${API_BASE}/auth/token`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData.toString()
                });

                if (!res.ok) throw new Error('Invalid email or password');
                const data = await res.json();
                await signIn(data.access_token);
            } else {
                // Register
                const res = await fetch(`${API_BASE}/auth/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, email, password })
                });

                if (!res.ok) {
                    const data = await res.json();
                    throw new Error(data.detail || 'Registration failed');
                }
                
                // Switch to login automatically
                setIsLogin(true);
                setEmail('');    // Clear email
                setPassword(''); // Clear password
                setError('Registration successful! Please sign in.');
            }
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <KeyboardAvoidingView 
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            className="flex-1 bg-white"
        >
            <ScrollView contentContainerStyle={{ flexGrow: 1 }} keyboardShouldPersistTaps="handled">
                <View className="flex-1 px-6 justify-center pb-12 pt-20">
                    
                    <Animated.View entering={FadeInDown.delay(100)} className="items-center mb-10">
                        <View className="w-24 h-24 bg-purple-50 rounded-[32px] items-center justify-center mb-6 shadow-sm border border-purple-100">
                            <TheCouncilUltimateLogo size={70} primaryColor="#7C3AED" accentColor="#A78BFA" />
                        </View>
                        <Text className="text-3xl font-bold text-gray-900 mb-2 text-center">
                            {isLogin ? 'Welcome Back' : 'Join The Council'}
                        </Text>
                        <Text className="text-gray-500 text-base text-center px-4">
                            {isLogin 
                                ? 'Sign in to access your subjects and question banks.' 
                                : 'Create an account to start generating intelligent assessments.'}
                        </Text>
                    </Animated.View>

                    <Animated.View entering={FadeInUp.delay(200)} className="bg-white rounded-3xl p-6 shadow-sm border border-gray-100">
                        
                        {!isLogin && (
                            <View className="mb-4">
                                <Text className="text-gray-700 font-bold text-sm mb-2 ml-1">Full Name</Text>
                                <View className="flex-row items-center bg-gray-50 rounded-xl px-4 py-3 border border-gray-200">
                                    <User size={20} color="#9CA3AF" />
                                    <TextInput 
                                        className="flex-1 ml-3 text-base text-gray-800"
                                        placeholder="Professor Name"
                                        placeholderTextColor="#9CA3AF"
                                        value={name}
                                        onChangeText={setName}
                                        autoCapitalize="words"
                                    />
                                </View>
                            </View>
                        )}

                        <View className="mb-4">
                            <Text className="text-gray-700 font-bold text-sm mb-2 ml-1">Email Address</Text>
                            <View className="flex-row items-center bg-gray-50 rounded-xl px-4 py-3 border border-gray-200">
                                <Mail size={20} color="#9CA3AF" />
                                <TextInput 
                                    className="flex-1 ml-3 text-base text-gray-800"
                                    placeholder="faculty@university.edu"
                                    placeholderTextColor="#9CA3AF"
                                    value={email}
                                    onChangeText={setEmail}
                                    keyboardType="email-address"
                                    autoCapitalize="none"
                                />
                            </View>
                        </View>

                        <View className="mb-6">
                            <Text className="text-gray-700 font-bold text-sm mb-2 ml-1">Password</Text>
                            <View className="flex-row items-center bg-gray-50 rounded-xl px-4 py-3 border border-gray-200">
                                <Lock size={20} color="#9CA3AF" />
                                <TextInput 
                                    className="flex-1 ml-3 text-base text-gray-800"
                                    placeholder="••••••••"
                                    placeholderTextColor="#9CA3AF"
                                    value={password}
                                    onChangeText={setPassword}
                                    secureTextEntry
                                />
                            </View>
                        </View>

                        {error ? (
                            <Text className={`text-center mb-4 font-medium ${error.includes('successful') ? 'text-green-600' : 'text-red-500'}`}>
                                {error}
                            </Text>
                        ) : null}

                        <TouchableOpacity onPress={handleSubmit} disabled={loading} className="mb-6 shadow-sm">
                            <LinearGradient 
                                colors={['#a78bfa', '#7c3aed']} 
                                start={{x: 0, y: 0}} end={{x: 1, y: 0}}
                                className="py-4 rounded-xl flex-row items-center justify-center"
                            >
                                {loading ? (
                                    <ActivityIndicator color="white" />
                                ) : (
                                    <>
                                        <Text className="text-white font-bold text-lg mr-2">
                                            {isLogin ? 'Sign In' : 'Create Account'}
                                        </Text>
                                        <ArrowRight size={20} color="white" />
                                    </>
                                )}
                            </LinearGradient>
                        </TouchableOpacity>

                        <View className="flex-row justify-center items-center">
                            <Text className="text-gray-500">
                                {isLogin ? "Don't have an account? " : "Already have an account? "}
                            </Text>
                            <TouchableOpacity onPress={() => { setIsLogin(!isLogin); setError(''); }}>
                                <Text className="text-purple-600 font-bold">
                                    {isLogin ? 'Sign Up' : 'Log In'}
                                </Text>
                            </TouchableOpacity>
                        </View>

                    </Animated.View>
                </View>
            </ScrollView>
        </KeyboardAvoidingView>
    );
}
