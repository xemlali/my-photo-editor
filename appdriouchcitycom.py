import streamlit as st
from newspaper import Article
import requests
import base64
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import io
import numpy as np

# --- إعدادات الصفحة ---
st.set_page_config(page_title="المحرر الذكي (Gemini Pro)", layout="wide", page_icon="🗞️")
st.title("🗞️ المحرر الصحفي الشامل (نسخة Gemini Pro)")

# --- القائمة الجانبية ---
with st.sidebar:
    st.header("1. إعدادات الموقع")
    wp_url = st.text_input("رابط الموقع", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم (WordPress)")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")
    
    st.divider()
    st.header("2. إعدادات الذكاء الاصطناعي")
    api_key = st.text_input("مفتاح Gemini API", type="password")
    st.caption("احصل عليه من: aistudio.google.com")

# --- دوال معالجة الصور (الفلاتر) ---
def create_vignette(image, corner_darkness=180):
    # تحويل الصورة لنمط RGB لضمان التوافق
    if image.mode != 'RGB':
        image = image.convert('RGB')
        
    width, height = image.size
    
    # إنشاء قناع التدرج الدائري
    x = np.linspace(-1, 1, width)
    y = np.linspace(-1, 1, height)
    X, Y = np.meshgrid(x, y)
    radius = np.sqrt(X**2 + Y**2)
    
    # تطبيع القيمة (Normalize)
    radius = radius / np.max(radius)
    alpha = 1 - radius
    alpha = np.power(alpha, 1.5) # التحكم في نعومة التدرج
    
    # تطبيق القناع
    vignette_mask = Image.fromarray((alpha * 255).astype('uint8'), mode='L')
    black_layer = Image.new('RGB', (width, height), 'black')
    return Image.composite(image, black_layer, vignette_mask)

def process_image_for_news(image_url):
    try:
        # 1. تحميل الصورة
        response = requests.get(image_url, stream=True)
        img = Image.open(response.raw)
        
        # التأكد من أن الصورة RGB (لحل مشاكل صور PNG)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # 2. تحسين الألوان (Saturation)
        converter = ImageEnhance.Color(img)
        img = converter.enhance(1.4) # زيادة التشبع 40% لجعل الألوان زاهية
        
        # 3. تحسين التباين (Contrast)
        converter = ImageEnhance.Contrast(img)
        img = converter.enhance(1.2) 
        
        # 4. تحسين الحدة (Sharpness)
        converter = ImageEnhance.Sharpness(img)
        img = converter.enhance(1.3)
        
        # 5. إضافة الفينييت (تأثير انستغرام السينمائي)
        img = create_vignette(img)
        
        # تحويل النتيجة لملف بايتس
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        return buf.getvalue()
    except Exception as e:
        st.error(f"خطأ في معالجة الصورة: {e}")
        return None

# --- دوال الذكاء الاصطناعي (إعادة الصياغة) ---
def rewrite_article_ai(original_text, api_key):
    try:
        genai.configure(api_key=api_key)
        # استخدام الموديل المستقر Gemini Pro
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        أنت صحفي محترف (Senior Editor) في موقع إخباري مغربي.
        المطلوب: إعادة صياغة الخبر التالي بأسلوب مهني جداً.
        
        القواعد:
        1. **العنوان:** اكتب عنواناً واحداً فقط في السطر الأول. يجب أن يكون قوياً، جذاباً للنقر (Clickbait مهني)، ويراعي SEO.
        2. **المتن:** اكتب بأسلوب سردي قصصي (Storytelling) إن أمكن، وابتعد عن التكرار والحشو.
        3. **اللغة:** عربية فصحى سليمة، قوية ومؤثرة.
        4. **الهيكل:** فقرات قصيرة ومترابطة.
        
        النص الأصلي:
        {original_text[:6000]}
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"خطأ في الاتصال بـ AI: {e}"

# --- دوال ووردبريس ---
def upload_image_bytes(image_data, wp_url, wp_user, wp_password):
    credentials = f"{wp_user}:{wp_password}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    headers = {
        'Authorization': f'Basic {token}',
        'Content-Disposition': 'attachment; filename=processed-news.jpg',
        'Content-Type': 'image/jpeg'
    }
    try:
        response = requests.post(f"{wp_url}/wp-json/wp/v2/media", headers=headers, data=image_data)
        if response.status_code == 201:
            return response.json()['id']
        else:
            st.error(f"فشل رفع الصورة: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"خطأ اتصال WP: {e}")
        return None

def create_wp_post(title, content, image_id, wp_url, wp_user, wp_password):
    credentials = f"{wp_user}:{wp_password}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    headers = {'Authorization': f'Basic {token}', 'Content-Type': 'application/json'}
    
    post = {
        'title': title,
        'content': content,
        'status': 'draft', # مسودة
        'featured_media': image_id
    }
    return requests.post(f"{wp_url}/wp-json/wp/v2/posts", headers=headers, json=post)

# --- الواجهة الرئيسية ---
url_input = st.text_input("🔗 ضع رابط الخبر الأصلي هنا:")

if st.button("✨ تشغيل المعالج السحري"):
    if not api_key or not wp_password:
        st.warning("⚠️ تأكد من تعبئة مفتاح API وكلمة السر في القائمة الجانبية.")
    else:
        status_box = st.status("جاري العمل... ⏳", expanded=True)
        
        try:
            # 1. جلب الخبر
            status_box.write("📥 1. جاري سحب الخبر من المصدر...")
            article = Article(url_input)
            article.download()
            article.parse()
            
            # عرض البيانات الأولية
            # st.info(f"تم جلب: {article.title}") 

            # 2. معالجة الصورة
            status_box.write("🎨 2. جاري تحسين الصورة (ألوان، تباين، تأثير