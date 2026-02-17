export const Colors = {
  background: ['#c5ccd4', '#a8b5c7'] as const,
  card: {
    background: ['#ffffff', '#f7f7f7'] as const,
    border: '#a0a0a0',
    shadow: 'rgba(0,0,0,0.2)',
  },
  primary: ['#5eb0e5', '#3a8cc7', '#2d7ab8'] as const,
  success: ['#8fd36a', '#5cb82a'] as const,
  danger: ['#ff6b6b', '#dc4747'] as const,
  purple: ['#a78bfa', '#8b5cf6', '#7c3aed'] as const,
  warning: ['#fef08a', '#facc15', '#eab308'] as const,
  text: {
    primary: '#1f2937',
    secondary: '#6b7280',
    onButton: '#ffffff',
  },
  gradients: {
    subjects: ['#5eb0e5', '#3a8cc7'] as const, // Blue
    generate: ['#a78bfa', '#8b5cf6'] as const, // Purple
    vetting: ['#8fd36a', '#5cb82a'] as const,  // Green
    reports: ['#fef08a', '#facc15'] as const,  // Yellow/Orange-ish (Warning color used for Reports icon gradient in request?) 
    // Request said: Reports orange gradient... wait, "Reports orange gradient with BarChart3 icon"
    // But palette says Warning Yellow/Amber. Let's add an orange one for Reports specifically if needed, 
    // or use the Warning one. Let's add an specific Orange for Reports to match text.
    reportsOrange: ['#fbbf24', '#d97706'] as const,
  }
};
