const BUILD_DIR = __dirname + "/output/";
const SRC_DIR = __dirname + "/src/";
const HtmlWebpackPlugin = require("html-webpack-plugin");
const MinifyPlugin = require("babel-minify-webpack-plugin");
const pageList = [
  {
    title: "Elixire",
    chunkName: "index"
  },
  {
    title: "Login | Elixire",
    chunkName: "login"
  },
  {
    title: "Signup | Elixire",
    chunkName: "signup"
  },
  {
    title: "Upload | Elixire",
    chunkName: "upload"
  },
  {
    title: "My Account | Elixire",
    chunkName: "account"
  },
  {
    title: "Logout",
    chunkName: "logout"
  },
  {
    title: "New Token | Elixire",
    chunkName: "token",
    chunks: ["highlight", "highlightTheme"]
  },
  {
    title: "About Us | Elixire",
    chunkName: "about"
  }
];

module.exports = {
  entry: {
    index: `${SRC_DIR}/homepage.js`,
    login: `${SRC_DIR}/login.js`,
    signup: `${SRC_DIR}/signup.js`,
    upload: `${SRC_DIR}/upload.js`,
    account: `${SRC_DIR}/account.js`,
    logout: `${SRC_DIR}/logout.js`,
    token: `${SRC_DIR}/token.js`,
    highlight: `${SRC_DIR}/highlight.js`,
    highlightTheme: `${SRC_DIR}/highlightTheme.js`,
    theme: `${SRC_DIR}/theme.js`,
    themeCSS: `${SRC_DIR}/themeCSS.js`,
    about: `${SRC_DIR}/about.js`
  },
  output: {
    filename: "assets/[chunkhash].js",
    path: BUILD_DIR,
    chunkFilename: "assets/[chunkhash].js",
    sourceMapFilename: "assets/[chunkhash].map.js",
    publicPath: "/"
  },
  plugins: [
    ...(process.env.NODE_ENV == "production"
      ? [
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
          chunks: ["themeCSS", page.chunkName, "theme"].concat(
            page.chunks || []
          ),
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
        include: [SRC_DIR],
        loader: "babel-loader",
        options: {
          babelrc: false,
          presets: ["@babel/preset-env"]
        }
      },
      {
        test: /\.s?css$/,
        use: ["style-loader", "css-loader", "sass-loader"]
      },
      {
        test: /\.pug$/,
        use: ["pug-loader"],
        exclude: /node_modules/
      },
      {
        test: /\.(?:sv|pn)g$/,
        use: ["file-loader?name=./assets/[hash].[ext]"]
      }
    ]
  }
};
