import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'ODIN Protocol',
  description: 'Typed, signed, translated, and provably auditable AI-to-AI messaging.',
  head: [
    ['meta', { name: 'theme-color', content: '#0f172a' }],
    ['meta', { property: 'og:title', content: 'ODIN Protocol' }],
    ['meta', { property: 'og:description', content: 'An AI intranet: typed, signed, translated, auditable.' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:url', content: 'https://odin-protocol.dev' }],
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/logo.svg' }],
  ],
  themeConfig: {
    logo: { src: '/logo.svg', alt: 'ODIN Protocol', width: 32, height: 32 },
    nav: [
      { 
        text: 'Products', 
        items: [
          { text: 'Core (Gateway & Relay)', link: '/docs/' },
          { text: 'Bridge Pro (Payments)', link: '/docs/bridges#payments-bridge-pro' },
          { text: 'Realm Packs', link: '/docs/realms' },
          { text: 'SDKs', link: '/docs/sdk' },
        ]
      },
      { 
        text: 'Docs', 
        items: [
          { text: 'Quickstart', link: '/#quickstart' },
          { text: 'Research Engine', link: '/research' },
          { text: 'API Reference', link: '/docs/api' },
          { text: 'Realms', link: '/docs/realms' },
          { text: 'Bridges', link: '/docs/bridges' },
          { text: 'Receipts & Audit', link: '/docs/receipts' },
          { text: 'Security', link: '/docs/security' },
        ]
      },
      { text: 'Pricing', link: '/pricing' },
      { text: 'Changelog', link: '/changelog' },
      { text: 'Status', link: 'https://status.odin-protocol.dev' },
      { text: 'GitHub', link: 'https://github.com/Maverick0351a/ODINAIMESH' }
    ],
    sidebar: {
      '/docs/': [
        { 
          text: 'Getting Started',
          items: [
            { text: 'Overview', link: '/docs/' },
            { text: 'Quickstart', link: '/docs/quickstart' },
            { text: 'Research Engine', link: '/research' },
            { text: 'SDK Installation', link: '/docs/sdk' },
          ]
        },
        {
          text: 'Core Concepts',
          items: [
            { text: 'API Reference', link: '/docs/api' },
            { text: 'Realms & Packs', link: '/docs/realms' },
            { text: 'Bridges & SFT', link: '/docs/bridges' },
            { text: 'Receipts & Audit', link: '/docs/receipts' },
            { text: 'Security Model', link: '/docs/security' },
          ]
        },
        {
          text: 'Enterprise Add-ons',
          items: [
            { text: 'Payments Bridge Pro', link: '/docs/bridges#payments-bridge-pro' },
            { text: 'Roaming Federation', link: '/docs/roaming' },
          ]
        }
      ]
    },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/Maverick0351a/ODINAIMESH' },
      { icon: 'discord', link: 'https://discord.gg/odin-protocol' },
      { icon: 'twitter', link: 'https://twitter.com/odin_protocol' }
    ],
    search: { provider: 'local' },
    footer: {
      message: 'Built for regulated environments. Enterprise-ready AI infrastructure.',
      copyright: 'Copyright © 2024-2025 ODIN Protocol'
    },
    editLink: {
      pattern: 'https://github.com/Maverick0351a/ODINAIMESH/edit/main/docs/:path',
      text: 'Edit this page on GitHub'
    }
  },
  lastUpdated: true,
  cleanUrls: true,
  markdown: {
    theme: {
      light: 'github-light',
      dark: 'github-dark'
    },
    lineNumbers: true
  }
})
