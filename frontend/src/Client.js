import superagent from "superagent";

class Client {
  constructor(options) {
    if (!options.endpoint) throw new Error("No endpoint specified!");
    this.token = options.token;
    this.endpoint = "http://localhost:8080/api"; // options.endpoint;
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
      this.quota = await this.request("get", "/limits").then(
        res => res.body.limit
      );
    } catch (err) {
      throw this.handleErr(err);
      // TODO: handle the error properly !
    }
    return this.quota;
  }

  async login(username, password) {
    if (!username || !password) throw new Error("BAD_AUTH");
    try {
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
