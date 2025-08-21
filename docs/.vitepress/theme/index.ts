import DefaultTheme from 'vitepress/theme'
import { App } from 'vue'
import OdinPlayground from './components/OdinPlayground.vue'
import './custom.css'

export default {
  ...DefaultTheme,
  enhanceApp({ app }: { app: App }) {
    DefaultTheme.enhanceApp?.({ app })
    app.component('OdinPlayground', OdinPlayground)
  }
}
