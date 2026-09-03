---
name: UDGAM.ai
colors:
  surface: '#fbf9f4'
  surface-dim: '#dbdad5'
  surface-bright: '#fbf9f4'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f5f4ee'
  surface-container: '#efeee8'
  surface-container-high: '#e9e8e3'
  surface-container-highest: '#e4e2dd'
  on-surface: '#1b1c19'
  on-surface-variant: '#404943'
  inverse-surface: '#30312d'
  inverse-on-surface: '#f2f1eb'
  outline: '#707973'
  outline-variant: '#bfc9c1'
  surface-tint: '#2c694e'
  primary: '#0f5238'
  on-primary: '#ffffff'
  primary-container: '#2d6a4f'
  on-primary-container: '#a8e7c5'
  inverse-primary: '#95d4b3'
  secondary: '#835500'
  on-secondary: '#ffffff'
  secondary-container: '#feb956'
  on-secondary-container: '#734a00'
  tertiary: '#274e45'
  on-tertiary: '#ffffff'
  tertiary-container: '#3f665d'
  on-tertiary-container: '#b8e2d6'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b1f0ce'
  primary-fixed-dim: '#95d4b3'
  on-primary-fixed: '#002114'
  on-primary-fixed-variant: '#0e5138'
  secondary-fixed: '#ffddb4'
  secondary-fixed-dim: '#feb956'
  on-secondary-fixed: '#291800'
  on-secondary-fixed-variant: '#633f00'
  tertiary-fixed: '#c1ebdf'
  tertiary-fixed-dim: '#a6cfc3'
  on-tertiary-fixed: '#00201a'
  on-tertiary-fixed-variant: '#274e45'
  background: '#fbf9f4'
  on-background: '#1b1c19'
  surface-variant: '#e4e2dd'
typography:
  display-lg:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans
      Devanagari', sans-serif
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  stat-lg:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans
      Devanagari', sans-serif
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 42px
  headline-md:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans
      Devanagari', sans-serif
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 36px
  headline-sm:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans
      Devanagari', sans-serif
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 30px
  body-base:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans
      Devanagari', sans-serif
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-bold:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans
      Devanagari', sans-serif
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 26px
  label-caps:
    fontFamily: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans
      Devanagari', sans-serif
    fontSize: 14px
    fontWeight: '700'
    lineHeight: 22px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 16px
  touch-target-min: 48px
  touch-target-large: 52px
---

## Brand & Style

The design system for this agricultural marketplace is built on a foundation of **Trust, Vitality, and Extreme Accessibility**. It is designed to serve a user base of farmers and traders who require high-fidelity tools that remain functional in challenging outdoor environments (high glare) and on varying mobile hardware.

The design style is a blend of **Modern Professionalism** and **Tactile Minimalism**. It avoids complex shadows and translucent glass effects which can wash out in sunlight, instead relying on crisp, high-contrast borders and a solid, "grounded" color palette. The interface uses a single-column, mobile-first approach to reduce cognitive load for semi-literate users, ensuring that every action is intentional, visible, and easily triggered by physical touch.

**Key Visual Principles:**
- **Clarity over Decoration:** No standalone icons; every glyph is paired with a text label.
- **Environmental Resilience:** High-contrast ratios (WCAG AAA for critical paths) ensure readability in direct sunlight.
- **Tactile Confidence:** Large, clear hitboxes designed for users with calloused hands or those using low-end resistive/capacitive screens.
- **Bilingual Fluidity:** Structural layouts account for the 25-35% text expansion typical when translating from English to Indic scripts.

## Colors

The palette is derived from the agricultural landscape, using "Earth Green" and "Harvest Gold" to signal growth and prosperity.

- **Primary (Earth Green - #2D6A4F):** Used for primary actions, success states, and brand trust. It is deep enough to maintain high contrast against light backgrounds.
- **Secondary (Warm Amber - #E09F3E):** Used for attention-grabbing elements, high-priority transaction alerts, and the voice-assistant core.
- **Background (Creamy Off-White - #F9F7F2):** Replaces pure white to reduce eye strain and screen glare in outdoor field settings.
- **Surface (#FFFFFF):** Reserved for interactive cards and modals to create a clear visual "lift" from the background without relying on heavy shadows.
- **Neutral/Ink (#1B1C19):** A deep slate used for all primary text to ensure maximum legibility.

## Typography

This system uses a **System Font Stack** to ensure zero-latency rendering on slow networks and perfect native support for Indic scripts (Devanagari, etc.).

**Typography Rules:**
- **Minimum Size:** No body text may fall below **16px** to accommodate diverse literacy levels and vision quality.
- **Indic Optimization:** A strict minimum line-height of **1.5x** is enforced to prevent the "clipping" of Hindi matras (vowel signs) and top bars.
- **Contrast over Weight:** Weights below 400 (Regular) are prohibited. Use SemiBold (600) and Bold (700) liberally for pricing and crop metrics.
- **Bilingual Display:** Always ensure that UI components can expand vertically if translated text exceeds the line length.

## Layout & Spacing

The layout is **Mobile-First and Single-Column**. This vertical stack approach ensures that users only need to scroll in one direction, reducing navigation errors.

**Layout Model:**
- **Fluid Mobile Grid:** A single-column layout with 16px side margins on mobile.
- **Fixed Tablet/Desktop Grid:** On screens >768px, content transitions to a 2-column card grid or a centered 1120px container.
- **Vertical Rhythm:** A strict 8px-based spacing system. 16px is the standard spacing between elements; 24px-32px is used to separate major functional sections.
- **Touch Areas:** Every interactive element (buttons, inputs, chips) must have a minimum height of **48px**, with a preferred height of **52px** for primary actions.

## Elevation & Depth

This design system prioritizes **Bold Borders** over shadows for depth perception. This ensures that UI elements remain distinguishable even when screen brightness is turned up to maximum in outdoor settings.

- **Structural Borders:** Use `1.5px solid #C4C8BA` for default card states and `2px solid #74796D` for form inputs.
- **Tonal Layering:** Interactive surfaces are pure white (`#FFFFFF`) placed on the creamy background (`#F9F7F2`).
- **Minimal Shadows:** Shadows are used sparingly as a secondary cue (e.g., `0 2px 4px rgba(0,0,0,0.06)`) and should never be the sole indicator of an interactive element.
- **Focus States:** Focused inputs or active cards use a thicker `3px` border in Primary Green to provide unmistakable feedback.

## Shapes

The shape language uses **Rounded Corners** to convey friendliness and safety, while maintaining enough structure to look professional and enterprise-ready.

- **Standard Elements (Buttons, Inputs):** Use `12px` (0.75rem) radius for a modern, approachable feel.
- **Container Cards:** Use `16px` (1rem) radius to clearly define major sections of content.
- **Pills & Badges:** Use `rounded-full` (9999px) for status indicators like "Verified" or "In-Stock."
- **Visual Enclosure:** Every image or crop thumbnail must have at least an `8px` corner radius to match the overall UI softness.

## Components

### Buttons
- **Primary:** Full-width (on mobile), 52px height, Earth Green fill with white text. High tactile feedback (scale 0.98 on tap).
- **Secondary/CTA:** Warm Amber fill or light Amber container with dark text. Used for "Sell Now" or voice triggers.
- **Icons:** Must never appear alone. Icons are always accompanied by 14px or 16px bold labels.

### Cards
- **Marketplace Cards:** White background, 1.5px olive border. Contains a square 1:1 image, bold price metric, and a primary action button at the bottom.
- **Spacing:** Content inside cards should have a minimum 16px internal padding.

### Inputs
- **Form Fields:** 52px height with always-visible labels. Labels must be 16px Bold.
- **Numeric Inputs:** Large keys with helper increment chips (+1, +5, +10) for quick quantity entry.

### Voice Assistant (Floating Mic)
- **Visuals:** A 64x64px circular floating button in Warm Amber (#E09F3E).
- **Behavior:** Fixed to the bottom-right. It features a pulsing animation to signal that the AI is ready to listen.
- **Feedback:** On tap, a visual waveform and real-time text transcription appear at the bottom of the screen.

### Navigation
- **Bottom Bar:** 64px height. Icons must have labels. Active states are indicated by the Primary Green color and a subtle bar above the icon.