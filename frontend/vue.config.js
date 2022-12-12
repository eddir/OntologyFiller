module.exports = {
  lintOnSave: false,
  runtimeCompiler: true,
  configureWebpack: {
    //Necessary to run npm link https://webpack.js.org/configuration/resolve/#resolve-symlinks
    resolve: {
       symlinks: false
    }
  },
  transpileDependencies: [
    '@coreui/utils',
    '@coreui/vue'
  ],
  devServer: {
    disableHostCheck: true,
    port: 443,
    https: true,
    proxy: {
      '^/api': {
        target: 'http://onto.rostkov.me:8080',
        changeOrigin: true,
        ws: true,
      },
      '^/auth': {
        target: 'http://onto.rostkov.me:8080',
        changeOrigin: true,
        ws: true,
      },
      '^/admin': {
        target: 'http://onto.rostkov.me:8080',
        changeOrigin: true,
        ws: true,
      },
      '^/static': {
        target: 'http://onto.rostkov.me:8080',
        changeOrigin: true,
        ws: true,
      },
    }
  }
}
