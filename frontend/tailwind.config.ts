import type { Config } from 'tailwindcss';

/**
 * UDGAM design system, ported verbatim from frontend/css/tokens.css, which was
 * itself transcribed from design_reference/udgam.ai/DESIGN.md (the design
 * authority, A-1). The palette, type scale, radii and spacing are NOT
 * reinvented here -- changing them would change the product's visual identity.
 *
 * Design intent, unchanged: readable in direct sunlight, tappable with
 * calloused hands, structurally ready for Devanagari that runs 25-35% longer
 * than its English source.
 */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#006e1c',
          strong: '#005313',
          container: '#acf4a4',
          bright: '#4caf50',
          on: '#ffffff',
          'on-container': '#003c0b',
        },
        secondary: {
          DEFAULT: '#6b5e31',
          strong: '#52461c',
          container: '#f4e2a9',
          on: '#ffffff',
          'on-container': '#4a3e15',
        },
        tertiary: { DEFAULT: '#2a6b2c', container: '#acf4a4', on: '#ffffff' },
        /** Reserved for AI / model output only. Never ordinary UI. */
        insight: '#673ab7',
        bg: '#fcf9f2',
        surface: {
          DEFAULT: '#ffffff',
          low: '#f6f3ec',
          container: '#f0eee7',
          high: '#ebe8e1',
          highest: '#e5e2db',
          inverse: '#31312c',
          'on-inverse': '#f3f0ea',
        },
        ink: { DEFAULT: '#1c1c18', muted: '#3f4a3c' },
        outline: { DEFAULT: '#6f7a6b', variant: '#becab9' },
        line: { card: '#dfe6dc', input: '#6f7a6b' },
        danger: {
          DEFAULT: '#ba1a1a',
          container: '#ffdad6',
          on: '#ffffff',
          'on-container': '#93000a',
        },
        success: { DEFAULT: '#006e1c', container: '#acf4a4' },
        warning: { DEFAULT: '#52461c', container: '#f4e2a9' },
      },
      fontFamily: {
        sans: [
          'Public Sans',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          // Devanagari fallbacks come before the generic: a failed webfont fetch
          // on a rural connection must still shape Hindi/Marathi correctly.
          'Noto Sans Devanagari',
          'Noto Sans',
          'sans-serif',
        ],
      },
      fontSize: {
        // 16px is a HARD FLOOR for body text. `label` is for captions only.
        label: ['0.875rem', { lineHeight: '1.5' }],
        body: ['1rem', { lineHeight: '1.625' }],
        h2: ['1.25rem', { lineHeight: '1.5' }],
        h1: ['1.5rem', { lineHeight: '1.5' }],
        stat: ['1.75rem', { lineHeight: '1.5' }],
        display: ['2rem', { lineHeight: '1.5' }],
      },
      borderRadius: { sm: '4px', md: '12px', lg: '16px', img: '8px', full: '9999px' },
      spacing: {
        // 48px tap floor, 52px for primary actions. Non-negotiable.
        tap: '48px',
        'tap-primary': '52px',
        nav: '64px',
        sidebar: '272px',
      },
      maxWidth: { content: '1280px' },
      boxShadow: {
        sm: '0 2px 4px rgba(0,0,0,0.06)',
        // Tinted with the primary green, not black, so cards lift off the cream
        // background without going grey.
        ambient: '0 16px 32px -8px rgba(0,110,28,0.08)',
      },
      borderWidth: { card: '1.5px', input: '2px', focus: '3px' },
      transitionTimingFunction: { udgam: 'cubic-bezier(0.2,0,0.2,1)' },
      transitionDuration: { fast: '120ms', base: '200ms' },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.97)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: { from: { backgroundPosition: '-200% 0' }, to: { backgroundPosition: '200% 0' } },
        // Route line drawing itself: logistics motion, used by the shipment
        // timeline. Transform/opacity only -- never layout properties.
        'draw-line': { from: { transform: 'scaleX(0)' }, to: { transform: 'scaleX(1)' } },
      },
      animation: {
        'fade-up': 'fade-up 200ms cubic-bezier(0.2,0,0.2,1) both',
        'fade-in': 'fade-in 200ms cubic-bezier(0.2,0,0.2,1) both',
        'scale-in': 'scale-in 160ms cubic-bezier(0.2,0,0.2,1) both',
        shimmer: 'shimmer 1.4s linear infinite',
        'draw-line': 'draw-line 500ms cubic-bezier(0.2,0,0.2,1) both',
      },
      zIndex: { nav: '100', banner: '200', modal: '300', toast: '400' },
    },
  },
  plugins: [],
} satisfies Config;
