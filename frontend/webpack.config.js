const BUILD_DIR = __dirname + "/output/";
const SRC_DIR = __dirname + "/src/";
const HtmlWebpackPlugin = require("html-webpack-plugin");
const MinifyPlugin = require("babel-minify-webpack-plugin");
const ExtractTextPlugin = require("extract-text-webpack-plugin");
const extractCSS = new ExtractTextPlugin("assets/[chunkhash].css");
const CleanWebpackPlugin = require("clean-webpack-plugin");
const path = require("path");

const pageList = [
  {
    title: "elixi.re",
    chunkName: "index"
  },
  {
    title: "Login | elixi.re",
    chunkName: "login"
  },
  {
    title: "Upload | elixi.re",
    chunkName: "upload"
  },
  {
    title: "My Account | elixi.re",
    chunkName: "account",
    chunks: ["accountSelect2"]
  },
  {
    title: "Logout",
    chunkName: "logout"
  },
  {
    title: "New Token | elixi.re",
    chunkName: "token"
  },
  {
    title: "About Us | elixi.re",
    chunkName: "about"
  },
  {
    title: "FAQ | elixi.re",
    chunkName: "faq"
  },
  {
    title: "My Files | elixi.re",
    chunkName: "list"
  },
  {
    title: "My Shortened URLs | elixi.re",
    chunkName: "shortlist"
  },
  {
    title: "Shorten | elixi.re",
    chunkName: "shorten"
  },
  {
    title: "Signup | elixi.re",
    chunkName: "signup"
  },
  {
    title: "Admin | elixi.re",
    chunkName: "admin"
  },
  {
    title: "Delete your Account | elixi.re",
    chunkName: "deleteconfirm"
  },
  {
    title: "Password Reset | elixi.re",
    chunkName: "password_reset"
  }
];

const entryPointNames = [
  "login",
  "upload",
  "account",
  "logout",
  "token",
  "theme",
  "themeCSS",
  "about",
  "faq",
  "list",
  "shortlist",
  "shorten",
  "signup",
  "admin",
  "deleteconfirm",
  "password_reset"
];
let entry = {};
for (const name of entryPointNames) {
  entry[name] = `${SRC_DIR}js/${name}.js`;
}

module.exports = {
  entry: {
    babelPolyfill: "babel-polyfill",
    index: `${SRC_DIR}js/homepage.js`,
    bootstrapJs: "bootstrap",
    themeCSS: `${SRC_DIR}js/themeCSS.js`,
    accountSelect2: `${SRC_DIR}js/account-select2`,
    ...entry
  },
  resolve: {
    alias: {
      // import "@/file" goes to "src/file"
      "@": path.resolve(SRC_DIR)
    }
  },
  output: {
    filename: "assets/[chunkhash].js",
    path: BUILD_DIR,
    chunkFilename: "assets/[chunkhash].js",
    sourceMapFilename: "assets/[chunkhash].map.js",
    publicPath: "/"
  },
  plugins: [
    extractCSS,
    ...(process.env.NODE_ENV == "production"
      ? [
          new CleanWebpackPlugin([BUILD_DIR], {
            beforeEmit: true
          }),
          new MinifyPlugin(
            {
              removeConsole: true,
              removeDebugger: true
            },
            {
              comments: false
            }
          )
        ]
      : []),
    ...pageList.map(
      page =>
        new HtmlWebpackPlugin({
          title: page.title,
          filename: `${page.chunkName}.html`,
          template: `${SRC_DIR}/${page.chunkName}.pug`,
          chunks: [
            "babelPolyfill",
            "theme",
            "themeCSS",
            page.chunkName,
            "bootstrapJs"
          ].concat(page.chunks || []),
          mobile: true,
          inject: true,
          minify: {
            collapseWhitespace: true,
            removeComments: true,
            removeAttributeQuotes: true
          },
          xhtml: true
        })
    )
  ],
  module: {
    rules: [
      {
        test: /\.js$/,
        include: [SRC_DIR, `${SRC_DIR}/js`],
        loader: "babel-loader",
        options: {
          babelrc: false,
          presets: ["@babel/preset-env"],
          plugins: ["@babel/plugin-syntax-dynamic-import"]
        }
      },
      {
        test: /\.s?css$/,
        use: extractCSS.extract([
          {
            loader: "css-loader",
            options: { minimize: process.env.NODE_ENV == "production" }
          },

          { loader: "sass-loader" }
        ])
      },
      {
        test: /\.pug$/,
        loader: "pug-loader",
        query: {},
        exclude: /node_modules/
      },
      {
        test: /\.(?:sv|pn)g$/,
        use: ["file-loader?name=./assets/[hash].[ext]"]
      }
    ]
  }
};
