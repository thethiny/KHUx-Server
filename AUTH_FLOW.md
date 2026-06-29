# KHUx Authentication and Session Handling Flow

Complete documentation of the client-server authentication protocol, derived from
IDA9 decompilation of `libcocos2dcpp.so` (v5.0.1 ARM64) and the `khuxdecrypt3`
reference tool.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Initial Handshake](#2-initial-handshake)
3. [Session Establishment](#3-session-establishment)
4. [Request Encryption](#4-request-encryption)
5. [Response Decryption](#5-response-decryption)
6. [Session Maintenance](#6-session-maintenance)
7. [Error Handling](#7-error-handling)
8. [Crypto Implementation Details](#8-crypto-implementation-details)
9. [HTTP Headers](#9-http-headers)
10. [Key Source Files](#10-key-source-files)

---

## 1. Architecture Overview

```
Client (v5.0.1 APK)
  APIManager                    -- game logic, JSON parsing (libcocos2dcpp_0003.c)
    -> hole::network::api::Client   -- request building, action dispatch (libcocos2dcpp_0002.c)
      -> hole::network::RESTClient  -- HTTP dispatch, response callback (libcocos2dcpp_0001.c)
        -> cocos2d::network::HttpClient  -- threading (libcocos2dcpp_0026.c)
          -> libcurl 7.52.1              -- TLS transport (libcocos2dcpp_0035.c)
```

### Endpoints

| Host | Purpose |
|------|---------|
| `api-s.kingdomhearts.com` | Game API (REST, encrypted payloads) |
| `psg.sqex-bridge.jp` | Session provider / native auth |
| `cache.sqex-bridge.jp` | News/information pages (unencrypted) |

### Configuration Files (client-side)

- `json/server_config.json` -- contains `serverURLDomain` (base URL for API)
- `json/server_api.json` -- contains `actions[]` array, each with `path` and `method`

The client loads these at startup in `sub_415C58` (ea=0x415C58, libcocos2dcpp_0002.c:24660).

---

## 2. Initial Handshake

### Step 1: UUID Generation

The client generates a device UUID via JNI on first launch:

```c
// sub_489BD0 (ea=0x489BD0) -- libcocos2dcpp_0003.c:56590
java.util.UUID.randomUUID()
uuid.getMostSignificantBits()   -> 8 bytes
uuid.getLeastSignificantBits()  -> 8 bytes
```

The 16 UUID bytes are stored in `AppState::setupUUID()` and persisted locally.
The UUID is formatted as a string via `sub_4A9C94` for use in requests.

### Step 2: Native Login Request

The client sends an initial login to `psg.sqex-bridge.jp` with:

```
UUID=<device_uuid_string>
```

This is formatted in `sub_4F7E1C` (ea=0x4F7E1C, libcocos2dcpp_0006.c:1089):
```c
format_buffer(v65, "UUID=%s", uuid_string);
```

The request also includes a format string from offset 116 of the global state
(`sub_41C32C()`) which appears to be the bridge URL pattern, and a numeric token
from `sub_3BBE30(0, 101000011, &v51)`.

### Step 3: Bridge Response

The bridge server responds with a JSON object containing:

```json
{
  "nativeToken": "<token_string>",
  "nativeSessionId": "<session_id_string>",
  "sharedSecurityKey": "<32_byte_hex_or_base64_key>"
}
```

Parsed in `sub_3D8E34` (ea=0x3D8E34, libcocos2dcpp_0001.c:25914) -- extracts
`nativeToken` for subsequent requests.

---

## 3. Session Establishment

### Receiving the Security Key

Function `sub_417AE4` (ea=0x417AE4, libcocos2dcpp_0002.c:26024) processes the
bridge response:

```c
// Extract both fields from JSON response
v8 = sub_3C1804(response, "nativeSessionId");
v9 = sub_3C1804(response, "sharedSecurityKey");

// Verify both are present (string type check: byte+18 & 0x10)
if ((*(BYTE*)v8 + 18) & 0x10) && (*(BYTE*)v9 + 18) & 0x10))
{
    // Get the main game state
    v11 = sub_49CDE0(v9);

    // Store the nativeSessionId into the crypto manager
    sub_4A9F80(v11, nativeSessionId_value);

    // Initialize AES-256-CBC cipher with sharedSecurityKey
    cipher = operator new(0x58);
    sub_489B04(cipher + 3, sharedSecurityKey_bytes);  // 32-byte key init
}
```

### Key Storage via XOR-LCG Obfuscation

The 32-byte AES key is stored internally using XOR obfuscation with an LCG
(Linear Congruential Generator):

```c
// sub_3937EC (ea=0x3937EC) -- libcocos2dcpp_0000.c:4840
// Used for both encoding (storage) and decoding (retrieval)
for each byte:
    decoded_byte = stored_byte ^ ((214013 * (offset + seed) + 2531011) >> 16)
```

Constants `214013` and `2531011` are the classic MSVC `rand()` LCG parameters.
This is NOT real encryption -- it is an obfuscation layer to prevent trivial
memory scanning.

### Session ID Storage

The `nativeSessionId` is stored at offset 0 of the crypto state buffer (32 bytes,
via `sub_4A9F80`). It is later sent as the `X-Sqex-Hole-Nsid` HTTP header.

---

## 4. Request Encryption

### Overview

For game API calls (method=POST), the full pipeline is:

```
1. Build key-value parameters (JSON or form-encoded)
2. Serialize to query string (key=value&key=value)
3. Encrypt with AES-256-CBC (PKCS7 padding, zero IV)
4. Base64 encode the ciphertext
5. URL-encode the base64 string into: v=<base64_ciphertext>
6. Send as POST body with Content-Type: application/x-www-form-urlencoded
```

### Step-by-step Detail

#### 4.1 Parameter Assembly

The body is built by `sub_417990` (ea=0x417990, libcocos2dcpp_0002.c:25947):

```c
// Start with mode parameter
format_buffer(buf, "m=%d", mode);   // mode from game state

// Append session index if available
format_buffer(buf, "&i=%lld", session_index);
```

On first request (non-retry), additional fields are added via `sub_3CEFF8`:

| Field | Type | Description |
|-------|------|-------------|
| `ruv` | int | Resource update version |
| `deviceType` | int | Device type ID (2=Android, 8=iOS) |
| `systemVersion` | string | OS version string |
| `appVersion` | string | App version string |

#### 4.2 JSON Serialization (POST with body)

For POST requests with JSON body (`a4=1` in `sub_3C9628`), the data is
serialized via `sub_3C9ED4` into a JSON string using rapidjson. For GET-style
form-encoded data (`a4=0`), key-value pairs are joined with `&` separators via
`sub_3CA2F8`.

The result is prepended with `v=` when encryption is active:

```c
// sub_3C9628, line 12785
if (has_key)
    sub_3A99C8(body, "v=");
string_concat(body, serialized_params, strlen(serialized_params));
```

#### 4.3 AES-256-CBC Encryption

Performed by `sub_489B7C` -> `sub_489980` (ea=0x489980, libcocos2dcpp_0003.c:56463):

```c
// Encrypt mode (a2=0):
AES_set_encrypt_key(key_32bytes, 256, &schedule);

// PKCS7 padding
pad_len = 16 - (data_len & 0xF);       // always 1-16 bytes
padded = malloc(data_len + pad_len);
memcpy(padded, data, data_len);
memset(padded + data_len, pad_len, pad_len);

// CBC with zero IV
iv[0] = 0;  iv[1] = 0;  // 16 bytes of zeros
AES_cbc_encrypt(padded, output, padded_len, &schedule, iv, AES_ENCRYPT);
```

**Key parameters:**
- Algorithm: AES-256-CBC
- Key: 32 bytes from `sharedSecurityKey`
- IV: **All zeros** (16 bytes, hardcoded)
- Padding: PKCS7 (RFC 5652)

#### 4.4 Base64 Encode

The encrypted bytes are base64-encoded by `sub_A4A8A8` (ea=0xA4A8A8,
libcocos2dcpp_0034.c:5734):

```c
// Output size calculation: 4 * ceil(len / 3)
output_len = 4 * len / 3 + (len % 3 != 0 ? 4 : 0);
output = malloc(output_len + 1);
sub_A4A6F8(input, len, output);   // standard base64 encode
```

#### 4.5 URL Encoding

The base64 string is then URL-encoded via `sub_AA08BC` (libcurl's
`curl_easy_escape`) for safe transmission as a form value.

#### 4.6 Final POST Body

```
v=<url_encoded_base64_of_aes_ciphertext>&m=<mode>&i=<session_index>
```

Or for the first request of a session:
```
v=<url_encoded_base64>&m=<mode>&i=<session_index>&ruv=<n>&deviceType=<n>&systemVersion=<str>&appVersion=<str>
```

---

## 5. Response Decryption

### Overview

```
1. Receive HTTP response body (raw bytes)
2. URL-decode (via libcurl)
3. Base64 decode
4. AES-256-CBC decrypt (PKCS7 unpadding, zero IV)
5. Parse resulting string as JSON (rapidjson)
```

### Step-by-step Detail

#### 5.1 URL Decode + Base64 Decode

In `sub_3CA674` (response handler callback, libcocos2dcpp_0001.c:14051):

```c
// URL decode the response
result = sub_AA0A2C(http_client, response_data, response_len, &decoded_len);

// Base64 decode
decoded_data = NULL;
actual_len = sub_A4A7E4(result, decoded_len, &decoded_data);
```

`sub_A4A7E4` (ea=0xA4A7E4, libcocos2dcpp_0034.c:5705) allocates
`ceil(len * 3 / 4)` bytes and calls `sub_A4A5B4` for standard base64 decode.

#### 5.2 AES-256-CBC Decryption

```c
// sub_489B94 -> sub_489980 with a2=1 (decrypt)
// libcocos2dcpp_0001.c:14059
sub_489B94(&result, crypto_key_ptr, decoded_data, decoded_len);
```

Inside `sub_489980` (decrypt mode):

```c
// Verify alignment
if ((data_len & 0xF) != 0) return NULL;   // must be 16-byte aligned

AES_set_decrypt_key(key_32bytes, 256, &schedule);

iv[0] = 0;  iv[1] = 0;  // zero IV
AES_cbc_encrypt(input, output, data_len, &schedule, iv, AES_DECRYPT);

// Strip PKCS7 padding
actual_len = data_len - output[data_len - 1];
```

#### 5.3 JSON Parsing

The decrypted plaintext is a JSON string, parsed by `sub_3C18D8` which wraps
rapidjson's `GenericDocument::Parse()`.

---

## 6. Session Maintenance

### Session State Fields (from server response)

The server's response to the login/status check contains these fields
(parsed in libcocos2dcpp_0001.c:25470):

```json
{
  "ret": {
    "isMaintenance": true/false,
    "isKhuxMaintenance": true/false,
    "isDarkMaintenance": true/false,
    "isPhotonMaintenance": true/false,
    "sessionTO": true/false,
    "isNewDayPeriod": true/false,
    "isRetry": true/false,
    "versionApp": "5.0.1",
    "versionRes": 1234,
    "versionResLow": 5678,
    "versionDat": 9012,
    "commonVersionDat": 3456,
    "darkVersionRes": 7890,
    "login": <int>,
    "continueLogin": <int>,
    "continueLoginCount": <int>
  }
}
```

### Session Timeout Handling

- `sessionTO == true` (value 258 internally) indicates the session has expired
- The client checks this on every response and triggers re-authentication
- `isRetry == true` means the server wants the client to retry the request

### Retry Mechanism

The `X-Sqex-Hole-Retry` header carries the retry count (0 or 1). When the
server signals `isRetry`, the client resends with the retry flag set.

### Continue Login

The `continueLoginCount` field tracks consecutive logins. It is sent back to the
server in subsequent requests and displayed in the UI.

### X-HTTP-USER-TOKEN

A separate user token is maintained at offset 31 of the global state singleton
(`sub_41C32C()`) and sent as `X-HTTP-USER-TOKEN: <token>` on certain API calls
(built in libcocos2dcpp_0003.c:45738). This appears to be used for auxiliary
APIs (board rooms, social features).

---

## 7. Error Handling

### Authentication Failure Path

When `sub_417AE4` fails to extract both `nativeSessionId` and `sharedSecurityKey`:

```c
// Falls through to error handler
sub_417494(a1, action_index, response);
```

`sub_417494` (ea=0x417494, libcocos2dcpp_0002.c:25690) dispatches the error to
the registered callback, which triggers `APIManager::openErrorDialog`.

### Maintenance Detection

The `appStatus` response field is checked in `sub_417C4C`
(libcocos2dcpp_0002.c:26072). It contains:

```json
{
  "appStatus": {
    "mode": "<mode_string>",
    "current": "<current_version>",
    "server": "<server_url>"
  }
}
```

When `mode` indicates maintenance, the client shows the maintenance screen.
The `server` field can redirect to a different server URL (stored at offset 240
of the client object).

### Decryption Failure

If AES decryption returns NULL (misaligned data, wrong key):

```c
// sub_489980: returns a5 = {0, 0} on failure
if ((data_len & 0xF) != 0) {
    *a5 = 0;
    a5[1] = 0;
    return;
}
```

The caller checks for NULL and falls through to the error handler, which
typically shows a network error dialog.

### Version Mismatch

When `systemStatusUpdateResult` is stale or the version check fails, the client
attempts to update via the `server` field in `appStatus`. It searches the
response for "http" prefix (bytes 104, 116, 116, 112) to validate it as a URL.

---

## 8. Crypto Implementation Details

### AES-256-CBC

| Parameter | Value |
|-----------|-------|
| Algorithm | AES-256-CBC |
| Key size | 256 bits (32 bytes) |
| Block size | 128 bits (16 bytes) |
| IV | All zeros (16 bytes) |
| Padding | PKCS7 |
| Library | OpenSSL `AES_cbc_encrypt` (ARMv8 hardware AES) |

**IMPORTANT**: The IV is always zero. This means the first block of each message
encrypted with the same key will produce the same ciphertext for the same
plaintext. For a private server, this is fine -- just replicate the same behavior.

### Key Obfuscation (Storage Only)

The 32-byte AES key is XOR-obfuscated in memory using:

```
LCG(n) = (214013 * n + 2531011) >> 16
decoded[i] = stored[i] ^ LCG(offset + seed)
```

where `seed` is stored at `*(DWORD*)(obj + 8)` and `offset` starts at the
`a5` parameter (usually 0).

This is the same LCG as MSVC's `rand()`. It is NOT part of the network protocol
-- only used for in-memory obfuscation.

### Base64

Standard base64 encoding/decoding (RFC 4648). No URL-safe variant -- the result
is URL-encoded separately via libcurl.

### MD5 for Key Hashing

`sub_48A14C` (ea=0x48A14C, libcocos2dcpp_0003.c:56748) computes MD5 of a key
and returns the hex-encoded digest (32 chars). This is used for file integrity
verification, not for the main encryption flow.

---

## 9. HTTP Headers

### Request Headers

| Header | Value | When |
|--------|-------|------|
| `Content-Type` | `application/x-www-form-urlencoded;charset=UTF8` | POST requests |
| `X-Sqex-Hole-Retry` | `0` or `1` | All API requests |
| `X-Sqex-Hole-Nsid` | `<nativeSessionId>` | After session established |
| `X-HTTP-USER-TOKEN` | `<user_token>` | Social/board API calls |

### Cookie Handling

The client uses libcurl's cookie engine with a local `cookieFile.txt`
(referenced in libcocos2dcpp_0026.c:32851). Standard Netscape cookie file format.

---

## 10. Key Source Files

### Decompiled Source (IDA9)

| File | Key Content |
|------|-------------|
| `libcocos2dcpp_0000.c` | `sub_3937EC` -- XOR-LCG key decode |
| `libcocos2dcpp_0001.c` | `sub_3C8DD8` -- HTTP request builder; `sub_3C9628` -- request dispatch; response handler with decrypt |
| `libcocos2dcpp_0002.c` | `sub_415C58` -- API client init; `sub_416F3C` -- API request builder; `sub_417AE4` -- session key handler; `sub_417990` -- body params |
| `libcocos2dcpp_0003.c` | `sub_489980` -- AES-256-CBC encrypt/decrypt; `sub_489B04` -- key init; `sub_489BD0` -- UUID generation; `sub_48A14C` -- MD5 hash |
| `libcocos2dcpp_0004.c` | `sub_4A9F80` -- store nativeSessionId in crypto state |
| `libcocos2dcpp_0006.c` | `sub_4F7E1C` -- bridge login with UUID |
| `libcocos2dcpp_0010.c` | sqex-bridge.jp information URLs |
| `libcocos2dcpp_0026.c` | cocos2d HttpClient, cookieFile.txt |
| `libcocos2dcpp_0034.c` | `sub_A4A7E4` -- base64 decode; `sub_A4A8A8` -- base64 encode |
| `libcocos2dcpp_0035.c` | libcurl 7.52.1 transport layer |

### Reference Tools

| File | Content |
|------|---------|
| `khuxdecrypt3_r3/src/khuxdecrypt3.c` | BGAD asset decryption (XOR PRNG, ChaCha8); not directly related to API auth but shares LCG constants |

### External References

| Project | Contribution |
|---------|-------------|
| xlash123/khux-re-api | Documented AES-256-CBC API encryption, MITM proxy, data backup tools |

---

## Summary: Complete Request/Response Cycle

```
CLIENT                                          SERVER
  |                                               |
  |  1. POST psg.sqex-bridge.jp                   |
  |     Body: UUID=<device_uuid>                  |
  |  ------------------------------------------>  |
  |                                               |
  |  2. Response:                                 |
  |     { nativeSessionId, sharedSecurityKey,     |
  |       nativeToken }                           |
  |  <------------------------------------------  |
  |                                               |
  |  [Client stores 32-byte AES key]              |
  |                                               |
  |  3. POST api-s.kingdomhearts.com/<action>     |
  |     Headers:                                  |
  |       Content-Type: application/x-www-form-   |
  |         urlencoded;charset=UTF8               |
  |       X-Sqex-Hole-Retry: 0                   |
  |       X-Sqex-Hole-Nsid: <sessionId>          |
  |     Body:                                     |
  |       v=<urlencode(base64(AES(params)))>      |
  |  ------------------------------------------>  |
  |                                               |
  |  4. Response body:                            |
  |     <urlencode(base64(AES(json_response)))>   |
  |  <------------------------------------------  |
  |                                               |
  |  [Client: urldecode -> b64decode -> AES       |
  |   decrypt -> JSON parse]                      |
  |                                               |
  |  5. Repeat step 3-4 for each API call         |
  |     (same key, same zero IV)                  |
```

### For Private Server Implementation

1. **Bridge endpoint** (`psg.sqex-bridge.jp`): Return `nativeSessionId`,
   `sharedSecurityKey` (32 random bytes, hex-encoded), and `nativeToken`
2. **API endpoints** (`api-s.kingdomhearts.com`): Decrypt incoming `v=` parameter
   (URL-decode -> base64-decode -> AES-256-CBC decrypt with zero IV and the
   shared key), process the JSON, encrypt the response the same way
3. **Status response**: Always include `ret.sessionTO=false`,
   `ret.isMaintenance=false`, and valid version numbers
4. **Cookie file**: Not critical for server -- the client manages its own cookies
