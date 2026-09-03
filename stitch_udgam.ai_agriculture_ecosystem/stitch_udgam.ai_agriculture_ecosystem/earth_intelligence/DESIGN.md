---
name: Earth & Intelligence
colors:
  surface: '#fcf9f2'
  surface-dim: '#dcdad3'
  surface-bright: '#fcf9f2'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3ec'
  surface-container: '#f0eee7'
  surface-container-high: '#ebe8e1'
  surface-container-highest: '#e5e2db'
  on-surface: '#1c1c18'
  on-surface-variant: '#3f4a3c'
  inverse-surface: '#31312c'
  inverse-on-surface: '#f3f0ea'
  outline: '#6f7a6b'
  outline-variant: '#becab9'
  surface-tint: '#006e1c'
  primary: '#006e1c'
  on-primary: '#ffffff'
  primary-container: '#4caf50'
  on-primary-container: '#003c0b'
  inverse-primary: '#78dc77'
  secondary: '#2a6b2c'
  on-secondary: '#ffffff'
  secondary-container: '#acf4a4'
  on-secondary-container: '#307231'
  tertiary: '#6b5e31'
  on-tertiary: '#ffffff'
  tertiary-container: '#bbaa76'
  on-tertiary-container: '#4a3e15'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#94f990'
  primary-fixed-dim: '#78dc77'
  on-primary-fixed: '#002204'
  on-primary-fixed-variant: '#005313'
  secondary-fixed: '#acf4a4'
  secondary-fixed-dim: '#91d78a'
  on-secondary-fixed: '#002203'
  on-secondary-fixed-variant: '#0c5216'
  tertiary-fixed: '#f4e2a9'
  tertiary-fixed-dim: '#d7c690'
  on-tertiary-fixed: '#231b00'
  on-tertiary-fixed-variant: '#52461c'
  background: '#fcf9f2'
  on-background: '#1c1c18'
  surface-variant: '#e5e2db'
  insight-purple: '#673AB7'
  data-blue: '#2196F3'
  earth-gray: '#4E4B42'
typography:
  display:
    fontFamily: Public Sans
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Public Sans
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-lg-mobile:
    fontFamily: Public Sans
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
  headline-md:
    fontFamily: Public Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Public Sans
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Public Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Public Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Public Sans
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  unit: 8px
  container-max: 1280px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
---

## Brand & Style

This design system is built for a modern Indian agritech platform that bridges the gap between advanced AI and the grounded reality of farming. The brand personality is **nurturing, innovative, and reliable**. It avoids the coldness of typical tech platforms in favor of a "Human-Centric AI" aesthetic.

The design style is **Modern Organic**. It combines high-end SaaS clarity with soft, tactile elements inspired by nature. We use heavy whitespace to allow complex data to breathe, paired with a sophisticated interpretation of agricultural tones. The goal is to evoke a sense of calm efficiency—positioning the AI as a helpful companion rather than a complex tool.

## Colors

The palette is rooted in the Indian landscape. 
- **Primary Green (#4CAF50):** Used for growth-related indicators, success states, and primary interactive elements.
- **Deep Forest (#1B5E20):** Provides the necessary gravitas for typography and high-priority actions, ensuring high legibility against the light background.
- **Cream Base (#FCF9F2):** Replaces harsh whites to reduce eye strain and provide a premium, paper-like feel.
- **Accents:** Warm Yellow is used for highlights and cautionary states, while the subtle Purple and Blue are reserved for AI-generated insights and technical data visualizations to distinguish them from biological data.

## Typography

We use **Public Sans** across the entire system. Its neutral yet friendly character ensures accessibility for users with varying levels of digital literacy. 

- **Hierarchy:** Strong contrast between Forest Green headings and Earth Gray body text helps users scan information quickly.
- **Spacing:** Generous line-heights are maintained to ensure readability in field conditions where glare may be present.
- **Data Display:** For numerical data and AI insights, use the `label-md` style with slightly increased letter spacing to enhance clarity.

## Layout & Spacing

The design follows a **Fluid-Fixed Hybrid** model. Content is centered within a 1280px container on desktop to maintain focus, while background elements bleed to the edges. 

- **Grid:** A 12-column grid for desktop and a 4-column grid for mobile.
- **Rhythm:** An 8px linear scale governs all spacing.
- **Spaciousness:** Large internal padding in containers (minimum 32px) is used to create the "spacious" feel requested. Use "Section Spacing" (80px - 120px) to separate distinct AI-driven modules on the landing pages.

## Elevation & Depth

We avoid harsh shadows in favor of **Natural Depth**. Hierarchy is established through:
- **Soft Ambient Shadows:** Use very large blur radii (32px+) with low opacity (5-8%) tinted with the Primary Green to make cards appear as if they are floating gently above the cream background.
- **Tonal Layering:** Use the Warm Yellow accent at 10% opacity as a secondary surface color to highlight "AI Suggestion" areas.
- **Thin Outlines:** Components use 1px borders in a slightly darker shade of the background color (#E5E2D9) to provide structure without adding visual noise.

## Shapes

The shape language is **Ultra-Soft**. We use high-radius corners to mirror the organic forms found in nature (seeds, leaves, hills). 

- **Standard Elements:** Buttons and inputs use a 1rem (16px) radius.
- **Containers:** Primary cards and dashboard modules use `rounded-2xl` (24px) or `rounded-3xl` (32px) to reinforce the friendly, modern aesthetic.
- **Iconography:** Icons should feature rounded caps and joins, avoiding any sharp 90-degree angles.

## Components

- **Buttons:** Primary buttons use the Forest Green background with white text and `rounded-full` (pill) shapes. Secondary buttons use a Forest Green outline with a subtle cream hover state.
- **AI Insight Cards:** These feature a subtle gradient border using the "Insight Purple" and a soft "Warm Yellow" background. They should always be paired with a "sparkle" icon.
- **Input Fields:** Large 56px height inputs with `rounded-xl` corners. The border thickens and changes to Primary Green on focus.
- **Chips/Badges:** Used for crop types or status indicators. Use high-contrast text on low-saturation backgrounds (e.g., Deep Green text on Light Green background).
- **Interactive Lists:** List items should have generous vertical padding (20px+) and be separated by thin, soft-grey dividers.
- **Farmer Profiles:** User-centric components should use circular avatars with a Forest Green ring to indicate "Active/Verified" status.