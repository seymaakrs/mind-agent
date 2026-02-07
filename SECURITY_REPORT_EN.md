# Security Analysis Report

### 1. Server-Side Request Forgery (SSRF)
*   **Vulnerability Type:** Injection Vulnerabilities (SSRF)
*   **Severity:** **Critical**
*   **Source Location:** `src/tools/web_tools.py` (Lines 126-128)
*   **Description:** The `scrape_website` and `scrape_for_seo` functions accept a user-controlled `url` parameter and perform an HTTP GET request to it using `httpx` without any validation or allowlisting. This allows an attacker to force the server to make requests to internal resources, such as the cloud metadata server (e.g., `http://169.254.169.254/latest/meta-data/` on Cloud Run/AWS/GCP) to steal service account credentials, or to scan internal network ports.
*   **Line Content:**
    ```python
    response = await client.get(
        url,
        follow_redirects=True,
    ```
*   **Recommendation:** Implement strict URL validation before making the request.
    1.  Validate that the URL scheme is `http` or `https`.
    2.  Resolve the hostname to an IP address and check if it falls within private/internal IP ranges (e.g., `127.0.0.1`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`).
    3.  Disallow redirects or re-validate the URL after each redirect to prevent bypasses.

### 2. Broken Access Control (Firestore IDOR)
*   **Vulnerability Type:** Broken Access Control
*   **Severity:** **High**
*   **Source Location:** `src/tools/orchestrator_tools.py` (Lines 100-104, 144-150)
*   **Description:** The `get_document` and `save_document` tools allow the caller to specify an arbitrary `collection` or `document_path`. Since the application uses a privileged service account, there are no checks to ensure the user is authorized to access the specified collection. An attacker (via prompt injection or direct API use) can read or overwrite sensitive documents in other collections (e.g., `settings`, `users`) or other businesses' data.
*   **Line Content:**
    ```python
    async def get_document(
        document_path: str | None = None,
        document_id: str | None = None,
        collection: str = "documents",
    ) -> dict[str, Any]:
    ```
*   **Recommendation:** Restrict the tools to only access specific, safe collections (e.g., only `businesses`). Enforce that the `business_id` in the path matches the authenticated user's context, rather than accepting it as an open parameter.

### 3. Missing Authentication
*   **Vulnerability Type:** Authentication
*   **Severity:** **High**
*   **Source Location:** `src/app/api.py` (Lines 48-49)
*   **Description:** The `/task` endpoint is publicly exposed and does not implement any authentication mechanism. Any user can send a POST request to this endpoint to trigger the orchestrator agent. This can lead to unauthorized usage, data manipulation, and Denial of Wallet (resource exhaustion via LLM costs).
*   **Line Content:**
    ```python
    @app.post("/task")
    async def run_task(payload: TaskRequest):
    ```
*   **Recommendation:** Implement authentication middleware. Verify a valid API key or Bearer token in the request headers before processing the task.

### 4. Broken Access Control (Instagram Analytics IDOR)
*   **Vulnerability Type:** Broken Access Control
*   **Severity:** **High**
*   **Source Location:** `src/tools/instagram_tools.py` (Lines 13-14)
*   **Description:** The `get_instagram_insights` tool accepts a `late_profile_id` directly from the input. The `LateClient` uses a shared API key to make requests. If the API key has access to all profiles, a user can provide a victim's `late_profile_id` to view their private analytics data.
*   **Line Content:**
    ```python
    async def get_instagram_insights(
        late_profile_id: str,
    ```
*   **Recommendation:** Do not accept `late_profile_id` as a parameter from the tool. Instead, derive it securely from the authenticated user's session or business profile stored in the database, ensuring the user owns the profile they are querying.

### 5. Insecure CORS Configuration
*   **Vulnerability Type:** Insecure Data Handling
*   **Severity:** **Medium**
*   **Source Location:** `src/app/api.py` (Line 25)
*   **Description:** The application is configured to allow Cross-Origin Resource Sharing (CORS) from any origin (`*`). This is overly permissive and allows malicious websites to make requests to the API on behalf of a user if browser-based authentication were to be added in the future.
*   **Line Content:**
    ```python
    allow_origins=["*"],
    ```
*   **Recommendation:** Restrict `allow_origins` to a specific list of trusted domains (e.g., the frontend application's domain).

### 6. Arbitrary File Overwrite (Path Traversal)
*   **Vulnerability Type:** Insecure Data Handling
*   **Severity:** **Medium**
*   **Source Location:** `src/tools/image_tools.py`
*   **Description:** The `generate_image` tool constructs the file path using `f"images/{business_id}/{file_name}"`. While GCS is an object store, using `../` in the `file_name` could potentially allow writing files outside the intended directory structure (e.g. `images/target_biz/file.png`), overwriting other users' data. This is exacerbated by the fact that `business_id` is also user-controlled.
*   **Recommendation:** Sanitize `file_name` to remove directory traversal characters (`../`, `\..`) and restrict it to a safe set of characters (alphanumeric, dashes, underscores).
