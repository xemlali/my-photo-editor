import streamlit as st
from newspaper import Article
import requests
import base64
import google.generativeai as genai
from PIL import Image, ImageEnhance
import io
import numpy as np

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="المحرر الذكي 2.0", layout="wide")

# --- 2. القائمة الجانبية ---
with st.sidebar:
    st.header("🔐 بيانات الاتصال")
    wp_url = st.text_input("رابط الموقع", "https://driouchcity.com")
    wp_user = st.text_input("اسم المستخدم (WordPress)")
    wp_password = st.text_input("كلمة مرور التطبيق", type="password")
    st.divider()
    api_key = st.text_input("مفتاح Gemini API", type="password")

# --- 3. الواجهة الرئيسية ---
st.title("🚀 المحرر الصحفي (Gemini 2.0)")
st.markdown("---")

col1, col2 = st.columns([3, 1])
with col1:
    url_input = st.text_input("🔗 رابط الخبر:", placeholder="https://...")
with col2:
    st.write("") 
    st.write("") 
    start_btn = st.button("✨ ابدأ المعالجة", use_container_width=True, type="primary")

# --- 4. المحرك (الدوال) ---

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
    
    # تحويل القناع
    mask_arr = (alpha * 255).astype('uint8')
    vignette_mask = Image.fromarray(mask_arr, mode='L')
    black_layer = Image.new('RGB', (width, height), 'black')
    return Image.composite(image, black_layer, vignette_mask)

def process_image_for_news(image_url):
    try:
        response = requests.get(image_url, stream=True)
        img = Image.open(response.raw)
        
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # تحسينات بصرية
        img = ImageEnhance.Color(img).enhance(1.4)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img = ImageEnhance.Sharpness(img).enhance(1.3)
        img = create_vignette(img)
        
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        return buf.getvalue()
    except:
        return None

def rewrite_article_ai(text, key):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        أنت صحفي خبير. أعد صياغة الخبر التالي بأسلوب مهني:
        1. عنوان جذاب (SEO) في السطر الأول.
        2. متن قصصي مترابط.
        3. لغة عربية قوية.
        
        النص:
        {text[:8000]}
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {e}"

def upload_to_wp(img_data, title, content, url, user, password):
    # تجهيز التوثيق
    creds = f"{user}:{password}"
    token = base64.b64encode(creds.encode()).decode('utf-8')
    headers_auth = {'Authorization': f'Basic {token}'}

    # 1. رفع الصورة (هنا كان الخطأ السابق وتم إصلاحه)
    media_id = 0
    if img_data:
        headers_img = headers_auth.copy()
        # قمنا بتقصير السطر لتفادي أخطاء النسخ
        headers_img['Content-Disposition'] = 'attachment; filename=news.jpg'
        headers_img['Content-Type'] = 'image/jpeg'
        
        try:
            api = f"{url}/wp-json/wp/v2/media"
            r = requests.post(api, headers=headers_img, data=img_data)
            if r.status_code == 201:
                media_id = r.json()['id']
        except:
            pass

    # 2. رفع المقال
    headers_post = headers_auth.copy()
    headers_post['Content-Type'] = 'application/json'
    
    post_data = {
        'title': title,
        'content': content,
        'status': 'draft',
        'featured_media': media_id
    }
    
    api_post = f"{url}/wp-json/wp/v2/posts"
    return requests.post(api_post, headers=headers_post, json=post_data)

# --- 5. التنفيذ ---
if start_btn:
    if not url_input or not api_key or not wp_password:
        st.error("⚠️ تأكد من ملء الرابط وبيانات الدخول كاملة.")
    else:
        with st.status("جاري العمل... ⏳", expanded=True) as status:
            try:
                # 1. الجلب
                status.write("📥 جلب الخبر...")
                article = Article(url_input)
                article.download()
                article.parse()
                
                # 2. الصورة
                status.write("🎨 معالجة الصورة...")
                img_bytes = None
                if article.top_image:
                    img_bytes = process_image_for_news(article.top_image)
                    if img_bytes:
                        st.image(img_bytes, caption="الصورة المحسنة", width=350)
                
                # 3. الصياغة
                status.write("🤖 الذكاء الاصطناعي...")
                ai_txt = rewrite_article_ai(article.text, api_key)
                
                if "Error" in ai_txt:
                    status.update(label="خطأ AI", state="error")
                    st.error(ai_txt)
                else:
                    lines = ai_txt.split('\n')
                    # استخراج العنوان بذكاء
                    tit = next((l for l in lines if l.strip()), "عنوان")
                    tit = tit.replace('*', '').replace('#', '').strip()
                    # استخراج المحتوى
                    con = "\n".join([l for l in lines if l.strip() != tit])
                    
                    st.success("تمت الصياغة:")
                    st.text_area("العنوان", tit)
                    st.markdown(con)
                    
                    # 4. النشر
                    status.write("🚀 الرفع للموقع...")
                    res = upload_to_wp(img_bytes, tit, con, wp_url, wp_user, wp_password)
                    
                    if res.status_code == 201:
                        status.update(label="✅ تم بنجاح!", state="complete", expanded=False)
                        lnk = res.json()['link']
                        st.balloons()
                        st.success(f"تم الحفظ! [رابط المعاينة]({lnk})")
                    else:
                        status.update(label="خطأ نشر", state="error")
                        st.error(f"Error: {res.text}")

            except Exception as e:
                status.update(label="خطأ غير متوقع", state="error")
                st.error(f"Details: {e}")