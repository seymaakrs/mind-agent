# Güvenlik Analizi Raporu

### 1. Sunucu Taraflı İstek Sahteciliği (SSRF)
*   **Zafiyet Türü:** Enjeksiyon Zafiyetleri (SSRF)
*   **Önem Derecesi:** **Kritik**
*   **Kaynak Konumu:** `src/tools/web_tools.py` (Satır 126-128)
*   **Açıklama:** `scrape_website` ve `scrape_for_seo` fonksiyonları, kullanıcı tarafından kontrol edilen bir `url` parametresini kabul eder ve herhangi bir doğrulama veya izin listesi kontrolü yapmadan `httpx` kullanarak bu adrese HTTP GET isteği gönderir. Bu durum, bir saldırganın sunucuyu dahili kaynaklara (örneğin Cloud Run/AWS/GCP üzerindeki `http://169.254.169.254/latest/meta-data/` gibi cloud metadata sunucularına) istek göndermeye zorlamasına, servis hesabı kimlik bilgilerini çalmasına veya dahili ağ portlarını taramasına olanak tanır.
*   **Satır İçeriği:**
    ```python
    response = await client.get(
        url,
        follow_redirects=True,
    ```
*   **Öneri:** İstek yapmadan önce sıkı bir URL doğrulaması uygulayın.
    1.  URL şemasının `http` veya `https` olduğunu doğrulayın.
    2.  Hostname'i IP adresine çözümleyin ve özel/dahili IP aralıklarında (örn. `127.0.0.1`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`) olup olmadığını kontrol edin.
    3.  Yönlendirmeleri (redirects) engelleyin veya her yönlendirmeden sonra URL'yi tekrar doğrulayın.

### 2. Bozuk Erişim Kontrolü (Firestore IDOR)
*   **Zafiyet Türü:** Bozuk Erişim Kontrolü (Broken Access Control)
*   **Önem Derecesi:** **Yüksek**
*   **Kaynak Konumu:** `src/tools/orchestrator_tools.py` (Satır 100-104, 144-150)
*   **Açıklama:** `get_document` ve `save_document` araçları, çağrıcının keyfi bir `collection` (koleksiyon) veya `document_path` (doküman yolu) belirtmesine izin verir. Uygulama yetkili bir servis hesabı kullandığından, kullanıcının belirtilen koleksiyona erişim yetkisi olup olmadığını kontrol eden bir mekanizma yoktur. Bir saldırgan (prompt enjeksiyonu veya doğrudan API kullanımı yoluyla), diğer koleksiyonlardaki (örn. `settings`, `users`) veya diğer işletmelere ait hassas verileri okuyabilir veya üzerine yazabilir.
*   **Satır İçeriği:**
    ```python
    async def get_document(
        document_path: str | None = None,
        document_id: str | None = None,
        collection: str = "documents",
    ) -> dict[str, Any]:
    ```
*   **Öneri:** Araçların yalnızca belirli, güvenli koleksiyonlara (örneğin sadece `businesses`) erişmesini sağlayın. Yoldaki `business_id`'nin, açık bir parametre olarak kabul edilmesi yerine, kimliği doğrulanmış kullanıcının bağlamıyla (context) eşleşmesini zorunlu kılın.

### 3. Eksik Kimlik Doğrulama
*   **Zafiyet Türü:** Kimlik Doğrulama
*   **Önem Derecesi:** **Yüksek**
*   **Kaynak Konumu:** `src/app/api.py` (Satır 48-49)
*   **Açıklama:** `/task` endpoint'i halka açıktır ve herhangi bir kimlik doğrulama mekanizması uygulamaz. Herhangi bir kullanıcı, orchestrator ajanını tetiklemek için bu endpoint'e POST isteği gönderebilir. Bu durum yetkisiz kullanıma, veri manipülasyonuna ve "Denial of Wallet" (LLM maliyetleri üzerinden kaynak tüketimi) saldırılarına yol açabilir.
*   **Satır İçeriği:**
    ```python
    @app.post("/task")
    async def run_task(payload: TaskRequest):
    ```
*   **Öneri:** Kimlik doğrulama katmanı (middleware) ekleyin. İsteği işlemeden önce istek başlıklarında (headers) geçerli bir API Anahtarı veya Bearer Token doğrulayın.

### 4. Bozuk Erişim Kontrolü (Instagram Analitik IDOR)
*   **Zafiyet Türü:** Bozuk Erişim Kontrolü
*   **Önem Derecesi:** **Yüksek**
*   **Kaynak Konumu:** `src/tools/instagram_tools.py` (Satır 13-14)
*   **Açıklama:** `get_instagram_insights` aracı, girdiden doğrudan `late_profile_id` parametresini kabul eder. `LateClient`, istekleri yapmak için paylaşılan bir API anahtarı kullanır. Eğer API anahtarı tüm profillere erişim yetkisine sahipse, bir kullanıcı kurbanın `late_profile_id` bilgisini vererek onun özel analitik verilerini görüntüleyebilir.
*   **Satır İçeriği:**
    ```python
    async def get_instagram_insights(
        late_profile_id: str,
    ```
*   **Öneri:** `late_profile_id` bilgisini araç parametresi olarak kabul etmeyin. Bunun yerine, bu bilgiyi kimliği doğrulanmış kullanıcının oturumundan veya veritabanındaki işletme profilinden güvenli bir şekilde alın ve kullanıcının sorguladığı profilin sahibi olduğundan emin olun.

### 5. Güvensiz CORS Yapılandırması
*   **Zafiyet Türü:** Güvensiz Veri İşleme
*   **Önem Derecesi:** **Orta**
*   **Kaynak Konumu:** `src/app/api.py` (Satır 25)
*   **Açıklama:** Uygulama, Cross-Origin Resource Sharing (CORS) için herhangi bir kaynağa (`*`) izin verecek şekilde yapılandırılmıştır. Bu çok geniş bir izindir ve gelecekte tarayıcı tabanlı kimlik doğrulama eklenirse, kötü amaçlı web sitelerinin kullanıcı adına API'ye istek göndermesine izin verebilir.
*   **Satır İçeriği:**
    ```python
    allow_origins=["*"],
    ```
*   **Öneri:** `allow_origins` ayarını yalnızca güvenilir alan adlarından (örneğin, frontend uygulamasının domain'i) oluşan belirli bir listeyle sınırlandırın.

### 6. Keyfi Dosya Üzerine Yazma (Path Traversal)
*   **Zafiyet Türü:** Güvensiz Veri İşleme
*   **Önem Derecesi:** **Orta**
*   **Kaynak Konumu:** `src/tools/image_tools.py`
*   **Açıklama:** `generate_image` aracı dosya yolunu `f"images/{business_id}/{file_name}"` şeklinde oluşturur. GCS bir nesne depolama sistemi olsa da, `file_name` içinde `../` kullanılması, potansiyel olarak hedeflenen dizin yapısının dışına (örneğin `images/hedef_isletme/dosya.png`) dosya yazılmasına ve diğer kullanıcıların verilerinin üzerine yazılmasına izin verebilir. `business_id`'nin de kullanıcı tarafından kontrol edilebilir olması bu riski artırır.
*   **Öneri:** `file_name` içindeki dizin geçiş karakterlerini (`../`, `\..`) temizleyin (sanitize) ve dosya ismini güvenli bir karakter kümesiyle (alfanümerik, tire, alt çizgi) sınırlandırın.
