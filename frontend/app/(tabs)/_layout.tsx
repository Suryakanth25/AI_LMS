import { Tabs } from 'expo-router';
import React from 'react';
import TabBar from '../../components/TabBar';

export default function TabLayout() {
  return (
    <Tabs
      tabBar={(props) => <TabBar {...props} />}
      screenOptions={{
        headerShown: false,
      }}
    >
      <Tabs.Screen
        name="subjects"
        options={{
          title: 'Subjects',
        }}
      />
      <Tabs.Screen
        name="generate"
        options={{
          title: 'Generate',
        }}
      />
      <Tabs.Screen
        name="vetting"
        options={{
          title: 'Vetting',
        }}
      />
      <Tabs.Screen
        name="benchmarks"
        options={{
          title: 'Benchmarks',
        }}
      />
    </Tabs>
  );
}
