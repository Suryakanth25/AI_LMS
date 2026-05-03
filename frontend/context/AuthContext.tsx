import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useRouter, useSegments } from 'expo-router';

interface AuthContextType {
    userToken: string | null;
    isLoading: boolean;
    signIn: (token: string) => Promise<void>;
    signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [userToken, setUserToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const segments = useSegments();
    const router = useRouter();

    useEffect(() => {
        // Fetch the token from storage
        const bootstrapAsync = async () => {
            let token;
            try {
                token = await AsyncStorage.getItem('userToken');
            } catch (e) {
                // Restoring token failed
            }
            setUserToken(token || null);
            setIsLoading(false);
        };

        bootstrapAsync();
    }, []);

    useEffect(() => {
        if (isLoading) return;

        const inAuthGroup = segments[0] === '(auth)' || segments[0] === 'login';

        if (!userToken && !inAuthGroup) {
            // Redirect to the sign-in page.
            router.replace('/login');
        } else if (userToken && inAuthGroup) {
            // Redirect away from the sign-in page.
            router.replace('/(tabs)');
        }
    }, [userToken, segments, isLoading]);

    const signIn = async (token: string) => {
        await AsyncStorage.setItem('userToken', token);
        setUserToken(token);
    };

    const signOut = async () => {
        await AsyncStorage.removeItem('userToken');
        setUserToken(null);
    };

    return (
        <AuthContext.Provider value={{ userToken, isLoading, signIn, signOut }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
