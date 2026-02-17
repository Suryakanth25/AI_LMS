import { Stack } from 'expo-router';

export default function SubjectsLayout() {
    return (
        <Stack screenOptions={{ headerShown: false }}>
            <Stack.Screen name="index" />
            <Stack.Screen name="[subjectId]" />
        </Stack>
    );
}
