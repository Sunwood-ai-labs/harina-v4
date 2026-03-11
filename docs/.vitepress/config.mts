import { defineConfig } from "vitepress";

const repo = "https://github.com/Sunwood-ai-labs/harina-v4";

export default defineConfig({
  title: "Harina Receipt Bot",
  description: "Discord receipt recognition bot with Gemini, Google Drive, Google Sheets, and migration dataset backfills.",
  base: "/harina-v4/",
  cleanUrls: true,
  lastUpdated: true,
  head: [
    ["link", { rel: "icon", href: "/harina-v4/brand/harina-mark.svg" }],
    ["meta", { property: "og:image", content: "https://sunwood-ai-labs.github.io/harina-v4/brand/harina-hero.svg" }]
  ],
  themeConfig: {
    logo: "/brand/harina-mark.svg",
    siteTitle: "Harina Receipt Bot",
    socialLinks: [{ icon: "github", link: repo }],
    search: {
      provider: "local"
    }
  },
  locales: {
    root: {
      label: "English",
      lang: "en-US",
      link: "/",
      themeConfig: {
        nav: [
          { text: "Guide", link: "/guide/overview" },
          { text: "Dataset", link: "/guide/dataset-downloader" },
          { text: "Deploy", link: "/guide/deployment" },
          { text: "GitHub", link: repo }
        ],
        sidebar: [
          {
            text: "Guide",
            items: [
              { text: "Overview", link: "/guide/overview" },
              { text: "Dataset Downloader", link: "/guide/dataset-downloader" },
              { text: "Google Setup", link: "/guide/google-setup" },
              { text: "Deployment", link: "/guide/deployment" }
            ]
          }
        ],
        footer: {
          message: "Released under the MIT License.",
          copyright: "Copyright 2026 Sunwood AI Labs"
        }
      }
    },
    ja: {
      label: "日本語",
      lang: "ja-JP",
      link: "/ja/",
      themeConfig: {
        nav: [
          { text: "ガイド", link: "/ja/guide/overview" },
          { text: "データセット", link: "/ja/guide/dataset-downloader" },
          { text: "デプロイ", link: "/ja/guide/deployment" },
          { text: "GitHub", link: repo }
        ],
        sidebar: [
          {
            text: "ガイド",
            items: [
              { text: "概要", link: "/ja/guide/overview" },
              { text: "データセットダウンローダー", link: "/ja/guide/dataset-downloader" },
              { text: "Google 設定", link: "/ja/guide/google-setup" },
              { text: "デプロイ", link: "/ja/guide/deployment" }
            ]
          }
        ],
        footer: {
          message: "MIT License のもとで公開しています。",
          copyright: "Copyright 2026 Sunwood AI Labs"
        }
      }
    }
  }
});
