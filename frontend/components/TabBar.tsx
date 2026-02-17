import React from 'react';
import { View, TouchableOpacity, Text } from 'react-native';
import { BottomTabBarProps } from '@react-navigation/bottom-tabs';
import { BookOpen, Sparkles, Check, ChartBar } from 'lucide-react-native';

// Map route names to icons and labels — 4 tabs, no Home
const TAB_ICONS: Record<string, any> = {
    subjects: BookOpen,
    generate: Sparkles,
    vetting: Check,
    benchmarks: ChartBar,
};

const TAB_LABELS: Record<string, string> = {
    subjects: 'Subjects',
    generate: 'Generate',
    vetting: 'Vetting',
    benchmarks: 'Benchmarks',
};

export default function TabBar({ state, descriptors, navigation }: BottomTabBarProps) {
    return (
        <View className="absolute bottom-0 left-0 right-0 h-[70px] flex-row items-center justify-around bg-[#1A1A1A] px-2 pb-2">
            {state.routes.map((route, index) => {
                const { options } = descriptors[route.key];
                const isFocused = state.index === index;

                const onPress = () => {
                    const event = navigation.emit({
                        type: 'tabPress',
                        target: route.key,
                        canPreventDefault: true,
                    });

                    if (!isFocused && !event.defaultPrevented) {
                        navigation.navigate(route.name, route.params);
                    }
                };

                const onLongPress = () => {
                    navigation.emit({
                        type: 'tabLongPress',
                        target: route.key,
                    });
                };

                const Icon = TAB_ICONS[route.name] || BookOpen;
                const label = TAB_LABELS[route.name] || route.name;
                const color = isFocused ? '#5BA3F5' : '#6B7280';

                return (
                    <TouchableOpacity
                        key={route.key}
                        accessibilityRole="button"
                        accessibilityState={isFocused ? { selected: true } : {}}
                        accessibilityLabel={options.tabBarAccessibilityLabel}
                        testID={options.tabBarTestID}
                        onPress={onPress}
                        onLongPress={onLongPress}
                        className="flex-1 items-center justify-center py-2 gap-1"
                    >
                        <Icon size={24} color={color} strokeWidth={isFocused ? 2.5 : 2} />
                        <Text style={{ color, fontSize: 10, fontWeight: isFocused ? '600' : '500' }}>
                            {label}
                        </Text>
                    </TouchableOpacity>
                );
            })}
        </View>
    );
}
