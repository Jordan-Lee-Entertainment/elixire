const BUILD_DIR = __dirname + "/output/";
const SRC_DIR = __dirname + "/src/";
const HtmlWebpackPlugin = require("html-webpack-plugin");
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
  }
];

module.exports = {
  entry: {
    index: `${SRC_DIR}/homepage.js`,
    login: `${SRC_DIR}/login.js`,
    signup: `${SRC_DIR}/signup.js`,
    upload: `${SRC_DIR}/upload.js`
  },
  output: {
    filename: "assets/[hash].js",
    path: BUILD_DIR,
    chunkFilename: "assets/[hash].js",
    sourceMapFilename: "assets/[hash].map.js",
    publicPath: "/"
  },
  plugins: pageList.map(
    page =>
      new HtmlWebpackPlugin({
        title: page.title,
        filename: `${page.chunkName}.html`,
        template: `${SRC_DIR}/${page.chunkName}.ejs`,
        chunks: [page.chunkName],
        inject: false,
        minify: {
          collapseWhitespace: true,
          removeComments: true,
          removeAttributeQuotes: true
        },
        xhtml: true
      })
  ),
  module: {
    loaders: [
      {
        test: /\.js$/,
        exclude: /node_modules/,
        include: [SRC_DIR],
        loader: "babel-loader",
        options: {
          babelrc: false,
          presets: ["babel-preset-env"]
        }
      },
      {
        test: /\.s?css$/,
        use: ["style-loader", "css-loader", "sass-loader"],
        exclude: /node_modules/
      }
    ]
  }
};
