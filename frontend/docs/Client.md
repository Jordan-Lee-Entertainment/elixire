## Classes

<dl>
<dt><a href="#Client">Client</a></dt>
<dd></dd>
</dl>

## Typedefs

<dl>
<dt><a href="#Files">Files</a> : <code>Object.&lt;Shortcode, File&gt;</code></dt>
<dd><p>Files uploaded by the user</p>
</dd>
<dt><a href="#Shortcode">Shortcode</a> : <code>String</code></dt>
<dd><p>The shortcode of a file/shorten</p>
</dd>
<dt><a href="#File">File</a> : <code>Object</code></dt>
<dd><p>An uploaded file</p>
</dd>
<dt><a href="#Shortens">Shortens</a> : <code>Object.&lt;Shortcode, Shorten&gt;</code></dt>
<dd><p>Shortened URLs created by the user</p>
</dd>
<dt><a href="#Shorten">Shorten</a> : <code>Object</code></dt>
<dd><p>Shortened URL</p>
</dd>
<dt><a href="#Profile">Profile</a> : <code>Object</code></dt>
<dd><p>A user&#39;s profile</p>
</dd>
<dt><a href="#Quota">Quota</a> : <code>Object</code></dt>
<dd><p>The quota of a user</p>
</dd>
<dt><a href="#Domains">Domains</a></dt>
<dd><p>Shows domains available to the user</p>
</dd>
<dt><a href="#AllContent">AllContent</a> : <code>Object</code></dt>
<dd><p>The files and the shortened urls created</p>
</dd>
<dt><a href="#DataDumpState">DataDumpState</a> : <code>Object</code></dt>
<dd></dd>
<dt><a href="#RequestSetup">RequestSetup</a> : <code>function</code></dt>
<dd><p>Setup function called every time a request needs to be made (usually only once, but when ratelimited this can be called a few times)</p>
</dd>
</dl>

<a name="Client"></a>

## Client
**Kind**: global class  

* [Client](#Client)
    * [new Client(options)](#new_Client_new)
    * [.token](#Client+token) : <code>String</code>
    * [.endpoint](#Client+endpoint) : <code>String</code>
    * [.profile](#Client+profile) : [<code>Profile</code>](#Profile)
    * [.quota](#Client+quota) : [<code>Quota</code>](#Quota)
    * [.files](#Client+files) : [<code>Files</code>](#Files)
    * [.shortens](#Client+shortens) : [<code>Shortens</code>](#Shortens)
    * [.getProfile()](#Client+getProfile) ⇒ [<code>Promise.&lt;Profile&gt;</code>](#Profile)
    * [.getDomains()](#Client+getDomains) ⇒ [<code>Promise.&lt;Domains&gt;</code>](#Domains)
    * [.updateAccount(changes)](#Client+updateAccount) ⇒ <code>Promise.&lt;Array&gt;</code>
    * [.deleteLink(shortcode)](#Client+deleteLink) ⇒ <code>Promise.&lt;Object&gt;</code>
    * [.deleteFile(shortcode)](#Client+deleteFile) ⇒ <code>Promise.&lt;Object&gt;</code>
    * [.generateToken(password, [username])](#Client+generateToken) ⇒ <code>Promise.&lt;String&gt;</code>
    * [.revokeTokens(password)](#Client+revokeTokens) ⇒ <code>Promise.&lt;Object&gt;</code>
    * [.upload(file)](#Client+upload) ⇒ <code>superagent.Request</code>
    * [.shortenUrl(longUrl)](#Client+shortenUrl) ⇒ <code>Promise.&lt;String&gt;</code>
    * [.getQuota()](#Client+getQuota) ⇒ [<code>Quota</code>](#Quota)
    * [.signup(params)](#Client+signup) ⇒ <code>Promise.&lt;Boolean&gt;</code>
    * [.login(username, password)](#Client+login) ⇒ <code>Promise.&lt;String&gt;</code>
    * [.deleteAccount(password)](#Client+deleteAccount) ⇒ <code>Promise.&lt;Boolean&gt;</code>
    * [.deleteConfirm(token)](#Client+deleteConfirm) ⇒ <code>Promise.&lt;Boolean&gt;</code>
    * [.resetPassword(username)](#Client+resetPassword) ⇒ <code>Promise.&lt;Boolean&gt;</code>
    * [.confirmPasswordReset(token, password)](#Client+confirmPasswordReset) ⇒ <code>Promise.&lt;Boolean&gt;</code>
    * [.getFiles(pageNum)](#Client+getFiles) ⇒ [<code>Promise.&lt;AllContent&gt;</code>](#AllContent)
    * [.dumpStatus()](#Client+dumpStatus) ⇒ [<code>Promise.&lt;DataDumpState&gt;</code>](#DataDumpState)
    * [.requestDump()](#Client+requestDump) ⇒ <code>Promise.&lt;Boolean&gt;</code>
    * [.handleErr()](#Client+handleErr) ⇒ <code>Error</code>
    * [.ratelimitedRequest(method, url, [setup])](#Client+ratelimitedRequest) ⇒ <code>superagent.Response</code>
    * ~~[.request(method, url)](#Client+request) ⇒ <code>superagent.Request</code>~~


* * *

<a name="new_Client_new"></a>

### new Client(options)
Create a client for the Elixire API


| Param | Type | Default | Description |
| --- | --- | --- | --- |
| options | <code>Object</code> |  | Options to instantiate the client with |
| options.endpoint | <code>String</code> |  | Endpoint to prefix all requests with, including the trailing /api |
| [options.token] | <code>String</code> | <code></code> | Token to use for authenticated routes |


* * *

<a name="Client+token"></a>

### client.token : <code>String</code>
The token used to make authenticated requests on the API

**Kind**: instance property of [<code>Client</code>](#Client)  

* * *

<a name="Client+endpoint"></a>

### client.endpoint : <code>String</code>
The endpoint to be prepended to API endpoints including the trailing /api

**Kind**: instance property of [<code>Client</code>](#Client)  

* * *

<a name="Client+profile"></a>

### client.profile : [<code>Profile</code>](#Profile)
The profile of the currently logged in user (Only set if getProfile() has been called)

**Kind**: instance property of [<code>Client</code>](#Client)  

* * *

<a name="Client+quota"></a>

### client.quota : [<code>Quota</code>](#Quota)
The quota of the currently logged in user (Only set if getQuota() has been called)

**Kind**: instance property of [<code>Client</code>](#Client)  

* * *

<a name="Client+files"></a>

### client.files : [<code>Files</code>](#Files)
The files created by the user

**Kind**: instance property of [<code>Client</code>](#Client)  

* * *

<a name="Client+shortens"></a>

### client.shortens : [<code>Shortens</code>](#Shortens)
The shortens created by the user

**Kind**: instance property of [<code>Client</code>](#Client)  

* * *

<a name="Client+getProfile"></a>

### client.getProfile() ⇒ [<code>Promise.&lt;Profile&gt;</code>](#Profile)
Gets the user's profile from the API

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: [<code>Promise.&lt;Profile&gt;</code>](#Profile) - The profile of the currently logged-in user  
**Api**: public  

* * *

<a name="Client+getDomains"></a>

### client.getDomains() ⇒ [<code>Promise.&lt;Domains&gt;</code>](#Domains)
Gets the domains currently available to the user

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: [<code>Promise.&lt;Domains&gt;</code>](#Domains) - Domains available to the user  
**Api**: public  

* * *

<a name="Client+updateAccount"></a>

### client.updateAccount(changes) ⇒ <code>Promise.&lt;Array&gt;</code>
Updates the account with the specified changes

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Promise.&lt;Array&gt;</code> - An array containing the list of fields that were modified  
**Api**: public  

| Param | Type | Description |
| --- | --- | --- |
| changes | <code>Object</code> | The changes to be applied to the account |
| changes.password | <code>String</code> | The password to be used to authenticate the changes (required) |
| [changes.new_password] | <code>String</code> | Optional parameter to set the user's password |
| [change.domain] | <code>Number</code> | Optional parameter to set the user's upload domain |
| [change.subdomain] | <code>String</code> | Optional parameter that sets the user's subdomain |


* * *

<a name="Client+deleteLink"></a>

### client.deleteLink(shortcode) ⇒ <code>Promise.&lt;Object&gt;</code>
Deletes a shortened URL

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Promise.&lt;Object&gt;</code> - The response body  
**Api**: public  

| Param | Type | Description |
| --- | --- | --- |
| shortcode | [<code>Shortcode</code>](#Shortcode) | The shortcode of the shortened link to delete |


* * *

<a name="Client+deleteFile"></a>

### client.deleteFile(shortcode) ⇒ <code>Promise.&lt;Object&gt;</code>
Deletes an uploaded file

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Promise.&lt;Object&gt;</code> - The response body  
**Api**: public  

| Param | Type | Description |
| --- | --- | --- |
| shortcode | [<code>Shortcode</code>](#Shortcode) | The shortcode of the file to be deleted |


* * *

<a name="Client+generateToken"></a>

### client.generateToken(password, [username]) ⇒ <code>Promise.&lt;String&gt;</code>
Generates an uploader API key

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Promise.&lt;String&gt;</code> - The generated API key  
**Api**: public  

| Param | Type | Default | Description |
| --- | --- | --- | --- |
| password | <code>String</code> |  | The user's password to authenticate with |
| [username] | <code>String</code> | <code>this.profile.username</code> | The username to login with |


* * *

<a name="Client+revokeTokens"></a>

### client.revokeTokens(password) ⇒ <code>Promise.&lt;Object&gt;</code>
Revokes all the user's tokens (uploader tokens and api keys)

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Promise.&lt;Object&gt;</code> - The response body  
**Api**: public  

| Param | Type | Description |
| --- | --- | --- |
| password | <code>String</code> | The user's password to authenticate with |


* * *

<a name="Client+upload"></a>

### client.upload(file) ⇒ <code>superagent.Request</code>
Uploads a file

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>superagent.Request</code> - The request object for the upload  
**Api**: public  

| Param | Type | Description |
| --- | --- | --- |
| file | [<code>File</code>](#File) | The file to be uploaded |


* * *

<a name="Client+shortenUrl"></a>

### client.shortenUrl(longUrl) ⇒ <code>Promise.&lt;String&gt;</code>
Shortens a given URL

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Promise.&lt;String&gt;</code> - The shortened URL  
**Api**: public  

| Param | Type | Description |
| --- | --- | --- |
| longUrl | <code>String</code> | The URL to be shortened |


* * *

<a name="Client+getQuota"></a>

### client.getQuota() ⇒ [<code>Quota</code>](#Quota)
Finds the user's quota

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: [<code>Quota</code>](#Quota) - The quotas of the user  
**Api**: public  

* * *

<a name="Client+signup"></a>

### client.signup(params) ⇒ <code>Promise.&lt;Boolean&gt;</code>
Creates a temporary account to be activated.

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Promise.&lt;Boolean&gt;</code> - Resolves with a boolean indicating success  
**Api**: public  

| Param | Type | Description |
| --- | --- | --- |
| params | <code>Object</code> | The details for the account to be created with |
| params.username | <code>String</code> | The username for the account |
| params.password | <code>String</code> | The password for the account |
| params.email | <code>String</code> | The email of the user for whom the account will be created |
| params.discord | <code>String</code> | The DiscordTag of the user for whom the account will be created in the form of username#0000 |


* * *

<a name="Client+login"></a>

### client.login(username, password) ⇒ <code>Promise.&lt;String&gt;</code>
Gets a token for the given username/password pair

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Promise.&lt;String&gt;</code> - The API token created  
**Api**: public  

| Param | Type | Description |
| --- | --- | --- |
| username | <code>String</code> | The username to login with |
| password | <code>String</code> | The password to login with |


* * *

<a name="Client+deleteAccount"></a>

### client.deleteAccount(password) ⇒ <code>Promise.&lt;Boolean&gt;</code>
Enters a request to delete the current user's account

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Promise.&lt;Boolean&gt;</code> - Boolean indicating success  
**Api**: public  

| Param | Type | Description |
| --- | --- | --- |
| password | <code>String</code> | The password to login with |


* * *

<a name="Client+deleteConfirm"></a>

### client.deleteConfirm(token) ⇒ <code>Promise.&lt;Boolean&gt;</code>
Confirms a user's account deletion

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Promise.&lt;Boolean&gt;</code> - Boolean indicating success  
**Api**: public  

| Param | Type | Description |
| --- | --- | --- |
| token | <code>String</code> | The token the user recieved in their email |


* * *

<a name="Client+resetPassword"></a>

### client.resetPassword(username) ⇒ <code>Promise.&lt;Boolean&gt;</code>
Sends an email to reset a user's password

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Promise.&lt;Boolean&gt;</code> - Boolean indicating success  
**Api**: public  

| Param | Type | Description |
| --- | --- | --- |
| username | <code>String</code> | The username to reset the password forgotten |


* * *

<a name="Client+confirmPasswordReset"></a>

### client.confirmPasswordReset(token, password) ⇒ <code>Promise.&lt;Boolean&gt;</code>
Confirms a user's password reset using token from email

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Promise.&lt;Boolean&gt;</code> - Boolean indicating success  
**Api**: public  

| Param | Type | Description |
| --- | --- | --- |
| token | <code>String</code> | The token the user got from their email |
| password | <code>Stirng</code> | The password to change to |


* * *

<a name="Client+getFiles"></a>

### client.getFiles(pageNum) ⇒ [<code>Promise.&lt;AllContent&gt;</code>](#AllContent)
Gets a list of all the files the user has uploaded and the links they've shortened

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: [<code>Promise.&lt;AllContent&gt;</code>](#AllContent) - The files and shortens created by the user  
**Api**: public  

| Param | Type | Default | Description |
| --- | --- | --- | --- |
| pageNum | <code>Number</code> | <code>0</code> | The page to fetch files for |


* * *

<a name="Client+dumpStatus"></a>

### client.dumpStatus() ⇒ [<code>Promise.&lt;DataDumpState&gt;</code>](#DataDumpState)
Gets status of a data dump (if applicable)

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: [<code>Promise.&lt;DataDumpState&gt;</code>](#DataDumpState) - The current state of the user's data dump  

* * *

<a name="Client+requestDump"></a>

### client.requestDump() ⇒ <code>Promise.&lt;Boolean&gt;</code>
Requests a data dump of the account to be added to the queue

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Promise.&lt;Boolean&gt;</code> - True if successful else fules  
**Api**: public  

* * *

<a name="Client+handleErr"></a>

### client.handleErr() ⇒ <code>Error</code>
Used internally to determine what type of error to throw

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>Error</code> - The error to be thrown  
**Params**: <code>Error</code> err - The error encountered while sending the request  
**Api**: private  

* * *

<a name="Client+ratelimitedRequest"></a>

### client.ratelimitedRequest(method, url, [setup]) ⇒ <code>superagent.Response</code>
Used internally to make ratelimit-abiding requests to API endpoints, adds an Authorization header

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>superagent.Response</code> - The request created by this  
**Api**: private  

| Param | Type | Description |
| --- | --- | --- |
| method | <code>String</code> | The type of request to make (get, post, patch, etc) |
| url | <code>String</code> | The endpoint upon which to perform this request, is appended to the API base url of the client |
| [setup] | [<code>RequestSetup</code>](#RequestSetup) | The setup function gets called to apply any options needed to the request |


* * *

<a name="Client+request"></a>

### ~~client.request(method, url) ⇒ <code>superagent.Request</code>~~
***Deprecated***

Used internally to make requests to API endpoints, adds an Authorization header

**Kind**: instance method of [<code>Client</code>](#Client)  
**Returns**: <code>superagent.Request</code> - The request created by this  
**Api**: private  

| Param | Type | Description |
| --- | --- | --- |
| method | <code>String</code> | The type of request to make (get, post, patch, etc) |
| url | <code>String</code> | The endpoint upon which to perform this request, is appended to the API base url of the client |


* * *

<a name="Files"></a>

## Files : <code>Object.&lt;Shortcode, File&gt;</code>
Files uploaded by the user

**Kind**: global typedef  

* * *

<a name="Shortcode"></a>

## Shortcode : <code>String</code>
The shortcode of a file/shorten

**Kind**: global typedef  

* * *

<a name="File"></a>

## File : <code>Object</code>
An uploaded file

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| shortname | [<code>Shortcode</code>](#Shortcode) | The shortcode of the file |
| size | <code>Number</code> | The size of the file in bytes |
| snowflake | <code>Number</code> | The snowflake/unique ID of the file |
| thumbnail | <code>String</code> | The URL to the small thumbnail of the file |
| url | <code>String</code> | The URL to the original file |


* * *

<a name="Shortens"></a>

## Shortens : <code>Object.&lt;Shortcode, Shorten&gt;</code>
Shortened URLs created by the user

**Kind**: global typedef  

* * *

<a name="Shorten"></a>

## Shorten : <code>Object</code>
Shortened URL

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| redirto | <code>String</code> | The URL the shorten points to |
| shortname | [<code>Shortcode</code>](#Shortcode) | The shortcode of the shorten |
| snowflake | <code>Number</code> | the snowflake/unique ID of the shorten |
| url | <code>String</code> | The shortened version of the URL |


* * *

<a name="Profile"></a>

## Profile : <code>Object</code>
A user's profile

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| active | <code>Boolean</code> | True if the account is not disabled |
| admin | <code>Boolean</code> | If the user is admin, true otherwise false |
| domain | <code>Number</code> | The ID of the currently selected domain |
| limits | [<code>Quota</code>](#Quota) | The quota of the user |
| subdomain | <code>String</code> | The subdomain of the user if they have a wildcard domain selected |
| user_id | <code>String</code> | The ID of the user |
| username | <code>String</code> | The username of the user |


* * *

<a name="Quota"></a>

## Quota : <code>Object</code>
The quota of a user

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| limit | <code>Number</code> | The user's weekly file cap in bytes |
| shortenlimit | <code>Number</code> | The user's weekly shortened URL cap |
| shortenused | <code>Number</code> | The number of shortened URLs the user has created during the quota period |
| used | <code>Number</code> | The total amount of storage used during this quota period by uploaded files in bytes |


* * *

<a name="Domains"></a>

## Domains
Shows domains available to the user

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| officialDomains | <code>Array</code> | Array of official domains |
| domains | <code>Object.&lt;String, String&gt;</code> | Domain names indexed by ID |


* * *

<a name="AllContent"></a>

## AllContent : <code>Object</code>
The files and the shortened urls created

**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| files | [<code>Files</code>](#Files) | The files uploaded |
| shortens | [<code>Shortens</code>](#Shortens) | The shortened URLs created |


* * *

<a name="DataDumpState"></a>

## DataDumpState : <code>Object</code>
**Kind**: global typedef  
**Properties**

| Name | Type | Description |
| --- | --- | --- |
| state | <code>String</code> | The basic state the data dump is in, either in_queue not_in_queue or processing |
| [files_done] | <code>Number</code> | The amount of files done processing |
| [total_files] | <code>Number</code> | The total amount of files that need processing |
| [position] | <code>Number</code> | The position in the queue |


* * *

<a name="RequestSetup"></a>

## RequestSetup : <code>function</code>
Setup function called every time a request needs to be made (usually only once, but when ratelimited this can be called a few times)

**Kind**: global typedef  

| Param | Type | Description |
| --- | --- | --- |
| req | <code>superagent.Request</code> | The request to set necessary options once |


* * *

