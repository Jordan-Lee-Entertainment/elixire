import superagent from "superagent";

class Client {
  /**
   * Create a client for the Elixire API
   * @param {Object} options - Options to instantiate the client with
   * @param {String} options.endpoint - Endpoint to prefix all requests with, including the trailing /api
   * @param {String} [options.token=null] - Token to use for authenticated routes
   */
  constructor(options) {
    if (!options.endpoint) throw new Error("No endpoint specified!");
    /**
     * The token used to make authenticated requests on the API
     * @type {?String}
     */
    this.token = options.token || null;
    /**
     * The endpoint to be prepended to API endpoints including the trailing /api
     * @type {String}
     */
    this.endpoint =
      (window.localStorage
        ? window.localStorage.getItem("endpoint-override")
        : null) || options.endpoint;
    /**
     * The profile of the currently logged in user (Only set if getProfile() has been called)
     * @type {?Object}
     */
    this.profile = null;
    // TODO: Profile class?
    /**
     * The quota of the currently logged in user (Only set if getQuota() has been called)
     * @type {?Object}
     */
    this.quota = null;
    // TODO: Quota class?
    /**
     * The files and shortlinks created by the user
     * @type {?Object}
     */
    this.files = null;
  }

  /**
   * Gets the user's profile from the API
   * @returns {Promise<Object>} The profile of the currently logged-in user
   * @api public
   */
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

  /**
   * Gets the domains currently available to the user
   * @returns {Promise<Object>} An Object mapping domain id to domain
   * @api public
   */
  async getDomains() {
    if (!this.token) throw new Error("BAD_AUTH");
    try {
      this.domains = await this.request("get", "/domains").then(
        res => res.body.domains
      );
    } catch (err) {
      throw this.handleErr(err);
      // TODO: handle the error properly !
    }
    return this.domains;
  }

  /**
   * Updates the account with the specified changes
   * @param {Object} changes - The changes to be applied to the account
   * @param {String} changes.password - The password to be used to authenticate the changes (required)
   * @param {String} [changes.new_password] - Optional parameter to set the user's password
   * @param {Number} [change.domain] - Optional parameter to set the user's upload domain
   * @returns {Promise<Array>} An array containing the list of fields that were modified
   * @api public
   */
  async updateAccount(changes) {
    if (!this.token || !changes.password) throw new Error("BAD_AUTH");
    try {
      const res = await this.request("patch", "/profile")
        .send(changes)
        .then(res => res.body.updated_fields);
      if (changes.new_password) {
        await this.login(this.profile.username, changes.new_password);
      }
      return res;
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  /**
   * Deletes a shortened URL
   * @param {String} shortcode - The shortcode of the shortened link to delete
   * @returns {Promise<Object>} The response body
   * @api public
   */
  async deleteLink(shortcode) {
    if (!this.token) throw new Error("BAD_AUTH");
    try {
      return await this.request("delete", "/shortendelete")
        .send({
          filename: shortcode
        })
        .then(res => res.body);
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  /**
   * Deletes an uploaded file
   * @param {String} shorcode - The shortcode of the file to be deleted
   * @returns {Promise<Object>} The response body
   * @api public
   */
  async deleteFile(shortcode) {
    if (!this.token) throw new Error("BAD_AUTH");
    try {
      return await this.request("delete", "/delete")
        .send({
          filename: shortcode
        })
        .then(res => res.body);
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  /**
   * Generates an uploader API key
   * @param {String} password - The user's password to authenticate with
   * @returns {Promise<String>} The generated API key
   * @api public
   */
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

  /**
   * Revokes all the user's tokens (uploader tokens and api keys)
   * @param {String} password - The user's password to authenticate with
   * @returns {Promise<Object>} The response body
   * @api public
   */
  revokeTokens(password) {
    if (!this.token || !password) return Promise.reject(new Error("BAD_AUTH"));
    try {
      return this.request("post", "/revoke")
        .send({
          user: this.profile.username,
          password: password
        })
        .then(req => req.body);
    } catch (err) {
      throw this.handleErr(err);
      // TODO: handle the error properly !
    }
  }

  /**
   * Uploads a file
   * @param file {File} - The file to be uploaded
   * @returns {superagent.Request} The request object for the upload
   * @api public
   */
  upload(file) {
    if (!this.token) return Promise.reject(new Error("BAD_AUTH"));
    try {
      const formData = new FormData();
      formData.append("file", file);
      const request = this.request("post", "/upload").send(formData);
      if (this.profile.admin) request.query({ admin: 1 });
      return request;
    } catch (err) {
      return Promise.reject(this.handleErr(err));
    }
  }

  /**
   * Shortens a given URL
   * @param {String} longUrl - The URL to be shortened
   * @returns {Promise<String>} The shortened URL
   * @api public
   */
  async shortenUrl(longUrl) {
    if (!this.token) throw new Error("BAD_AUTH");
    try {
      return await this.request("post", "/shorten")
        .send({
          url: longUrl
        })
        .then(res => res.body.url);
    } catch (err) {
      throw this.handleErr(err);
      // TODO: handle the error properly !
    }
  }

  /**
   * Finds the user's quota
   * @returns {Object} The quotas of the user
   * @api public
   */
  async getQuota() {
    // TODO: Quota class?
    if (!this.token) throw new Error("BAD_AUTH");
    try {
      this.quota = await this.request("get", "/limits").then(res => res.body);
    } catch (err) {
      throw this.handleErr(err);
      // TODO: handle the error properly !
    }
    return this.quota;
  }

  /**
   * Gets a token for the given username/password pair
   * @param {String} username - The username to login with
   * @param {String} password - The password to login with
   * @returns {Promise<String>} The API token created
   * @api public
   */
  async login(username, password) {
    if (!username || !password) throw new Error("BAD_AUTH");
    try {
      const res = await this.request("post", "/login")
        .send({
          user: username,
          password
        })
        .set("Authorization", null);
      // So I guess the ratelimit code gets mad when you provide
      // an invalid token, bypassing the actual route handler entirely
      this.token = res.body.token;
      return res.body.token;
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  /**
   * Gets a list of all the files the user has uploaded and the links they've shortened
   * @returns {Promise<Object>} The files and shortens created by the user
   * @api public
   */
  async getFiles() {
    // TODO: Make a type for this so we can document the return value?
    if (!this.token) throw new Error("BAD_AUTH");

    try {
      this.files = await this.request("get", "/list").then(res => res.body);
      return this.files;
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  /**
   * Used internally to determine what type of error to throw
   * @params {Error} err - The error encountered while sending the request
   * @returns {Error} The error to be thrown
   * @api private
   */
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

  /**
   * Used internally to make requests to API endpoints, adds an Authorization header
   * @param {String} method - The type of request to make (get, post, patch, etc)
   * @param {String} url - The endpoint upon which to perform this request, is appended to the API base url of the client
   * @returns {superagent.Request} The request created by this
   * @api private
   */
  request(method, url) {
    return superagent[method.toLowerCase()](this.endpoint + url).set(
      "Authorization",
      this.token
    );
  }
}

export default Client;
