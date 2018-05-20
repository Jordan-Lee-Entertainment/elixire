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
     * @type {?Profile}
     */
    this.profile = null;
    /**
     * The quota of the currently logged in user (Only set if getQuota() has been called)
     * @type {?Quota}
     */
    this.quota = null;
    /**
     * The files created by the user
     * @type {?Files}
     */
    this.files = null;
    /**
     * The shortens created by the user
     * @type {?Shortens}
     */
    this.shortens = null;
  }

  /**
   * Files uploaded by the user
   * @typedef Files
   * @type {Object.<Shortcode, File}
   */

  /**
   * The shortcode of a file/shorten
   * @typedef Shortcode
   * @type {String}
   */

  /**
   * An uploaded file
   * @typedef File
   * @type {Object}
   * @property {Shortcode} shortname The shortcode of the file
   * @property {Number} size The size of the file in bytes
   * @property {Number} snowflake The snowflake/unique ID of the file
   * @property {String} thumbnail The URL to the small thumbnail of the file
   * @property {String} url The URL to the original file
   */

  /**
   * Shortened URLs created by the user
   * @typedef Shortens
   * @type {Object.<Shortcode, Shorten}
   */

  /**
   * Shortened URL
   * @typedef Shorten
   * @type {Object}
   * @property {String} redirto The URL the shorten points to
   * @property {Shortcode} shortname The shortcode of the shorten
   * @property {Number} snowflake the snowflake/unique ID of the shorten
   * @property {String} url The shortened version of the URL
   */

  /**
   * A user's profile
   * @typedef Profile
   * @type {Object}
   * @property {Boolean} active True if the account is not disabled
   * @property {Boolean} admin If the user is admin, true otherwise false
   * @property {Number} domain The ID of the currently selected domain
   * @property {Quota} limits The quota of the user
   * @property {?String} subdomain The subdomain of the user if they have a wildcard domain selected
   * @property {String} user_id The ID of the user
   * @property {String} username The username of the user
   */

  /**
   * The quota of a user
   * @typedef Quota
   * @type {Object}
   * @property {Number} limit The user's weekly file cap in bytes
   * @property {Number} shortenlimit The user's weekly shortened URL cap
   * @property {Number} shortenused The number of shortened URLs the user has created during the quota period
   * @property {Number} used The total amount of storage used during this quota period by uploaded files in bytes
   */

  /**
   * Gets the user's profile from the API
   * @returns {Promise<Profile>} The profile of the currently logged-in user
   * @api public
   */
  async getProfile() {
    if (!this.token) throw new Error("BAD_AUTH");
    try {
      this.profile = await this.ratelimitedRequest("get", "/profile").then(
        res => res.body
      );
    } catch (err) {
      throw this.handleErr(err);
      // TODO: handle the error properly !
    }
    return this.profile;
  }

  /**
   * Shows domains available to the user
   * @typedef Domains
   * @property {Array} officialDomains - Array of official domains
   * @property {Object.<String, String>} domains - Domain names indexed by ID
   */

  /**
   * Gets the domains currently available to the user
   * @returns {Promise<Domains>} Domains available to the user
   * @api public
   */
  async getDomains() {
    try {
      this.domains = await this.ratelimitedRequest("get", "/domains", req => {
        // Heh. Expired token woes...
        if (!this.profile) req.set("Authorization", null);
      }).then(res => ({
        officialDomains: res.body.officialdomains,
        domains: res.body.domains
      }));
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
   * @param {String} [change.subdomain] - Optional parameter that sets the user's subdomain
   * @returns {Promise<Array>} An array containing the list of fields that were modified
   * @api public
   */
  async updateAccount(changes) {
    if (!this.token || !changes.password) throw new Error("BAD_AUTH");
    try {
      const res = await this.ratelimitedRequest("patch", "/profile", req =>
        req.send(changes)
      ).then(res => res.body.updated_fields);
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
   * @param {Shortcode} shortcode - The shortcode of the shortened link to delete
   * @returns {Promise<Object>} The response body
   * @api public
   */
  async deleteLink(shortcode) {
    if (!this.token) throw new Error("BAD_AUTH");
    try {
      return await this.ratelimitedRequest("delete", "/shortendelete", req =>
        req.send({ filename: shortcode })
      ).then(res => res.body);
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  /**
   * Deletes an uploaded file
   * @param {Shortcode} shortcode - The shortcode of the file to be deleted
   * @returns {Promise<Object>} The response body
   * @api public
   */
  async deleteFile(shortcode) {
    if (!this.token) throw new Error("BAD_AUTH");
    try {
      return await this.ratelimitedRequest("delete", "/delete", req =>
        req.send({
          filename: shortcode
        })
      ).then(res => res.body);
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  /**
   * Generates an uploader API key
   * @param {String} password - The user's password to authenticate with
   * @param {String} [username=this.profile.username] - The username to login with
   * @returns {Promise<String>} The generated API key
   * @api public
   */
  async generateToken(password, username = this.profile.username) {
    if (!username || !password) throw new Error("BAD_AUTH");
    try {
      return await this.ratelimitedRequest("post", "/apikey", req =>
        req.send({
          user: username,
          password: password
        })
      ).then(res => res.body.api_key);
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
      return this.ratelimitedRequest("post", "/revoke", req =>
        req.send({
          user: this.profile.username,
          password: password
        })
      ).then(req => req.body);
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
      // TODO: How will we make this work and still handle ratelimits?
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
      return await this.ratelimitedRequest("post", "/shorten", req =>
        req.send({
          url: longUrl
        })
      ).then(res => res.body.url);
    } catch (err) {
      throw this.handleErr(err);
      // TODO: handle the error properly !
    }
  }

  /**
   * Finds the user's quota
   * @returns {Quota} The quotas of the user
   * @api public
   */
  async getQuota() {
    // TODO: Quota class?
    if (!this.token) throw new Error("BAD_AUTH");
    try {
      this.quota = await this.ratelimitedRequest("get", "/limits").then(
        res => res.body
      );
    } catch (err) {
      throw this.handleErr(err);
      // TODO: handle the error properly !
    }
    return this.quota;
  }

  /**
   * Creates a temporary account to be activated.
   * @param {Object} params - The details for the account to be created with
   * @param {String} params.username - The username for the account
   * @param {String} params.password - The password for the account
   * @param {String} params.email - The email of the user for whom the account will be created
   * @param {String} params.discord - The DiscordTag of the user for whom the account will be created in the form of username#0000
   * @returns {Promise<Boolean>} Resolves with a boolean indicating success
   * @api public
   */
  async signup({ username, password, email, discord }) {
    try {
      const res = await this.ratelimitedRequest("post", "/register", req =>
        req
          .send({
            discord_user: discord,
            username,
            password,
            email
          })
          // So I guess the ratelimit code gets mad when you provide
          // an invalid token, bypassing the actual route handler entirely
          .set("Authorization", null)
      );
      return res.body.success;
    } catch (err) {
      throw this.handleErr(err);
    }
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
      const res = await this.ratelimitedRequest("post", "/login", req =>
        req
          .send({
            user: username,
            password
          })
          // So I guess the ratelimit code gets mad when you provide
          // an invalid token, bypassing the actual route handler entirely
          .set("Authorization", null)
      );
      this.token = res.body.token;
      return res.body.token;
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  /**
   * Enters a request to delete the current user's account
   * @param {String} password - The password to login with
   * @returns {Promise<String>} A token used to confirm account deletion
   * @api public
   */
  async deleteAccount(password) {
    try {
      return await this.ratelimitedRequest("delete", "/account", req =>
        req.send({ password })
      ).then(res => res.body.email_token);
    } catch (err) {
      throw this.handleErr(err);
    }
  }

  /**
   * The files and the shortened urls created
   * @typedef AllContent
   * @type {Object}
   * @property {Files} files The files uploaded
   * @property {Shortens} shortens The shortened URLs created
   */

  /**
   * Gets a list of all the files the user has uploaded and the links they've shortened
   * @param {Number} pageNum - The page to fetch files for
   * @returns {Promise<AllContent>} The files and shortens created by the user
   * @api public
   */
  async getFiles(pageNum = 0) {
    if (!this.token) throw new Error("BAD_AUTH");

    try {
      const content = await this.ratelimitedRequest("get", "/list", req =>
        req.query({ page: pageNum })
      ).then(res => res.body);
      this.shortens = content.shortens;
      this.files = content.files;
      return content;
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
    } else if (err.status == 469) {
      return new Error("QUOTA_EXPLODED");
    }
    return err;
  }

  /**
   * Setup function called every time a request needs to be made (usually only once, but when ratelimited this can be called a few times)
   * @typedef {Function} RequestSetup
   * @param {superagent.Request} req The request to set necessary options once
   */

  /**
   * Used internally to make ratelimit-abiding requests to API endpoints, adds an Authorization header
   * @param {String} method - The type of request to make (get, post, patch, etc)
   * @param {String} url - The endpoint upon which to perform this request, is appended to the API base url of the client
   * @param {RequestSetup} [setup] - The setup function gets called to apply any options needed to the request
   * @returns {superagent.Response} The request created by this
   * @api private
   */
  async ratelimitedRequest(method, url, setup) {
    const req = superagent[method.toLowerCase()](this.endpoint + url).set(
      "Authorization",
      this.token
    );
    if (setup) setup(req);
    try {
      return await req;
    } catch (err) {
      if (
        err.response &&
        err.response.body &&
        !isNaN(err.response.body.retry_after)
      ) {
        return await new Promise(resolve =>
          setTimeout(
            async () =>
              resolve(await this.ratelimitedRequest(method, url, setup)),
            err.response.body.retry_after * 1000
          )
        );
      } else throw err;
    }
  }

  /**
   * Used internally to make requests to API endpoints, adds an Authorization header
   * @param {String} method - The type of request to make (get, post, patch, etc)
   * @param {String} url - The endpoint upon which to perform this request, is appended to the API base url of the client
   * @deprecated since [63a036d84fc959c4ba6a3591cf2d4db7caf523e6], use ratelimitedRequest wherever possible
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
