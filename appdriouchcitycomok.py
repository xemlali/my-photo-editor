import streamlit as st
from newspaper import Article
import requests
import base64
import google.generativeai as genai
from PIL import Image, ImageEnhance
import io
import numpy as np

# --- إعدادات الصفحة ---
st.set_page_config(page_title="المحرر الذكي (Gemini 2.0)", layout="wide", page_icon="🚀")
st.title("🚀 المحرر الصحفي الشامل (نسخة Gemini 2.0 Flash)")

# --- القائمة الجانبية ---
with st.sidebar:
    st.header("1. إعدادات الموقع")
    wp_url = st.text_input("رابط الموقع", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم (WordPress)")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")
    
    st.divider()
    st.header("2. إعدادات الذكاء الاصطناعي")
    api_key = st.text_input("مفتاح Gemini API", type="password")

# --- دوال معالجة الصور ---
def create_vignette(image):
    # التأكد من نمط الألوان
    if image.mode != 'RGB':
        image = image.convert('RGB')
        
    width, height = image.size
    x = np.linspace(-1, 1, width)
    y = np.linspace(-1, 1, height)
    X, Y = np.meshgrid(x, y)
    
    radius = np.sqrt(X**2 + Y**2)
    radius = radius / np.max(radius)
    
    alpha = 1 - radius
    alpha = np.power(alpha, 1.5) # نعومة التدرج
    
    vignette_mask = Image.fromarray((alpha * 255).astype('uint8'), mode='L')
    black_layer = Image.new('RGB', (width, height), 'black')
    
    return Image.composite(image, black_layer, vignette_mask)

def process_image_for_news(image_url):
    try:
        response = requests.get(image_url, stream=True)
        img = Image.open(response.raw)
        
        # معالجة صيغ الصور المختلفة
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # 1. زيادة تشبع الألوان (Saturation)
        converter = ImageEnhance.Color(img)
        img = converter.enhance(1.4) 
        
        # 2. زيادة التباين (Contrast)
        converter = ImageEnhance.Contrast(img)
        img = converter.enhance(1.2) 
        
        # 3. زيادة الحدة (Sharpness)
        converter = ImageEnhance.Sharpness(img)
        img = converter.enhance(1.3)
        
        # 4. إضافة الهالة السوداء
        img = create_vignette(img)
        
        # الحفظ في الذاكرة
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        return buf.getvalue()
    except Exception as e:
        st.error(f"خطأ في معالجة الصورة: {e}")
        return None

# --- دوال الذكاء الاصطناعي (Gemini 2.0) ---
def rewrite_article_ai(original_text, api_key):
    try:
        genai.configure(api_key=api_key)
        
        # هنا التعديل الجوهري: استخدام الموديل المتوفر لديك
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
        return f"خطأ في AI: {e}"

# --- دوال النشر في ووردبريس ---
def upload_image_bytes(image_data, wp_url, wp_user, wp_password):
    credentials = f"{wp_user}:{wp_password}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    headers = {
        'Authorization': f'Basic {token}',
        'Content-Disposition': 'attachment; filename=news-processed.jpg',
        'Content-Type': 'image/jpeg'
    }
    try:
        response = requests.post(f"{wp_url}/wp-json/wp/v2/media", headers=headers, data=image_data)
        if response.status_code == 201:
            return response.json()['id']
        return None
    except:
        return None

def create_wp_post(title, content, image_id, wp_url, wp_user, wp_password):
    credentials