import streamlit as st
from newspaper import Article
import requests
import base64
import google.generativeai as genai
from PIL import Image, ImageEnhance
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

# --- دوال معالجة الصور ---
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
        
        converter = ImageEnhance.Color(img)
        img = converter.enhance(1.4) 
        
        converter = ImageEnhance.Contrast(img)
        img = converter.enhance(1.2) 
        
        converter = ImageEnhance.Sharpness(img)
        img = converter.enhance(1.3)
        
        img = create_vignette(img)
        
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        return buf.getvalue()
    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None

# --- دوال الذكاء الاصطناعي ---
def rewrite_article_ai(original_text, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        أنت صحفي محترف. أعد صياغة الخبر التالي بأسلوب مهني.
        القواعد:
        1. عنوان واحد جذاب في السطر الأول.
        2. متن بأسلوب سردي وقصصي.
        3. لغة عربية قوية وخالية من الحشو.
        
        النص الأصلي:
        {original_text[:6000]}
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI Error: {e}"

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
            return None
    except:
        return None

def create_wp_post(title, content, image_id, wp_url, wp_user, wp_password):
    credentials = f"{wp_user}:{wp_password}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    headers = {'Authorization': f'Basic {token}', 'Content-Type': 'application/json'}
    post = {
        'title': title,
        'content': content,
        'status': 'draft',
        'featured_media': image_id
    }
    return requests.post(f"{wp_url}/wp-json/wp/v2/posts", headers=headers, json=post)

# --- الواجهة الرئيسية ---
url_input = st.text_input("🔗 ضع رابط الخبر الأصلي هنا:")

if st.button("✨ تشغيل المعالج"):
    if not api_key or not wp_password:
        st.warning("⚠️ أدخل البيانات في القائمة الجانبية")
    else:
        status_box = st.status("جاري العمل...", expanded=True)
        
        try:
            # 1. جلب الخبر
            status_box.write("📥 1. جلب الخبر...")
            article = Article(url_input)
            article.download()
            article.parse()
            
            # 2. معالجة الصورة
            status_box.write("🎨 2. معالجة الصورة...")
            processed_image = None
            if article.top_image:
                processed_image = process_image_for_news(article.top_image)
                if processed_image:
                    st.image(processed_image, caption="الصورة المحسنة", width=400)

            # 3. الذكاء الاصطناعي
            status_box.write("🤖 3. إعادة الصياغة...")
            ai_result = rewrite_article_ai(article.text, api_key)
            
            if "Error" in ai_result:
                status_box.update(label="خطأ في AI", state="error")
                st.error(ai_result)
            else:
                lines = ai_result.split('\n')
                final_title = next((line for line in lines if line.strip()), "عنوان")
                final_title = final_title.replace('*', '').replace('#', '').strip()
                final_content = "\n".join([line for line in lines if line.strip() != final_title])
                
                st.subheader("معاينة:")
                st.text_area("العنوان", final_title, height=70)
                st.markdown(final_content)

                # 4. النشر
                status_box.write("🚀 4. النشر...")
                media_id = 0
                if processed_image:
                    media_id = upload_image_bytes(processed_image, wp_url, wp_user, wp_password)
                
                res = create_wp_post(final_title, final_content, media_id, wp_url, wp_user, wp_password)
                
                if res.status_code == 201:
                    status_box.update(label="✅ تم!", state="complete", expanded=False)
                    st.success(f"تم! [رابط المقال]({res.json()['link']})")
                else:
                    st.error(f"خطأ: {res.text}")

        except Exception as e:
            st.error(f"Error: {e}")