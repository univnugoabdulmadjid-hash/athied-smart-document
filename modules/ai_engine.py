from google import genai
from google.genai import types

def get_genai_client(api_key):
    """
    Inisialisasi Client Google GenAI SDK
    """
    if not api_key:
        raise ValueError("API Key Google AI Studio belum terkonfigurasi.")
    return genai.Client(api_key=api_key)

def generate_section_content_with_pdf(api_key, system_instruction, user_prompt, pdf_bytes_list=None, model_name="gemini-3.1-pro-preview"):
    """
    Menghasilkan draf/analisis SOTA dari input teks dan berkas PDF.
    Terkunci temperature = 0.2 untuk presisi tinggi & pencegahan halusinasi.
    """
    try:
        client = get_genai_client(api_key)
        contents = []

        if pdf_bytes_list:
            for pdf_bytes in pdf_bytes_list:
                contents.append(types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"))

        contents.append(user_prompt)

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            top_p=0.95,
        )

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config
        )
        return response.text
    except Exception as e:
        return f"[ERROR AI ENGINE]: {str(e)}"

def generate_infographic_image(api_key, prompt_description, aspect_ratio="16:9"):
    """
    Menghasilkan gambar infografis/diagram visual menggunakan Nano Banana 2 Lite (gemini-3.1-flash-lite-image)
    """
    try:
        client = get_genai_client(api_key)
        response = client.models.generate_images(
            model='gemini-3.1-flash-lite-image',
            prompt=f"Professional legal infographic diagram, high quality, clean academic layout, 16:9 ratio: {prompt_description}",
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
            )
        )
        for generated_image in response.generated_images:
            return generated_image.image.image_bytes
    except Exception as e:
        print(f"[ERROR NANO BANANA]: {str(e)}")
        return None

def chat_interactive_agent(api_key, system_instruction, conversation_history, user_message, model_name="gemini-3.8-flash"):
    """
    Interaksi Chat Agent cepat untuk revisi draf bab pada panel sisi kanan.
    """
    try:
        client = get_genai_client(api_key)
        contents = []
        for msg in conversation_history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg["content"])]
            ))

        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)]
        ))

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
        )

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config
        )
        return response.text
    except Exception as e:
        return f"[ERROR CHAT AGENT]: {str(e)}"