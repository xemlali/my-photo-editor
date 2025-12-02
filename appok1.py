import streamlit as st
from newspaper import Article
import requests
import base64
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps # تم تصحيح هذا السطر
import io
import re

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="المحرر الاحترافي 5.1", layout="wide", page_icon="📰")

# --- 2. القائمة الجانبية ---
with st.sidebar:
    st.header("⚙️ الإعدادات التقنية")
    wp_url = st.text_input("رابط الموقع", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")
    st.divider()
    api_key = st.text_input("مفتاح Gemini API", type="password")
    
    st.divider()
    st.header("🎨 هندسة الصورة")
    remove_logo = st.checkbox("قص اللوغو السفلي", value=True)
    red_intensity = st.slider("كثافة المسحة الحمراء", 0.0, 0.5, 0.10, 0.05)

# --- 3. الدوال البرمجية المتقدمة ---

def resize_to_exact_dimensions(image, target_w=768, target_h=432):
    """قص وتغيير حجم ذكي للحصول على الأبعاد بالضبط"""
    current_w, current_h = image.size
    target_ratio = target_w / target_h
    current_ratio = current_w / current_h
    
    if current_ratio > target_ratio:
        new_h = target_h
        new_w = int(new_h * current_ratio)
        img_resized = image.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        img_final = img_resized.crop((left, 0, left + target_w, target_h))
    else:
        new_w = target_w
        new_h = int(new_w / current_ratio)
        img_resized = image.resize((new_w, new_h), Image.LANCZOS)
        top = (new_h - target_h) // 2
        img_final = img_resized.crop((0, top, target_w, top + target_h))
        
    return img_final

def process_image_pro(image_input, crop_logo, red_factor):
    try:
        if isinstance(image_input, str): 
            response = requests.get(image_input, stream=True)
            img = Image.open(response.raw)
        else: 
            img = Image.open(image_input)
        
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # 1. قص اللوغو
        if crop_logo:
            w, h = img.size
            img = img.crop((0, 0, w, int(h * 0.88)))

        # 2. القلب الأفقي
        img = ImageOps.mirror(img)

        # 3. ضبط الأبعاد (768x432)
        img = resize_to_exact_dimensions(img, 768, 432)

        # 4. المعالجة اللونية
        img = ImageEnhance.Color(img).enhance(1.5) 
        img = ImageEnhance.Contrast(img).enhance(1.1)
        
        # 5. المسحة الحمراء (تصحيح الكود هنا)
        red_layer = Image.new('RGB', img.size, (150, 0, 0))
        img = Image.blend(img, red_layer, alpha=red_factor)

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        return buf.getvalue()
    except Exception as e:
        return None

def clean_text(text):
    """تنظيف الرموز"""
    text = text.replace('**', '').replace('##', '').replace('__', '')
    text = re.sub(r'^\s*[\#\*\-]+\s*', '', text)
    return text.strip()

def rewrite_article_pro(text, key):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        أنت رئيس تحرير محترف. أعد صياغة هذا الخبر للنشر:
        
        القواعد:
        1. أسلوب بشري حيوي 100% (ابتعد عن لغة الروبوتات).
        2. عنوان واحد ذكي ومثير (Clickbait صادق) في السطر الأول.
        3. هيكل المقال: فقرات قصيرة ومترابطة.
        4. ممنوع استخدام كلمات مثل: "جدير بالذكر"، "في إطار"، "مما لا شك فيه".
        
        النص:
        {text[:9000]}
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {e}"

def upload_to_wp_pro(img_data, title, content, videos, url, user, password):
    creds = f"{user}:{password}"
    token = base64.b64encode(creds.encode()).decode('utf-8')
    headers_auth = {'Authorization': f'Basic {token}'}

    # رفع الصورة
    media_id = 0
    if img_data:
        headers_img = headers_auth.copy()
        headers_img['Content-Disposition'] = 'attachment; filename=news-768x432.jpg'
        headers_img['Content-Type'] = 'image/jpeg'
        try:
            r = requests.post(f"{url}/wp-json/wp/v2/media", headers=headers_img, data=img_data)
            if r.status_code == 201:
                media_id = r.json()['id']
        except:
            pass

    # تجهيز المحتوى والفيديو
    final_content = content
    if videos:
        final_content += "\n\n<h3>شاهد أيضاً:</h3>"
        for video_url in videos:
            final_content += f"\n{video_url}\n"

    # رفع المقال
    headers_post = headers_auth.copy()
    headers_post['Content-Type'] = 'application/json'
    post_data = {
        'title': title,
        'content': final_content,
        'status': 'draft',
        'featured_media': media_id
    }
    return requests.post(f"{url}/wp-json/wp/v2/posts", headers=headers_post, json=post_data)

# --- 4. الواجهة ---
st.title("📰 المحرر الصحفي (DriouchCity Pro)")
st.markdown("---")

tab1, tab2 = st.tabs(["🔗 رابط خبر", "📝 يدوي"])

with tab1:
    url_input = st.text_input("رابط الخبر:")
    btn_link = st.button("تنفيذ المعالجة", type="primary")

with tab2:
    col_img, col_txt = st.columns([1, 2])
    with col_img: uploaded_img = st.file_uploader("صورة", type=['jpg','png','jpeg'])
    with col_txt: uploaded_txt = st.text_area("النص", height=150)
    btn_manual = st.button("تنفيذ اليدوي", type="primary")

# المنطق