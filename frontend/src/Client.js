import superagent from "superagent";

class Client {
  constructor(options) {
    if (!options.endpoint) throw new Error("No endpoint specified!");
    this.token = options.token;
    this.endpoint =
      (window.localStorage
        ? window.localStorage.getItem("endpoint-override")
        : null) || options.endpoint;
  }
  async getProfile() {
    if (!this.token) throw new Error("BAD_AUTH");
    try {
      this.profile = await this.request("get", "/profile").then(
        res => res.body
      );
    } catch (err) {
      throw this.handleErr(err);
      // TODO: handle the error properly !
    }
    return this.profile;
  }

  async getDomains() {
    return [];
  }

  async updateAccount(changes) {
    if (!this.token || !changes.password) throw new Error("BAD_AUTH");
    try {
      const res = await this.request("patch", "/profile")
        .send(changes)
        .then(res => res.body);
      if (changes.new_password) {
        console.log(this.user, changes.new_password);
        await this.login(this.profile.username, changes.new_password);
      }
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  async deleteFile(shortcode) {
    if (!this.token) throw new Error("BAD_AUTH");
    try {
      const res = await this.request("delete", "/delete")
        .send({
          filename: shortcode
        })
        .then(res => res.body);
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  generateToken(password) {
    if (!this.token) return Promise.reject(new Error("BAD_AUTH"));
    try {
      return this.request("post", "/apikey")
        .send({
          user: this.profile.username,
          password: password
        })
        .then(res => res.body.api_key);
    } catch (err) {
      throw this.handleErr(err);
      // TODO: handle the error properly !
    }
  }

  revokeTokens(password) {
    if (!this.token) return Promise.reject(new Error("BAD_AUTH"));
    try {
      return this.request("post", "/revoke").send({
        user: this.profile.username,
        password: password
      });
    } catch (err) {
      throw this.handleErr(err);
      // TODO: handle the error properly !
    }
  }

  upload(file) {
    if (!this.token) return Promise.reject(new Error("BAD_AUTH"));
    try {
      const formData = new FormData();
      formData.append("file", file);
      return this.request("post", "/upload").send(formData);
    } catch (err) {
      return Promise.reject(this.handleErr(err));
    }
  }

  async getQuota() {
    if (!this.token) throw new Error("BAD_AUTH");
    try {
      this.quota = await this.request("get", "/limits").then(res => res.body);
    } catch (err) {
      throw this.handleErr(err);
      // TODO: handle the error properly !
    }
    return this.quota;
  }

  async login(username, password) {
    if (!username || !password) throw new Error("BAD_AUTH");
    try {
      this.user = username;
      const res = await this.request("post", "/login").send({
        user: username,
        password
      });
      this.token = res.body.token;
      return res.body.token;
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  async getFiles() {
    if (!this.token) throw new Error("BAD_AUTH");

    try {
      this.files = await this.request("get", "/list").then(
        res => res.body.files
      );
      return this.files;
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  async invalidateSessions(username, password) {
    if (!username || !password) throw new Error("BAD_AUTH");

    try {
      return await this.request("POST", "/revoke")
        .send({
          user: username,
          password
        })
        .then(res => res.body.ok);
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  handleErr(err) {
    console.log(err, err.status);
    if (err.status == 403) {
      return new Error("BAD_AUTH");
    } else if (err.status == 400) {
      return new Error("BAD_REQUEST");
    } else if (err.status == 415) {
      return new Error("BAD_IMAGE");
    } else if (err.status == 429) {
      return new Error("RATELIMITED");
    } else if (err.status == 404) {
      return new Error("NOT_FOUND");
    }
    return err;
  }

  request(method, url) {
    return superagent[method.toLowerCase()](this.endpoint + url).set(
      "Authorization",
      this.token
    );
  }
}

export default Client;
