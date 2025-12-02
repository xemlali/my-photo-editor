import streamlit as st
from newspaper import Article
import requests
import base64
import google.generativeai as genai
from PIL import Image, ImageEnhance
import io
import numpy as np

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="المحرر الذكي 2.0", layout="wide", page_icon="🗞️")

# --- 2. القائمة الجانبية (للبيانات السرية فقط) ---
with st.sidebar:
    st.header("🔐 بيانات الاتصال")
    st.info("أدخل هذه البيانات مرة واحدة ليعمل التطبيق")
    
    wp_url = st.text_input("رابط الموقع", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم (WordPress)")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")
    
    st.divider()
    api_key = st.text_input("مفتاح Gemini API", type="password")

# --- 3. الواجهة الرئيسية (مكان وضع الرابط) ---
st.title("🚀 المحرر الصحفي الشامل (Gemini 2.0)")
st.markdown("---")

# >>>>> هنا خانة الرابط (في الوجه مباشرة) <<<<<
col1, col2 = st.columns([3, 1])
with col1:
    url_input = st.text_input("🔗 ضع رابط الخبر الأصلي هنا:", placeholder="https://www.example.com/news...")
with col2:
    st.write("") # مسافة جمالية
    st.write("") 
    start_btn = st.button("✨ ابدأ المعالجة", use_container_width=True, type="primary")

# --- 4. الدوال البرمجية (المحرك) ---

def create_vignette(image):
    if image.mode != 'RGB':
        image = image.convert('RGB')
    width, height = image.size
    x = np.linspace(-1, 1, width)
    y = np.linspace(-1, 1, height)
    X, Y = np.meshgrid(x, y)
    radius = np.sqrt(X**2 + Y**2)
    radius = radius / np.max(radius)
    alpha = 1 - radius
    alpha = np.power(alpha, 1.5)
    vignette_mask = Image.fromarray((alpha * 255).astype('uint8'), mode='L')
    black_layer = Image.new('RGB', (width, height), 'black')
    return Image.composite(image, black_layer, vignette_mask)

def process_image_for_news(image_url):
    try:
        response = requests.get(image_url, stream=True)
        img = Image.open(response.raw)
        
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # تحسينات الصورة
        img = ImageEnhance.Color(img).enhance(1.4)      # ألوان مشبعة
        img = ImageEnhance.Contrast(img).enhance(1.2)   # تباين
        img = ImageEnhance.Sharpness(img).enhance(1.3)  # حدة
        img = create_vignette(img)                      # فينييت
        
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        return buf.getvalue()
    except Exception as e:
        return None

def rewrite_article_ai(original_text, api_key):
    try:
        genai.configure(api_key=api_key)
        # استخدام الموديل القوي المتوفر لديك
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        أنت صحفي خبير (Senior Editor). قم بإعادة صياغة الخبر التالي بأسلوب مهني ومشوق.
        
        القواعد الصارمة:
        1. اكتب عنواناً واحداً فقط في السطر الأول (جذاب، ذكي، ويراعي SEO).
        2. اكتب المتن بأسلوب قصصي مترابط (Storytelling) وتجنب التكرار.
        3. استخدم لغة عربية فصحى قوية وسلسة.
        4. لا تستخدم مقدمات مبتذلة مثل "في خطوة هامة..".
        
        النص الأصلي:
        {original_text[:8000]}
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {e}"

def upload_to_wp(image_data, title, content, wp_url, wp_user, wp_password):
    credentials = f"{wp_user}:{wp_password}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    headers_auth = {'Authorization': f'Basic {token}'}

    # 1. رفع الصورة
    media_id = 0
    if image_data:
        headers_img = headers_auth.copy()
        headers_img['Content-Disposition'] = 'attachment; filename=news-processed.jpg'
        headers_img['Content