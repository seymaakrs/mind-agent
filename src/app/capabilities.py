"""Agent capabilities registry.

Single source of truth for what the system can do.
Used by both the /capabilities API endpoint (for the UI) and
can be referenced in agent instructions.
"""
from __future__ import annotations

CAPABILITIES: dict = {
    "version": "1.0",
    "categories": [
        {
            "id": "image",
            "name": "Görsel Üretme",
            "icon": "🖼️",
            "features": [
                {
                    "id": "generate_image",
                    "name": "Görsel Oluşturma",
                    "description": "Prompt'tan sıfırdan görsel üretme",
                    "engine": "Google Gemini",
                    "examples": [
                        "Ürün için modern bir banner oluştur",
                        "Logomuzla Instagram görseli yap",
                    ],
                },
                {
                    "id": "generate_image_from_source",
                    "name": "Kaynaktan Görsel Üretme",
                    "description": "Mevcut görsel veya logoyu referans alarak yeni görsel oluşturma",
                    "engine": "Google Gemini",
                    "examples": [
                        "Bu fotoğrafı kullanarak poster yap",
                        "Logoyu kullanarak sosyal medya görseli oluştur",
                    ],
                },
            ],
        },
        {
            "id": "video",
            "name": "Video Üretme",
            "icon": "🎬",
            "features": [
                {
                    "id": "generate_video_veo",
                    "name": "Video Oluşturma (Veo 3.1)",
                    "description": "Metinden yüksek kaliteli video üretme",
                    "engine": "Google Veo 3.1",
                    "examples": [
                        "Ürün tanıtım videosu oluştur",
                        "Instagram Reels için 9:16 video yap",
                    ],
                },
                {
                    "id": "generate_video_kling",
                    "name": "Video Oluşturma (Kling 3.0)",
                    "description": "Kling AI ile metin veya görselden video üretme",
                    "engine": "Kling AI 3.0",
                    "examples": [
                        "Kling ile kısa bir tanıtım klibi oluştur",
                        "Bu fotoğrafı animasyonlu videoya çevir",
                    ],
                },
                {
                    "id": "generate_video_heygen",
                    "name": "Video Oluşturma (HeyGen)",
                    "description": "HeyGen Video Agent ile AI destekli video üretme",
                    "engine": "HeyGen Video Agent",
                    "examples": [
                        "HeyGen ile kurumsal tanıtım videosu yap",
                        "Profesyonel sunum videosu oluştur",
                    ],
                },
                {
                    "id": "add_audio_to_video",
                    "name": "Videoya Ses Ekleme",
                    "description": "Var olan videoya AI ile ses efekti veya müzik ekleme",
                    "engine": "fal.ai MMAudio V2",
                    "examples": [
                        "Bu videoya neşeli fon müziği ekle",
                        "Videodaki sesi ambient ile değiştir",
                    ],
                },
            ],
        },
        {
            "id": "social_media",
            "name": "Instagram & Sosyal Medya",
            "icon": "📱",
            "features": [
                {
                    "id": "post_instagram",
                    "name": "Instagram Post Paylaşma",
                    "description": "Görsel veya videoyu Instagram'a otomatik paylaşma",
                    "examples": [
                        "Bu görseli Instagram'a paylaş",
                        "Reel'i yayınla",
                    ],
                },
                {
                    "id": "post_carousel",
                    "name": "Carousel Post",
                    "description": "Çoklu görsel ile Instagram carousel paylaşma",
                    "examples": [
                        "5 görselden oluşan carousel yap",
                        "Ürün kataloğunu carousel olarak paylaş",
                    ],
                },
                {
                    "id": "content_plan",
                    "name": "Haftalık İçerik Planı",
                    "description": "İşletme için haftalık sosyal medya içerik takvimi oluşturma",
                    "examples": [
                        "Bu haftanın içerik planını oluştur",
                        "Haftalık Instagram takvimi hazırla",
                    ],
                },
                {
                    "id": "execute_plan",
                    "name": "Plana Göre Paylaşım",
                    "description": "Mevcut içerik planındaki bugünün gönderisini otomatik paylaşma",
                    "examples": [
                        "Plana göre bugünkü postu paylaş",
                        "İçerik planını uygula",
                    ],
                },
                {
                    "id": "instagram_analytics",
                    "name": "Instagram Analitik",
                    "description": "Haftalık metrik raporu ve performans analizi",
                    "examples": [
                        "Bu haftanın Instagram istatistiklerini analiz et",
                        "Performans raporu hazırla",
                    ],
                },
            ],
        },
        {
            "id": "analysis",
            "name": "Analiz & Araştırma",
            "icon": "📊",
            "features": [
                {
                    "id": "swot_analysis",
                    "name": "SWOT Analizi",
                    "description": "Güçlü/zayıf yönler, fırsatlar ve tehditler analizi",
                    "examples": [
                        "İşletmem için SWOT analizi yap",
                        "Rakiplere karşı stratejik analiz hazırla",
                    ],
                },
                {
                    "id": "seo_analysis",
                    "name": "SEO Analizi",
                    "description": "100 puanlık teknik SEO + GEO (AI arama motoru) analizi",
                    "details": "6 kategori: Teknik(25) + İçerik(25) + OnPage(20) + Mobil(15) + Şema(10) + Otorite(5)",
                    "examples": [
                        "Websitemizin SEO analizini yap",
                        "Rakip site ile SEO karşılaştırması",
                    ],
                },
                {
                    "id": "competitor_analysis",
                    "name": "Rakip Analizi",
                    "description": "Rakip websitelerini analiz etme ve karşılaştırma",
                    "examples": [
                        "En yakın 3 rakibimizi analiz et",
                        "Rakip sitelerin SEO güçlerini karşılaştır",
                    ],
                },
                {
                    "id": "serp_check",
                    "name": "SERP Sıralama Kontrolü",
                    "description": "Belirlenen anahtar kelimeler için Google sıralamalarını kontrol etme",
                    "examples": [
                        "Hangi anahtar kelimelerde üst sıradayız?",
                        "SEO anahtar kelime sıralamalarımızı göster",
                    ],
                },
                {
                    "id": "custom_report",
                    "name": "Özel Araştırma Raporu",
                    "description": "Herhangi bir konu hakkında web araştırması yapıp rapor hazırlama",
                    "examples": [
                        "2025 dijital pazarlama trendleri hakkında rapor yaz",
                        "Sektörümüzdeki son gelişmeleri araştır",
                    ],
                },
            ],
        },
        {
            "id": "storage",
            "name": "Dosya & Veri Yönetimi",
            "icon": "💾",
            "features": [
                {
                    "id": "file_management",
                    "name": "Dosya Yönetimi",
                    "description": "Firebase Storage'a dosya yükleme, listeleme, silme",
                    "examples": [
                        "Dosyalarımı listele",
                        "Bu videoyu sil",
                    ],
                },
                {
                    "id": "auto_save",
                    "name": "Otomatik Kayıt",
                    "description": "Üretilen tüm görseller, videolar ve raporlar Firebase'e otomatik kaydedilir",
                },
            ],
        },
    ],
}


__all__ = ["CAPABILITIES"]
