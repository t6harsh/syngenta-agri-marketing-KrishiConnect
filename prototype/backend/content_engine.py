"""
Content Generation Engine
==========================
Generates hyper-personalized, context-aware marketing content using
real grower context. Uses Groq API (LLaMA) for generation, with fallback
to template-based generation when API is unavailable.

All context injected into prompts is REAL data from the datasets.
"""

import os
from typing import Dict, Any, Optional

from gtts import gTTS
import base64
import io
import json

# ──────────────────────────────────────────────────────
# Vernacular Templates (fallback when no API key)
# ──────────────────────────────────────────────────────
SEGMENT_TEMPLATES = {
    "Hindi": {
        "whatsapp": "🌾 नमस्ते {state} के किसान भाइयो! {crop} फसल अभी {stage} अवस्था में है। आपके क्षेत्र में {threat} का खतरा बढ़ रहा है। {product} का छिड़काव करें — आपके स्थानीय दुकानदार पर उपलब्ध है। 📞 अधिक जानकारी के लिए मिस्ड कॉल करें।",
        "sms": "{state} me {crop} kisanon! {threat} ka khatra. {product} spray kare. Apne kshetra ke dealer se sampark kare.",
        "voice_script": "नमस्कार किसान भाइयो, मैं सिंजेंटा की तरफ से बोल रहा हूँ। आपकी {crop} फसल में {threat} का खतरा है। {product} का उपयोग करें। अपने स्थानीय दुकानदार से संपर्क करें।",
    },
    "Punjabi": {
        "whatsapp": "🌾 ਸਤ ਸ੍ਰੀ ਅਕਾਲ {state} ਦੇ ਕਿਸਾਨ ਵੀਰੋ! ਤੁਹਾਡੀ {crop} ਫ਼ਸਲ {stage} ਅਵਸਥਾ ਵਿੱਚ ਹੈ। {threat} ਦਾ ਖ਼ਤਰਾ ਵੱਧ ਰਿਹਾ ਹੈ। {product} ਦੀ ਸਪਰੇ ਕਰੋ — ਸਥਾਨਕ ਡੀਲਰ ਤੋਂ ਲਵੋ।",
        "sms": "{state} de kisan veero! {crop} vich {threat} da khatra. {product} spray karo. sthani dealer to lo.",
        "voice_script": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਕਿਸਾਨ ਵੀਰੋ, ਮੈਂ ਸਿੰਜੈਂਟਾ ਵੱਲੋਂ ਬੋਲ ਰਿਹਾ ਹਾਂ। ਤੁਹਾਡੀ {crop} ਫ਼ਸਲ ਵਿੱਚ {threat} ਦਾ ਖ਼ਤਰਾ ਹੈ। {product} ਵਰਤੋ।",
    },
    "Marathi": {
        "whatsapp": "🌾 नमस्कार {state} मधील शेतकरी बंधूंनो! तुमच्या {crop} पिकावर सध्या {stage} अवस्था आहे। {threat} चा धोका वाढत आहे। {product} ची फवारणी करा — जवळच्या दुकानात उपलब्ध.",
        "sms": "{state} til shhetakari! {crop} var {threat} cha dhoka. {product} favarani kara. sthanik dealer la bheta.",
        "voice_script": "नमस्कार शेतकरी बंधूंनो, मी सिंजेंटा कडून बोलत आहे. तुमच्या {crop} पिकावर {threat} चा धोका आहे. {product} वापरा.",
    },
    "Gujarati": {
        "whatsapp": "🌾 નમસ્તે {state} ના ખેડૂત ભાઈઓ! તમારો {crop} પાક {stage} અવસ્થામાં છે. {threat} નો ખતરો વધી રહ્યો છે. {product} નો છંટકાવ કરો — સ્થાનિક ડીલર પાસેથી મળશે.",
        "sms": "{state} na kheduto! {crop} ma {threat} no khataro. {product} spray karo. sthanik dealer ne mlo.",
        "voice_script": "નમસ્કાર ખેડૂત ભાઈઓ, હું સિન્જેન્ટા તરફથી બોલું છું. તમારા {crop} પાકમાં {threat} નો ખતરો છે. {product} વાપરો.",
    },
    "Kannada": {
        "whatsapp": "🌾 ನಮಸ್ಕಾರ {state} ನ ರೈತ ಬಂಧುಗಳಿರಾ! ನಿಮ್ಮ {crop} ಬೆಳೆ {stage} ಹಂತದಲ್ಲಿದೆ. {threat} ಅಪಾಯ ಹೆಚ್ಚಾಗಿದೆ. {product} ಸಿಂಪಡಿಸಿ — ಸ್ಥಳೀಯ ಡೀಲರ್ ಬಳಿ ಲಭ್ಯ.",
        "sms": "{state} raita bandhugale! {crop} bele {threat} apaya. {product} simpadisi. sthanika dealer hattira.",
        "voice_script": "ನಮಸ್ಕಾರ ರೈತ ಬಂಧುಗಳಿರಾ, ನಾನು ಸಿಂಜೆಂಟಾ ಇಂದ ಮಾತನಾಡುತ್ತಿದ್ದೇನೆ. ನಿಮ್ಮ {crop} ಬೆಳೆಯಲ್ಲಿ {threat} ಅಪಾಯವಿದೆ. {product} ಬಳಸಿ.",
    },
    "Bengali": {
        "whatsapp": "🌾 নমস্কার {state} এর কৃষক ভাইয়েরা! আপনার {crop} ফসল {stage} পর্যায়ে আছে। {threat} এর ঝুঁকি বাড়ছে। {product} স্প্রে করুন — স্থানীয় ডিলারের কাছে পাওয়া যাবে।",
        "sms": "{state} er krishak! {crop} te {threat} er jhuki. {product} spray korun. sthanik dealer e jan.",
        "voice_script": "নমস্কার কৃষক ভাইয়েরা, আমি সিনজেন্টা থেকে বলছি। আপনার {crop} ফসলে {threat} এর ঝুঁকি আছে। {product} ব্যবহার করুন।",
    },
}

TEMPLATES = {
    "Hindi": {
        "whatsapp": "🌾 नमस्ते किसान भाई! आपकी {crop} फसल अभी {stage} अवस्था में है। {threat} का खतरा बढ़ रहा है। {product} का छिड़काव करें — आपके नज़दीकी {district} के दुकानदार पर उपलब्ध है। 📞 अधिक जानकारी के लिए मिस्ड कॉल करें।",
        "sms": "{crop} me {threat} ka khatra! {product} spray kare. Apne {district} dealer se sampark kare.",
        "voice_script": "नमस्कार किसान भाई, मैं सिंजेंटा की तरफ से बोल रहा हूँ। आपकी {crop} फसल में {threat} का खतरा है। {product} का उपयोग करें। अपने नज़दीकी दुकानदार से संपर्क करें।",
    },
    "Punjabi": {
        "whatsapp": "🌾 ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਕਿਸਾਨ ਵੀਰ! ਤੁਹਾਡੀ {crop} ਫ਼ਸਲ {stage} ਅਵਸਥਾ ਵਿੱਚ ਹੈ। {threat} ਦਾ ਖ਼ਤਰਾ ਵੱਧ ਰਿਹਾ ਹੈ। {product} ਦੀ ਸਪਰੇ ਕਰੋ — {district} ਦੇ ਡੀਲਰ ਤੋਂ ਲਵੋ।",
        "sms": "{crop} vich {threat} da khatra! {product} spray karo. {district} dealer to lo.",
        "voice_script": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਕਿਸਾਨ ਵੀਰ, ਮੈਂ ਸਿੰਜੈਂਟਾ ਵੱਲੋਂ ਬੋਲ ਰਿਹਾ ਹਾਂ। ਤੁਹਾਡੀ {crop} ਫ਼ਸਲ ਵਿੱਚ {threat} ਦਾ ਖ਼ਤਰਾ ਹੈ। {product} ਵਰਤੋ।",
    },
    "Marathi": {
        "whatsapp": "🌾 नमस्कार शेतकरी बंधू! तुमच्या {crop} पिकावर सध्या {stage} अवस्था आहे। {threat} चा धोका वाढत आहे। {product} ची फवारणी करा — {district} मधील तुमच्या जवळच्या दुकानात उपलब्ध.",
        "sms": "{crop} var {threat} cha dhoka! {product} favarani kara. {district} dealer la bhetaa.",
        "voice_script": "नमस्कार शेतकरी बंधू, मी सिंजेंटा कडून बोलतो आहे. तुमच्या {crop} पिकावर {threat} चा धोका आहे. {product} वापरा.",
    },
    "Gujarati": {
        "whatsapp": "🌾 નમસ્તે ખેડૂત ભાઈ! તમારો {crop} પાક {stage} અવસ્થામાં છે. {threat} નો ખતરો વધી રહ્યો છે. {product} નો છંટકાવ કરો — {district} ના ડીલર પાસેથી મળશે.",
        "sms": "{crop} ma {threat} no khataro! {product} spray karo. {district} dealer ne mlo.",
        "voice_script": "નમસ્કાર ખેડૂત ભાઈ, હું સિન્જેન્ટા તરફથી બોલું છું. તમારા {crop} પાકમાં {threat} નો ખતરો છે. {product} વાપરો.",
    },
    "Kannada": {
        "whatsapp": "🌾 ನಮಸ್ಕಾರ ರೈತ ಬಂಧು! ನಿಮ್ಮ {crop} ಬೆಳೆ {stage} ಹಂತದಲ್ಲಿದೆ. {threat} ಅಪಾಯ ಹೆಚ್ಚಾಗಿದೆ. {product} ಸಿಂಪಡಿಸಿ — {district} ನ ಡೀಲರ್ ಹತ್ತಿರ ಲಭ್ಯ.",
        "sms": "{crop} bele {threat} apaya! {product} simpadisi. {district} dealer hattira.",
        "voice_script": "ನಮಸ್ಕಾರ ರೈತ ಬಂಧು, ನಾನು ಸಿಂಜೆಂಟಾ ಇಂದ ಮಾತನಾಡುತ್ತಿದ್ದೇನೆ. ನಿಮ್ಮ {crop} ಬೆಳೆಯಲ್ಲಿ {threat} ಅಪಾಯವಿದೆ. {product} ಬಳಸಿ.",
    },
    "Bengali": {
        "whatsapp": "🌾 নমস্কার কৃষক ভাই! আপনার {crop} ফসল {stage} পর্যায়ে আছে। {threat} এর ঝুঁকি বাড়ছে। {product} স্প্রে করুন — {district} এর ডিলারের কাছে পাওয়া যাবে।",
        "sms": "{crop} te {threat} er jhuki! {product} spray korun. {district} dealer e jan.",
        "voice_script": "নমস্কার কৃষক ভাই, আমি সিনজেন্টা থেকে বলছি। আপনার {crop} ফসলে {threat} এর ঝুঁকি আছে। {product} ব্যবহার করুন।",
    },
}


SYSTEM_PROMPT = """You are an agricultural marketing content specialist for Syngenta India.
You create hyper-personalized, culturally sensitive marketing messages for Indian farmers.

Rules:
1. Always use the EXACT product name provided — never invent product names.
2. Keep WhatsApp messages under 300 characters.
3. Keep SMS under 160 characters (transliterated Roman script).
4. Voice scripts should be conversational, 30-second read time.
5. Use respectful farmer-addressing conventions for the language.
6. Include a clear call-to-action (visit dealer, call number, scan product).
7. Never make unsubstantiated yield claims.
8. Mention the specific crop stage and threat to establish credibility.
"""


import os
from typing import Dict, Any, Optional

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


class ContentEngine:
    """Generates personalized marketing content from real grower context."""

    def __init__(self, groq_api_key: str = None):
        self.api_key = groq_api_key or os.environ.get("GROQ_API_KEY", "")
        self.groq_client = None

        if self.api_key and GROQ_AVAILABLE:
            try:
                self.groq_client = Groq(api_key=self.api_key)
                print("[ContentEngine] Groq API configured successfully.")
            except Exception as e:
                print(
                    f"[ContentEngine] Groq init failed: {e}. Falling back to templates."
                )
                self.groq_client = None
        else:
            print("[ContentEngine] No Groq API key. Using template-based generation.")

    def generate(
        self,
        grower_context: Dict[str, Any],
        format_type: str = "auto",
        weather_triggers: list = None,
    ) -> Dict[str, Any]:
        """
        Generate marketing content for a grower.

        Args:
            grower_context: Output from SegmentationEngine.get_grower_context()
            format_type: 'whatsapp', 'sms', 'voice_script', or 'auto'
            weather_triggers: Optional list of active disease triggers from WeatherTriggerEngine

        Returns:
            Dict with generated content for each format + visual + video.
        """
        # Determine format
        if format_type == "auto":
            channel = grower_context.get("recommended_channel", "sms")
            format_type = {
                "whatsapp": "whatsapp",
                "sms": "sms",
                "voice_call": "voice_script",
            }.get(channel, "sms")

        # Pick best available product (in stock preferred)
        products = grower_context.get("recommended_products", [])
        best_product = "Syngenta product"
        for p in products:
            if isinstance(p, dict) and p.get("in_stock", False):
                best_product = p["product"]
                break
        if best_product == "Syngenta product" and products:
            best_product = (
                products[0]["product"]
                if isinstance(products[0], dict)
                else str(products[0])
            )

        # Use weather trigger if available for more specific threat
        threat = grower_context.get("threat", "pest/disease")
        if weather_triggers:
            # Pick highest severity trigger
            severity_order = {"critical": 0, "high": 1, "medium": 2}
            sorted_triggers = sorted(
                weather_triggers,
                key=lambda t: severity_order.get(t.get("severity", "medium"), 3),
            )
            if sorted_triggers:
                threat = sorted_triggers[0]["disease"]
                best_product = sorted_triggers[0].get(
                    "recommended_product", best_product
                )

        context_vars = {
            "crop": grower_context.get("crop", "crop"),
            "stage": grower_context.get("current_stage", "growth"),
            "threat": threat,
            "product": best_product,
            "district": grower_context.get("district", ""),
            "state": grower_context.get("state", ""),
            "language": grower_context.get("language", "Hindi"),
            "farm_size": grower_context.get("farm_size_acres", 0),
        }

        result = {
            "grower_id": grower_context.get("grower_id", ""),
            "language": context_vars["language"],
            "channel": grower_context.get("recommended_channel", "sms"),
            "product_recommended": best_product,
            "generation_method": "template",
            "weather_triggers": weather_triggers or [],
        }

        # Generate content for requested format(s)
        formats_to_gen = ["whatsapp", "sms", "voice_script"] if format_type == "all" else [format_type]
        content = {}
        for fmt in formats_to_gen:
            if self.groq_client:
                try:
                    part = self._generate_with_groq(context_vars, fmt)
                    result["generation_method"] = "groq"
                except Exception as e:
                    print(f"[ContentEngine] Groq {fmt} failed: {e}. Falling back.")
                    part = self._generate_from_template(context_vars, fmt)
            else:
                part = self._generate_from_template(context_vars, fmt)
            content.update(part)
        result["content"] = content

        # HACKATHON DAY PATCH: Inject a dynamic placeholder image URL based on crop/threat
        threat_lower = context_vars["threat"].lower()
        if "blight" in threat_lower or "rust" in threat_lower or "wilt" in threat_lower:
            demo_image = "https://images.unsplash.com/photo-1592843997784-07e33dc3a105?q=80&w=400&auto=format&fit=crop"
        else:
            demo_image = "https://images.unsplash.com/photo-1625246333195-78d9c38ad449?q=80&w=400&auto=format&fit=crop"
        result["content"]["generated_image_url"] = demo_image

        # ── Run Content Guardrails ──
        from backend.orchestrator import CampaignOrchestrator

        orch = CampaignOrchestrator()
        result["guardrail_check"] = orch.validate_content(
            result["content"], best_product
        )

        # ── Add Audio Synthesis ──
        voice_script = result.get("content", {}).get("voice_script", "")
        if not voice_script and "voice_call script" in result.get("content", {}):
            voice_script = result["content"]["voice_call script"]

        if voice_script:
            print("[ContentEngine] Synthesizing audio...")
            result["content"]["voice_audio_base64"] = self._generate_audio(
                voice_script,
                context_vars["language"]
            )

        return result
    
        

    def _generate_with_groq(self, ctx: Dict, format_type: str) -> Dict[str, str]:
        """Generate content using Groq API."""
        user_prompt = f"""Generate a {format_type} marketing message with these EXACT parameters:
- Crop: {ctx['crop']}
- Current Stage: {ctx['stage']}
- Active Threat: {ctx['threat']}
- Product to Promote: {ctx['product']}
- Target Language: {ctx['language']}
- Region: {ctx['district']}, {ctx['state']}
- Farm Size: {ctx['farm_size']} acres

Generate the message in {ctx['language']} language.
Also provide an English translation.
Format your response as:
ORIGINAL: <message in target language>
ENGLISH: <english translation>
"""
        response = self.groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = response.choices[0].message.content.strip()

        # Parse response
        original = text
        english = ""
        if "ORIGINAL:" in text and "ENGLISH:" in text:
            parts = text.split("ENGLISH:")
            original = parts[0].replace("ORIGINAL:", "").strip()
            english = parts[1].strip()

        return {
            format_type: original,
            "english_translation": english,
        }

    def _generate_from_template(self, ctx: Dict, format_type: str) -> Dict[str, str]:
        """Generate content using pre-built vernacular templates."""
        lang = ctx["language"]
        templates = TEMPLATES.get(lang, TEMPLATES["Hindi"])
        if format_type == "all":
            result = {}
            for fmt in ["whatsapp", "sms", "voice_script"]:
                t = templates.get(fmt, "")
                result[fmt] = t.format(**ctx) if t else ""
            return result
        template = templates.get(format_type, "")
        return {format_type: template.format(**ctx) if template else ""}

    def _generate_visual_with_groq(self, ctx: Dict) -> str:
        """Generate visual concept prompt using Groq API."""
        prompt = f"""Create a detailed image prompt for an agricultural marketing infographic with these parameters:
- Crop: {ctx['crop']}
- Stage: {ctx['stage']}
- Threat: {ctx['threat']}
- Product: {ctx['product']}
- Language: {ctx['language']}
- Region: {ctx.get('district', '')}, {ctx.get('state', '')}

Requirements:
- Professional clean design, Syngenta green brand colors
- Split layout showing threat damage on left, healthy crop after treatment on right
- Product packaging prominently displayed in center
- Text overlay in {ctx['language']} language with product name and call-to-action
- Photorealistic crop imagery with flat-design infographic elements
- High contrast for mobile viewing, 1:1 square aspect ratio
- Suitable for feeding to DALL-E, Stable Diffusion, or Imagen

Return ONLY the image prompt text, no other commentary."""
        response = self.groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    def _generate_video_with_groq(self, ctx: Dict) -> list:
        """Generate video storyboard using Groq API."""
        prompt = f"""Generate a 30-second video storyboard as a JSON array for an agricultural marketing video with these parameters:
- Crop: {ctx['crop']}
- Stage: {ctx['stage']}
- Threat: {ctx['threat']}
- Product: {ctx['product']}
- Language: {ctx['language']}
- Region: {ctx.get('district', '')}, {ctx.get('state', '')}

Each scene must have these keys: "scene" (number), "duration_sec" (number), "visual" (string), "narration_lang" (string in {ctx['language']}), "narration_en" (string), "text_overlay" (string).

Create 5 scenes:
1. Wide shot establishing the region and crop, showing the threat
2. Close-up of threat symptoms with warning overlay
3. Product demonstration and application
4. Before/after comparison showing treatment results
5. Branding with call-to-action and dealer information

Return ONLY valid JSON, no other text."""
        response = self.groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)

    def _generate_visual_prompt(self, ctx: Dict) -> str:
        """Generate a visual concept prompt — Groq first, template fallback."""
        if self.groq_client:
            try:
                return self._generate_visual_with_groq(ctx)
            except Exception as e:
                print(f"[ContentEngine] Groq visual prompt failed: {e}. Falling back.")
        return self._generate_visual_prompt_template(ctx)

    def _generate_video_storyboard(self, ctx: Dict) -> list:
        """Generate a video storyboard — Groq first, template fallback."""
        if self.groq_client:
            try:
                return self._generate_video_with_groq(ctx)
            except Exception as e:
                print(f"[ContentEngine] Groq video storyboard failed: {e}. Falling back.")
        return self._generate_video_storyboard_template(ctx)

    def _generate_visual_prompt_template(self, ctx: Dict) -> str:
        lang_script = {
            "Hindi": "Devanagari script",
            "Punjabi": "Gurmukhi script",
            "Marathi": "Devanagari script",
            "Gujarati": "Gujarati script",
            "Kannada": "Kannada script",
            "Bengali": "Bengali script",
        }
        script = lang_script.get(ctx["language"], "Devanagari script")

        return (
            f"Agricultural marketing infographic, professional clean design, Syngenta green brand colors. "
            f"Split layout: LEFT SIDE shows a close-up photograph of {ctx['threat']} damage on "
            f"{ctx['crop']} leaves during {ctx['stage']} stage — wilting, discoloration, spots visible. "
            f"RIGHT SIDE shows a healthy, vibrant {ctx['crop']} field after treatment, lush green. "
            f"CENTER: Product packaging of '{ctx['product']}' prominently displayed with Syngenta logo. "
            f"BOTTOM BANNER: Text overlay in {script} ({ctx['language']} language) reading the product name "
            f"'{ctx['product']}' and a call-to-action 'Ask your local dealer'. "
            f"Region context: {ctx['district']}, {ctx['state']}. "
            f"Style: photorealistic crop imagery, flat-design infographic elements, high contrast for "
            f"mobile viewing. Aspect ratio: 1:1 square for WhatsApp status / social media."
        )

    def _generate_video_storyboard_template(self, ctx: Dict) -> list:
        return [
            {
                "scene": 1,
                "duration_sec": 5,
                "visual": f"Wide shot of a {ctx['crop']} field in {ctx['district']}, {ctx['state']}. "
                f"Camera slowly zooms in to show early signs of {ctx['threat']}.",
                "narration_lang": ctx["language"],
                "narration_en": f"Attention {ctx['crop']} farmers of {ctx['district']}! "
                f"Your crop is in the {ctx['stage']} stage.",
                "text_overlay": f"⚠️ {ctx['threat']}",
            },
            {
                "scene": 2,
                "duration_sec": 8,
                "visual": f"Close-up of {ctx['threat']} symptoms on {ctx['crop']} — "
                f"damaged leaves, discoloration, pest activity. "
                f"Red warning graphics overlay.",
                "narration_lang": ctx["language"],
                "narration_en": f"{ctx['threat']} is spreading in your area. "
                f"If untreated, it can reduce your yield significantly.",
                "text_overlay": f"Yield at risk!",
            },
            {
                "scene": 3,
                "duration_sec": 7,
                "visual": f"Product shot: {ctx['product']} packaging held by a farmer's hands. "
                f"Syngenta logo visible. Cut to sprayer applying the product on the field.",
                "narration_lang": ctx["language"],
                "narration_en": f"Use {ctx['product']} from Syngenta. "
                f"Proven protection for your {ctx['crop']} crop.",
                "text_overlay": f"✅ {ctx['product']}",
            },
            {
                "scene": 4,
                "duration_sec": 5,
                "visual": f"Before/after split screen: LEFT damaged {ctx['crop']}, "
                f"RIGHT healthy treated {ctx['crop']}. Bright, positive imagery.",
                "narration_lang": ctx["language"],
                "narration_en": f"Protect your crop. Protect your income.",
                "text_overlay": f"Healthy crop = Better harvest",
            },
            {
                "scene": 5,
                "duration_sec": 5,
                "visual": f"Syngenta branding screen with dealer locator QR code. "
                f"Text in {ctx['language']}: 'Available at your nearest dealer'.",
                "narration_lang": ctx["language"],
                "narration_en": f"Visit your nearest dealer in {ctx['district']} today. "
                f"Or give a missed call to know more.",
                "text_overlay": f"📞 Missed call: 1800-XXX-XXXX",
            },
        ]

    def generate_batch(self, grower_contexts: list, format_type: str = "auto") -> list:
        """Generate content for a batch of growers."""
        results = []
        for ctx in grower_contexts:
            content = self.generate(ctx, format_type)
            results.append(content)
        return results

    def generate_for_segment(
        self,
        segment_context: Dict[str, Any],
        format_type: str = "auto",
        weather_triggers: list = None,
    ) -> Dict[str, Any]:
        """
        Generate marketing content targeting an entire segment of farmers.

        Args:
            segment_context: Output from SegmentationEngine.get_segment_context()
            format_type: 'whatsapp', 'sms', 'voice_script', or 'auto'
            weather_triggers: Optional list of active disease triggers

        Returns:
            Dict with generated content, reach stats, and delivery plan.
        """
        if format_type == "auto":
            channel = segment_context.get("recommended_channel", "sms")
            format_type = {
                "whatsapp": "whatsapp",
                "sms": "sms",
                "voice_call": "voice_script",
            }.get(channel, "sms")

        best_product = segment_context.get("product_recommended", "Syngenta product")
        threat = segment_context.get("threat", "pest/disease")

        if weather_triggers:
            severity_order = {"critical": 0, "high": 1, "medium": 2}
            sorted_triggers = sorted(
                weather_triggers,
                key=lambda t: severity_order.get(t.get("severity", "medium"), 3),
            )
            if sorted_triggers:
                threat = sorted_triggers[0]["disease"]
                best_product = sorted_triggers[0].get(
                    "recommended_product", best_product
                )

        context_vars = {
            "crop": segment_context.get("crop", "crop"),
            "stage": segment_context.get("current_stage", "growth"),
            "threat": threat,
            "product": best_product,
            "district": segment_context.get("tehsils", [""])[0] if segment_context.get("tehsils") else "",
            "state": segment_context.get("state", ""),
            "language": segment_context.get("language", "Hindi"),
            "farm_size": segment_context.get("avg_farm_size_acres", 0),
            "grower_count": segment_context.get("grower_count", 0),
        }

        grower_count = segment_context.get("grower_count", 0)
        result = {
            "segment_id": segment_context.get("segment_id", ""),
            "language": context_vars["language"],
            "channel": segment_context.get("recommended_channel", "sms"),
            "product_recommended": best_product,
            "reach": grower_count,
            "generation_method": "template",
            "weather_triggers": weather_triggers or [],
        }

        formats_to_gen = ["whatsapp", "sms", "voice_script"] if format_type == "all" else [format_type]
        content = {}
        for fmt in formats_to_gen:
            if self.groq_client:
                try:
                    part = self._generate_segment_with_groq(context_vars, fmt)
                    result["generation_method"] = "groq"
                except Exception as e:
                    print(f"[ContentEngine] Groq segment {fmt} failed: {e}. Falling back.")
                    part = self._generate_from_segment_template(context_vars, fmt)
            else:
                part = self._generate_from_segment_template(context_vars, fmt)
            content.update(part)
        result["content"] = content

        threat_lower = context_vars["threat"].lower()
        if "blight" in threat_lower or "rust" in threat_lower or "wilt" in threat_lower:
            demo_image = "https://images.unsplash.com/photo-1592843997784-07e33dc3a105?q=80&w=400&auto=format&fit=crop"
        else:
            demo_image = "https://images.unsplash.com/photo-1625246333195-78d9c38ad449?q=80&w=400&auto=format&fit=crop"
        result["content"]["generated_image_url"] = demo_image

        from backend.orchestrator import CampaignOrchestrator
        orch = CampaignOrchestrator()
        result["guardrail_check"] = orch.validate_content(
            result["content"], best_product
        )

        voice_script = result.get("content", {}).get("voice_script", "")
        if not voice_script and "voice_call script" in result.get("content", {}):
            voice_script = result["content"]["voice_call script"]

        if voice_script:
            print("[ContentEngine] Synthesizing audio for segment...")
            result["content"]["voice_audio_base64"] = self._generate_audio(
                voice_script,
                context_vars["language"]
            )

        return result

    def _generate_segment_with_groq(self, ctx: Dict, format_type: str) -> Dict[str, str]:
        """Generate segment-targeted content using Groq API."""
        user_prompt = f"""Generate a GROUP {format_type} marketing message targeting multiple farmers with these EXACT parameters:
- Crop: {ctx['crop']}
- Current Stage: {ctx['stage']}
- Active Threat: {ctx['threat']}
- Product to Promote: {ctx['product']}
- Target Language: {ctx['language']}
- Region: {ctx['state']}
- Estimated Farmers Reached: {ctx.get('grower_count', 0)}

The message should address farmers as a group (plural/collective form).
Generate the message in {ctx['language']} language.
Also provide an English translation.
Format your response as:
ORIGINAL: <message in target language>
ENGLISH: <english translation>
"""
        response = self.groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = response.choices[0].message.content.strip()

        original = text
        english = ""
        if "ORIGINAL:" in text and "ENGLISH:" in text:
            parts = text.split("ENGLISH:")
            original = parts[0].replace("ORIGINAL:", "").strip()
            english = parts[1].strip()

        return {
            format_type: original,
            "english_translation": english,
        }

    def _generate_from_segment_template(self, ctx: Dict, format_type: str) -> Dict[str, str]:
        """Generate segment-targeted content using pre-built vernacular templates."""
        lang = ctx["language"]
        templates = SEGMENT_TEMPLATES.get(lang, SEGMENT_TEMPLATES["Hindi"])
        if format_type == "all":
            result = {}
            for fmt in ["whatsapp", "sms", "voice_script"]:
                t = templates.get(fmt, "")
                result[fmt] = t.format(**ctx) if t else ""
            return result
        template = templates.get(format_type, "")
        return {format_type: template.format(**ctx) if template else ""}

    def _generate_segment_visual_prompt(self, ctx: Dict) -> str:
        """Generate segment visual concept prompt — Groq first, template fallback."""
        if self.groq_client:
            try:
                return self._generate_visual_with_groq(ctx)
            except Exception as e:
                print(f"[ContentEngine] Groq segment visual prompt failed: {e}. Falling back.")
        return self._generate_segment_visual_prompt_template(ctx)

    def _generate_segment_video_storyboard(self, ctx: Dict) -> list:
        """Generate segment video storyboard — Groq first, template fallback."""
        if self.groq_client:
            try:
                return self._generate_video_with_groq(ctx)
            except Exception as e:
                print(f"[ContentEngine] Groq segment video storyboard failed: {e}. Falling back.")
        return self._generate_segment_video_storyboard_template(ctx)

    def _generate_segment_visual_prompt_template(self, ctx: Dict) -> str:
        lang_script = {
            "Hindi": "Devanagari script",
            "Punjabi": "Gurmukhi script",
            "Marathi": "Devanagari script",
            "Gujarati": "Gujarati script",
            "Kannada": "Kannada script",
            "Bengali": "Bengali script",
        }
        script = lang_script.get(ctx["language"], "Devanagari script")

        return (
            f"Agricultural marketing infographic targeting farmer community in {ctx['state']}. "
            f"Professional clean design, Syngenta green brand colors. "
            f"Split layout: LEFT SIDE shows a group of farmers examining {ctx['threat']} damage on "
            f"{ctx['crop']} during {ctx['stage']} stage. "
            f"RIGHT SIDE shows a thriving {ctx['crop']} field after community-wide treatment. "
            f"CENTER: Product packaging of '{ctx['product']}' prominently displayed with Syngenta logo. "
            f"BOTTOM BANNER: Text overlay in {script} ({ctx['language']} language) reading "
            f"'{ctx['product']}' and 'Ask your local dealer'. "
            f"Region context: {ctx['state']}. Style: photorealistic crop imagery, flat-design infographic "
            f"elements, high contrast for mobile viewing. Aspect ratio: 1:1 square."
        )

    def _generate_segment_video_storyboard_template(self, ctx: Dict) -> list:
        return [
            {
                "scene": 1,
                "duration_sec": 5,
                "visual": f"Panoramic wide shot of {ctx['crop']} fields across {ctx['state']}, "
                f"with multiple farmers working. Text: '{ctx['grower_count']} farmers affected.'",
                "narration_lang": ctx["language"],
                "narration_en": f"Attention {ctx['crop']} farmers in {ctx['state']}! "
                f"Your crop is in the {ctx['stage']} stage and facing threats.",
                "text_overlay": f"⚠️ {ctx['threat']} alert for {ctx['state']}",
            },
            {
                "scene": 2,
                "duration_sec": 8,
                "visual": f"Split screen showing {ctx['threat']} symptoms across multiple "
                f"fields in the region. Community concern imagery.",
                "narration_lang": ctx["language"],
                "narration_en": f"{ctx['threat']} is spreading across {ctx['state']}. "
                f"Act now to protect your yield.",
                "text_overlay": f"Protect your community's crop!",
            },
            {
                "scene": 3,
                "duration_sec": 7,
                "visual": f"Product shot: {ctx['product']} packaging in a farmer's hands. "
                f"Group of farmers applying the product. Syngenta logo visible.",
                "narration_lang": ctx["language"],
                "narration_en": f"Use {ctx['product']} from Syngenta — "
                f"the trusted choice of {ctx['state']} farmers.",
                "text_overlay": f"✅ {ctx['product']}",
            },
            {
                "scene": 4,
                "duration_sec": 5,
                "visual": f"Before/after: Left = damaged {ctx['crop']} fields across the district, "
                f"Right = vibrant green fields after community-wide treatment.",
                "narration_lang": ctx["language"],
                "narration_en": f"Protect your crop. Protect your community's income.",
                "text_overlay": f"Stronger together",
            },
            {
                "scene": 5,
                "duration_sec": 5,
                "visual": f"Syngenta branding with dealer locator map of {ctx['state']}. "
                f"Text in {ctx['language']}: 'Available at dealers near you'.",
                "narration_lang": ctx["language"],
                "narration_en": f"Visit your nearest dealer today. Or give a missed call.",
                "text_overlay": f"📞 Missed call: 1800-XXX-XXXX",
            },
        ]

    def _generate_audio(self, text: str, language: str) -> str:
        """Generate audio and return as base64 string for direct frontend playback."""
        # Map your database languages to standard ISO language codes
        lang_map = {
            "hindi": "hi",
            "gujarati": "gu",
            "marathi": "mr",
            "punjabi": "pa",
            "tamil": "ta",
            "telugu": "te",
            "english": "en"
        }
        lang_code = lang_map.get(language.lower(), "hi") # Default to Hindi
        
        try:
            tts = gTTS(text=text, lang=lang_code, slow=False)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            audio_b64 = base64.b64encode(fp.read()).decode("utf-8")
            return f"data:audio/mp3;base64,{audio_b64}"
        except Exception as e:
            print(f"[ContentEngine] Audio generation failed: {e}")
            return ""
