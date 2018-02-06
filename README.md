elixi.re v2
===============

```
"elixirae is the futureae"
  - lunae bunae genserv, 2018
```

elixi.re is a imagehost solution, the v1 was written in PHP,
v2 is being written in Python.

*(no, we won't write Elixir)*

# Running

get pythone!!!

```bash
python3.6 -m pip install -Ur requirements.txt
python3.6 run.py
```

# Operator's Manual

**TODO**

 - `scripts/adduser.py` adds a new user.

# API Documentation

**TODO**

There are two types of tokens, timed (tokens) and non-timed (API keys).

API keys should be used for your uploading program (KShare, sharenix, etc.).
Timed tokens should be used for the frontend (they expire in 3 days).

All tokens should be given in the `Authentication` header of your request.
It does not matter which token you put in, both types will be in the same header.

## Status Codes

On a non-500 error, you will get a error payload.

It is JSON with an `error` field (boolean, True),
and a `message` field (str)

### Known error codes
 - `400`
   - Bad Request, your input data is non-standard.
 - `403`
   - Failed Authentication, your token failed verification,
        or your username and password combo failed.


# `POST /api/login`
 - Should be the default way of logging-in, frontend wise.
 - Input: Receives JSON payload with `user` and `password` as fields.
 - Returns JSON with a `token` field, a timed token as value.

# `POST /api/apikey`
 - Main way to retrieve an api key for uploaders.
 - Input: Same as `POST /api/login`
 - Returns JSON with an `api_key` field, an API key as value.

# `POST /api/revoke`
 - Revoke all the user's current tokens.
 - All old tokens will become useless and invalid.
 - Input: Same as `POST /api/login`
 - Returns: JSON with an `ok` field, should be always `true`.

# `GET /api/profile`
 - Get your basic account information
 - Requires authentication
 - Input: None
 - Returns: JSON with many keys:
   - Example: ```javascript
{
    "user_id":"410159602408230912", // Your user ID, a snowflake
    "username":"lunae", // Your username
    "active":true, // If this account is active or not
    "admin":false, // If you are an admin account
    "domain":0 // Your current domain ID. (the domain you are using for your images)
}
   ```

# `GET /api/limits`
 - Get your limit information.
 - Requires authentication
 - Input: None
 - Returns JSON with `limit` key, as bytes (the unit of measurement)


# `POST /api/upload`
 - Incomplete route
 - Upload files
 - Only receives multipart formdata, nothing else, any field, only one file.
 - Returns: JSON with `url` key
