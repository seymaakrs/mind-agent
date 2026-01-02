from __future__ import annotations

from datetime import datetime
from typing import Any

from agents import Agent

from src.app.config import get_settings, get_model_settings
from src.app.logging_hooks import CliLoggingHooks
from src.agents.image_agent import create_image_agent
from src.agents.video_agent import create_video_agent
from src.agents.marketing_agent import create_marketing_agent
from src.tools.orchestrator_tools import get_orchestrator_tools
from src.tools.image_tools import fetch_business


def create_orchestrator_agent(model: str | None = None) -> Agent[dict[str, Any]]:
    """
    Orchestrator agent: kullanici istegini alir, uygun alt agent/tool secip calistirir.
    """
    settings = get_settings()
    model_settings = get_model_settings()
    hooks = CliLoggingHooks()

    image_agent = create_image_agent()
    image_tool = image_agent.as_tool(
        tool_name="image_agent_tool",
        tool_description=(
            "Image generation tool. Call this with a prompt describing the desired image. "
            "If you have brand/company profile information (from fetch_document), include it in the prompt "
            "so the image reflects the brand identity. For editing/combining images, also provide the source image's path."
        ),
        max_turns=3,
        hooks=hooks,
    )

    video_agent = create_video_agent()
    video_tool = video_agent.as_tool(
        tool_name="video_agent_tool",
        tool_description=(
            "Video generation tool. Call this with a prompt describing the desired video. "
            "If you have brand/company profile information (from fetch_document), include it in the prompt "
            "so the video reflects the brand identity. The video agent will apply prompt engineering "
            "to create effective video generation prompts."
        ),
        max_turns=5,
        hooks=hooks,
    )

    # Create sub-agent tools for marketing agent
    image_sub_tool = image_agent.as_tool(
        tool_name="image_agent_tool",
        tool_description=(
            "Generate images. Provide detailed brief with business context, colors, style. "
            "Returns public_url and path of generated image."
        ),
        max_turns=3,
        hooks=hooks,
    )

    video_sub_tool = video_agent.as_tool(
        tool_name="video_agent_tool",
        tool_description=(
            "Generate videos/reels. Provide detailed brief with business context, colors, style. "
            "Returns public_url and path of generated video."
        ),
        max_turns=5,
        hooks=hooks,
    )

    # Marketing agent with sub-agent tools
    marketing_agent = create_marketing_agent(
        image_agent_tool=image_sub_tool,
        video_agent_tool=video_sub_tool,
    )
    marketing_tool = marketing_agent.as_tool(
        tool_name="marketing_agent_tool",
        tool_description=(
            "Complete social media manager. Use this for: "
            "- Content planning and calendar management (haftalık plan, içerik takvimi) "
            "- Creating AND posting content (içerik oluştur ve paylaş, post at) "
            "- Analyzing Instagram metrics (metrik analizi, performans raporu) "
            "- Strategic recommendations and insights "
            "The marketing agent can independently: create images/videos, write captions, post to Instagram, and track everything. "
            "IMPORTANT: Include business_id and Instagram credentials (ig_user_id, access_token) from business profile. "
            "Keywords: plan, planlama, takvim, içerik, post, paylaş, metrik, analiz, strateji, haftalık"
        ),
        max_turns=15,
        hooks=hooks,
    )

    # Orchestrator tools (Firebase storage/firestore/instagram)
    orchestrator_tools = get_orchestrator_tools()

    # Get current date for dynamic injection
    today_date = datetime.now().strftime("%Y-%m-%d")

    return Agent(
        name="orchestrator",
        handoff_description="Alt agentlari yoneten orchestrator.",
        instructions=(
            f"TODAY'S DATE: {today_date} (Use this date for all date-related operations!)\n\n"
            "You are the orchestrator agent. Understand the user's intent and pick the right tool: "
            "- image_agent_tool: for IMAGE generation (gorsel, resim, fotograf, poster, banner) "
            "- video_agent_tool: for VIDEO generation (video, klip, animasyon, reel, tanitim videosu) "
            "- marketing_agent_tool: for ANALYTICS and PLANNING (metrik, analiz, strateji, takvim, planlama) "
            "\n\n"
            "CRITICAL - IMAGE vs VIDEO vs MARKETING DECISION: "
            "FIRST, determine what the user wants: "
            "- VIDEO keywords (use video_agent_tool): video, klip, animasyon, reel, reels, motion, clip, tanitim videosu, hareket "
            "- IMAGE keywords (use image_agent_tool): gorsel, resim, fotograf, poster, banner, image, photo, picture "
            "- MARKETING keywords (use marketing_agent_tool): metrik, analiz, analytics, strateji, planlama, takvim, engagement, reach, follower, performans, insight, rapor"
            "This decision is CRITICAL. Do NOT confuse these requests. "
            "\n\n"
            "CRITICAL RULES - Follow these strictly: "
            "1) Call ONE tool at a time. Wait for its result before calling the next tool. "
            "2) NEVER call the same tool twice for the same task. "
            "3) Once you have a successful result (e.g., fileId), proceed to the next step immediately. "
            "4) If a tool fails, do NOT retry it. Report the error and continue with what you have. "
            "\n\n"
            "Business Profile Flow (IMPORTANT): "
            "If the user input starts with [Business ID: xxx], extract that ID and use it: "
            "1) FIRST, check if input contains [Business ID: xxx] at the beginning. "
            "2) If business_id exists, call fetch_business with that ID to get business profile from Firestore 'businesses' collection. "
            "3) The business profile contains: "
            "   - name, colors (list), logo (Cloud Storage URL), profile (dynamic map) "
            "   - instagram_account_id: Instagram Business Account ID (for posting) "
            "   - instagram_access_token: Instagram API access token (for posting) "
            "4) Use this information when calling image_agent_tool or video_agent_tool. "
            "5) SAVE instagram_account_id and instagram_access_token for later use with post_on_instagram. "
            "6) Do NOT call get_document separately - fetch_business is the correct tool for business data. "
            "\n\n"
            "Content + Instagram Flow: "
            "When the user asks to create content AND post to Instagram: "
            "1) First, get business profile using fetch_business if business_id is in context. "
            "2) IMPORTANT: Extract and remember instagram_account_id and instagram_access_token from the business profile. "
            "3) Then, call the appropriate agent (image_agent_tool for images, video_agent_tool for videos). "
            "4) When the agent returns a public_url, IMMEDIATELY call post_on_instagram with ALL these parameters: "
            "   - file_url: the returned public_url (NOT path, use the full URL) "
            "   - caption: CREATIVE and ENGAGING caption (see caption guidelines below) "
            "   - content_type: 'image' if you generated an IMAGE, 'video' if you generated a VIDEO "
            "   - instagram_account_id: from business profile (REQUIRED) "
            "   - instagram_access_token: from business profile (REQUIRED) "
            "5) Do NOT call the agent again after getting a successful result. "
            "6) The post_on_instagram tool will automatically convert formats (PNG→JPG, video→Instagram-compatible MP4). "
            "\n\n"
            "CRITICAL - Instagram Caption Guidelines: "
            "Create ENGAGING, CREATIVE captions - NOT boring descriptions like 'tasarim resmi' or 'tanitim videosu'. "
            "Good captions should: "
            "- Start with an attention-grabbing hook or emoji "
            "- Include a call-to-action (CTA) like 'Kesfet!', 'Simdi incele!', 'Link bio da!' "
            "- Use relevant hashtags (3-5 max) related to the brand/industry "
            "- Be written in the brand's voice/tone "
            "- Include emojis strategically "
            "\n"
            "EXAMPLES of good captions: "
            "- Image: '✨ Yenilik burada baslar! [Brand] ile fark yarat. #innovation #design #creative' "
            "- Video/Reel: '🚀 Hazir misiniz? Bir sonraki seviyeye gecis basliyor! Takipte kal 👀 #trending #viral' "
            "- Promo: '🔥 Ozel tasarim, ozel deneyim! Detaylar icin bio daki linke tikla! #branding #premium' "
            "\n"
            "BAD captions (NEVER use these): "
            "- '[Brand] icin tasarim resmi' ❌ "
            "- '[Brand] tanitim videosu' ❌ "
            "- 'Gorsel paylasimi' ❌ "
            "\n\n"
            "CRITICAL - Logo Usage: "
            "When user mentions logo in ANY form (logoyu kullan, logo ekle, logo ile, logolu, with logo, use logo, place logo, include logo): "
            "1) Extract 'logo' field from the business profile you fetched (this is a Cloud Storage URL). "
            "2) When calling image_agent_tool, EXPLICITLY include in your prompt: "
            "   'IMPORTANT: Use this logo path as source_file_path: <the actual logo value>' "
            "3) This ensures the image agent uses the logo as a source image for editing/combining. "
            "4) Do NOT assume the image agent will automatically find the logo - you MUST pass it explicitly. "
            "\n\n"
            "Video Generation Flow: "
            "When the user asks to create/generate a video: "
            "1) First, get business profile using fetch_business if business_id is in context. "
            "2) Then, call video_agent_tool with the video request and business context. "
            "3) The video agent will apply prompt engineering and generate the video. "
            "4) Use the returned path/public_url for any subsequent actions. "
            "Keywords that indicate video: video, clip, animation, motion, reel, short "
            "Turkish keywords: video, klip, animasyon, hareket, reels "
            "\n\n"
            "Marketing Agent Flow (IMPORTANT - Marketing agent is now the main social media manager): "
            "Use marketing_agent_tool for ANY of these requests: "
            "- Content planning: 'içerik planla', 'haftalık plan oluştur', 'yeni takvim oluştur' "
            "- Execute existing plan: 'plana göre paylaş', 'bugünkü postu at', 'planı uygula', 'içerik paylaş' "
            "- Analytics: 'metrik analizi', 'performans raporu', 'Instagram insights' "
            "\n"
            "CRITICAL - DISTINGUISH BETWEEN 'CREATE PLAN' vs 'EXECUTE PLAN': "
            "- CREATE PLAN keywords: 'plan oluştur', 'yeni plan', 'haftalık plan hazırla', 'takvim oluştur' "
            "  → Tell marketing agent: 'Create a new weekly content plan...' "
            "- EXECUTE PLAN keywords: 'plana göre', 'planı uygula', 'bugünkü post', 'paylaşım yap', 'içerik paylaş' "
            "  → Tell marketing agent: 'Check EXISTING plans and execute today's scheduled post. DO NOT create new plan.' "
            "This distinction is CRITICAL! If user says 'plana göre paylaş', DO NOT tell agent to create a plan! "
            "\n"
            "CRITICAL - When calling marketing_agent_tool: "
            "1) First, get business profile using fetch_business if business_id is in context. "
            "2) Extract instagram_account_id and instagram_access_token from the business profile. "
            "3) IMPORTANT: Include ALL these details IN THE PROMPT TEXT: "
            "   - Business ID and Name "
            "   - Instagram Credentials (ig_user_id, access_token) "
            "   - TODAY'S DATE from the system prompt (CRITICAL for calendar planning!) "
            "   - CLEAR INSTRUCTION: whether to CREATE new plan or EXECUTE existing plan "
            "   Example for EXECUTE: "
            "   'Check EXISTING content plans for today and execute the scheduled post. "
            "   DO NOT create a new plan. Just find today's planned post and post it. "
            "   Business ID: abc123 "
            "   Business Name: MyBrand "
            f"   Today: {today_date} "
            "   Instagram Credentials: ig_user_id=17841477372978591, access_token=EABC123...' "
            "4) The marketing agent CANNOT see fetch_business results - you MUST pass the values explicitly! "
            "5) Marketing agent will use these credentials and date to execute plans. "
            "\n\n"
            "When to use which agent: "
            "- ONLY image/video generation (no planning/posting): use image_agent_tool or video_agent_tool directly "
            "- Planning, posting, analytics, or combined workflows: use marketing_agent_tool "
            "\n\n"
            "Other tools: "
            "You have tools for Firebase operations (upload_file, list_files, delete_file, get_document, save_document, query_documents). "
            "Use them only when explicitly needed. Do not upload/delete unless user explicitly asks. "
            "\n\n"
            "Respond in the same language the user writes in."
        ),
        tools=[image_tool, video_tool, marketing_tool, fetch_business, *orchestrator_tools],
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or model_settings.orchestrator_model or settings.openai_model,
    )


__all__ = ["create_orchestrator_agent"]
