> Kaynak repo agent-mimari-referans kaldırılmadan önce süzülen özet. Tarih: 2026-06-07.

# Agent Mimari Referansı — Süzülen Özet

`agent-mimari-referans`, Hugging Face ml-intern framework'ünün soyulmuş bir
kopyasıydı. README'si eski/yanıltıcıydı; gerçek değer `agent/core/` ve
`backend/` altındaki **mimari desenlerdeydi**. Bu doküman bu desenlerin NE
OLDUĞUNU ve bizim `mind-agent` (FastAPI + OpenAI Agents SDK) sistemimizde neden
faydalı olabileceğini özetler.

Not: O repo `litellm` tabanlıydı, biz OpenAI Agents SDK kullanıyoruz. Yani kodu
kopyalamak değil, **desenleri** örnek almak için.

---

## 1. Agent Loop (ajan döngüsü) — `agent/core/agent_loop.py`

**Ne:** Klasik "düşün → araç çağır → sonucu geri besle → tekrarla" döngüsünün
sağlamlaştırılmış hali. Tek bir LLM çağrısı değil; model araç çağırdıkça döngü
dönüyor, sonuç gelene kadar.

Dikkate değer desenler:
- **Araç argümanı doğrulama** (`_validate_tool_args`): LLM bazen `args`'ı dict
  yerine string gönderir. Çağrıyı çalıştırmadan önce yapı doğrulanıp, hatalıysa
  modele düzeltici hata mesajı geri besleniyor (crash yok, kendini düzeltme var).
- **Onay (approval) mekanizması** (`_needs_approval`): Bazı araçlar (para/
  geri-dönülemez işlem) çalışmadan önce insan onayı bekletiyor. → Bizim "yeni
  kampanya hep PAUSED + onay" kuralımızla birebir örtüşür.
- **Geçici hata ayrımı** (`_is_transient_error`): 5xx/timeout/connection-reset
  gibi geçici hatalar kalıcı hatalardan ayrılıp retry/backoff uygulanıyor.
- **Dostça hata mesajı** (`_friendly_error_message`): Ham 400/500 yerine
  kullanıcıya/loglara anlamlı mesaj.

**Bize faydası:** Prospecting/Qualifier/Outreach agent'larında araç çağrı
döngüsünü daha dayanıklı yapmak için referans. Özellikle onay + geçici hata
backoff desenleri Sales akışına doğrudan uygulanabilir.

---

## 2. Doom-loop (sonsuz döngü) tespiti — `agent/core/doom_loop.py`

**Ne:** Ajan aynı aracı aynı argümanlarla tekrar tekrar çağırıp takılırsa
(örn. başarısız bir aramayı sürekli denemek), bu durum tespit edilip modele
"döngüye girdin, yaklaşımını değiştir" diyen düzeltici prompt enjekte ediliyor.

Nasıl: Son ~30 mesajdaki araç çağrıları `(araç_adı + argüman_hash'i)` imzasına
indirgenip tekrar sayısına bakılıyor.

**Bize faydası:** LLM token + para yakan en sinsi problem budur. Otonom çalışan
("insansız") bir reklam ajansında, gece boyu aynı hatalı API çağrısını döndürüp
maliyet patlatmayı önler. mind-agent'a düşük maliyetli bir koruma katmanı.

---

## 3. Prompt caching — `agent/core/prompt_caching.py`

**Ne:** Anthropic'in prompt caching özelliği. Her turda yeniden faturalanan
statik prefiksler (sistem promptu + araç tanımları, ~4-5K token) `cache_control`
breakpoint'leriyle önbelleğe alınıyor. 5 dakikalık TTL içindeki sonraki turlar
tam giriş fiyatı yerine ~%10 (cache_read) ödüyor.

Detaylar:
- 4 izinli breakpoint'ten 2'si kullanılıyor: (1) araç bloğu, (2) sistem mesajı.
- Anthropic dışı modeller için no-op (dokunmadan geçiyor).
- Orijinal liste mutate edilmiyor; kalıcı geçmiş bozulmuyor.

**Bize faydası:** mind-agent maliyeti (~$10-25/ay OpenAI) doğrudan token'a bağlı.
Büyük statik sistem promptları + araç katalogları olan agent'larda (orchestrator,
sales) caching ciddi tasarruf sağlar. OpenAI'da da analog otomatik prompt caching
mevcut; aynı prensip: statik prefiksleri sabit ve başta tut.

---

## 4. Context Manager (bağlam yönetimi + sıkıştırma) — `agent/context_manager/manager.py`

**Ne:** Konuşma geçmişini tutan, token sayımını yapan ve limit aşılınca
**otomatik sıkıştırma (compaction)** uygulayan katman.

Desenler:
- Model bazlı maksimum context token'ı LiteLLM kataloğundan dinamik çekiliyor
  (`get_model_info`), bilinmeyen model için güvenli 200k fallback.
- Eşik (threshold) aşılınca eski mesajlar LLM ile özetlenip yer açılıyor; bu
  bir "compacted" event'i olarak yayınlanıyor.
- Sistem promptu Jinja2 template ile render ediliyor (dinamik değişkenler).

**Bize faydası:** Uzun süren satış konuşmaları / çok adımlı prospecting görevleri
context limitine takılmadan devam edebilir. Bizim agent'larda uzun konuşma
hafızası gerektiğinde (lead geçmişi, etkileşim logu) bu compaction deseni örnek.

---

## 5. Queue-tabanlı async döngü + SSE transport — `backend/session_manager.py`, `backend/routes/agent.py`

**Ne:** Backend, ajan oturumunu iki `asyncio.Queue` ile yönetiyor:
- **submission_queue:** kullanıcı girdisi/onayı buraya düşer.
- **event_queue:** ajanın ürettiği olaylar (token chunk, araç çağrısı, hata,
  tamamlandı) buraya yazılır.

Her oturum kendi `asyncio.Task`'ında çalışıyor; bir **EventBroadcaster**
event_queue'yu okuyup birden fazla aboneye dağıtıyor (subscribe/unsubscribe).

**SSE (Server-Sent Events) transport** (`_sse_response`):
- `text/event-stream` ile olaylar canlı stream ediliyor.
- 15 saniyede bir `: keepalive` yorumu → proxy timeout'larını önler.
- Terminal event'ler (`turn_complete`, `error`, `interrupted`...) gelince
  stream kapanıyor.
- `/events/{session_id}` ayrı endpoint: bağlantı koparsa (ekran uyuması vb.)
  yeni girdi göndermeden tekrar bağlanma (re-attach) imkânı.

**Bize faydası:**
- mind-agent şu an `POST /task` ile senkron/tek-seferlik çalışıyor. Uzun süren
  görevlerde (prospecting taraması, çok adımlı analiz) **ilerlemeyi canlı
  göstermek** için SSE deseni doğrudan örnek alınabilir (örn. mind-id panelinde
  "agent şu an X yapıyor" canlı akışı).
- Queue ayrımı (girdi/çıktı) ajanı API isteğinden ayırır: istek biter, ajan
  arka planda çalışmaya devam eder; panel tekrar bağlanıp kaldığı yerden
  olayları izler. Bağlantı dayanıklılığı için sağlam bir model.

---

## 6. Model esnekliği (ikincil değer) — `effort_probe.py`, `model_switcher.py`, `llm_params.py`

**Ne:** Çalışma zamanında model değiştirme + her modelin desteklediği "reasoning
effort" seviyesini 1-token'lık probe ile keşfetme (capability tablosu tutmadan,
provider'ın kendisi validator). Hatada cascade ile bir alt seviyeye düşme.

**Bize faydası:** Şu an kritik değil (sabit OpenAI modeli kullanıyoruz). Ama
ileride maliyet/kalite dengesi için model seçimi gerekirse, "tablo tutma, probe
edip cascade ile düş" yaklaşımı bakım yükü düşük bir desen olarak akılda kalsın.

---

## Özet: mind-agent için öncelik sırası

| Desen | Bize uygunluk | Öncelik |
|---|---|---|
| Doom-loop tespiti | Otonom agent maliyet koruması | **Yüksek** |
| Onay + geçici hata backoff (agent loop) | Sales "PAUSED + onay" kuralıyla örtüşür | **Yüksek** |
| Prompt caching | Doğrudan maliyet tasarrufu | Orta-Yüksek |
| SSE + queue transport | Panelde canlı ilerleme/yeniden bağlanma | Orta (UX gerekince) |
| Context compaction | Uzun konuşma hafızası gerekince | Orta |
| Model probe/switch | Şimdilik gerekmiyor | Düşük |
