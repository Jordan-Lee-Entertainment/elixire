# Authentication

## Hashing

bcrypt is used to hash and salt passwords with a work factor of 14.

[bcrypt]: https://en.wikipedia.org/wiki/Bcrypt

## Tokens

[itsdangerous] is used to create tokens. It uses HMAC-SHA1 internally.

[itsdangerous]: https://pythonhosted.org/itsdangerous/
